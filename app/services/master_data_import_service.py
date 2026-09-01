"""从资料汇总的 TableDataset 预览并原子初始化基础资料。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.table_dataset import TableDataset
from app.repositories.database import DatabaseManager
from app.utils.value_normalizer import normalize_column_name


CORE_FIELDS = {"name", "student_number", "class_name", "major", "grade", "phone", "dormitory", "remark"}
NON_EXTRA_FIELDS = {
    "sequence", "date", "course", "status", "late", "absent", "leave", "expected", "actual",
    "building", "room_number", "score",
}


@dataclass(frozen=True)
class ImportIssue:
    row_index: int
    source_file: str
    source_sheet: str | None
    source_row: int
    reason: str


@dataclass
class ImportPreview:
    new_classes: int = 0
    existing_classes: int = 0
    class_conflicts: list[str] = field(default_factory=list)
    new_dormitories: int = 0
    existing_dormitories: int = 0
    pending_dormitories: list[str] = field(default_factory=list)
    new_students: int = 0
    existing_students: int = 0
    updatable_students: int = 0
    student_conflicts: list[str] = field(default_factory=list)
    student_conflict_details: list[ImportIssue] = field(default_factory=list)
    invalid_records: list[ImportIssue] = field(default_factory=list)
    skipped_records: list[ImportIssue] = field(default_factory=list)
    pending_dormitory_details: list[ImportIssue] = field(default_factory=list)
    extra_field_count: int = 0

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_records)


class MasterDataImportService:
    """预览不写库；apply 按班级、寝室、学生顺序在同一事务中写入。"""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def preview(
        self,
        dataset: TableDataset,
        dormitory_corrections: dict[str, tuple[str, str] | None] | None = None,
    ) -> ImportPreview:
        preview = ImportPreview(extra_field_count=len(self._extra_columns(dataset)))
        classes: dict[str, tuple[str, str]] = {}
        dormitories: set[tuple[str, str, str]] = set()
        seen_numbers: dict[str, tuple[int, str, str]] = {}
        with self.database.connection() as connection:
            for row_index, row in enumerate(dataset.rows):
                values = self._values(row.values)
                class_name = values.get("class_name", "")
                if class_name:
                    candidate = (values.get("major", ""), values.get("grade", ""))
                    if class_name not in classes:
                        classes[class_name] = candidate
                        existing = connection.execute("SELECT major, grade FROM classes WHERE standard_name = ?", (class_name,)).fetchone()
                        if existing:
                            preview.existing_classes += 1
                            if self._conflict(existing["major"], candidate[0]) or self._conflict(existing["grade"], candidate[1]):
                                preview.class_conflicts.append(class_name)
                        else:
                            preview.new_classes += 1
                    elif classes[class_name] != candidate and any(candidate):
                        preview.class_conflicts.append(class_name)
                parsed = self._resolved_dormitory(values, dormitory_corrections)
                if parsed and parsed not in dormitories:
                    dormitories.add(parsed)
                    exists = connection.execute("SELECT 1 FROM dormitories WHERE standard_name = ?", (parsed[2],)).fetchone()
                    preview.existing_dormitories += int(bool(exists))
                    preview.new_dormitories += int(not bool(exists))
                elif values.get("dormitory", ""):
                    preview.pending_dormitories.append(values["dormitory"])
                    preview.pending_dormitory_details.append(self._issue(row_index, row, "寝室无法可靠解析，请填写楼栋和寝室号或跳过。"))
                number = values.get("student_number", "")
                missing = [label for key, label in (("name", "姓名"), ("student_number", "学号"), ("class_name", "班级")) if not values.get(key)]
                if missing:
                    issue = self._issue(row_index, row, f"缺少必填字段：{'、'.join(missing)}。")
                    preview.invalid_records.append(issue)
                    preview.skipped_records.append(issue)
                    continue
                if number in seen_numbers:
                    first_index, first_name, first_class = seen_numbers[number]
                    reason = f"同一数据集学号重复；第 {first_index + 1} 条记录已保留。"
                    if first_name != values["name"] or first_class != values["class_name"]:
                        reason += " 姓名或班级不一致，不能自动合并。"
                    issue = self._issue(row_index, row, reason)
                    preview.student_conflicts.append(number)
                    preview.student_conflict_details.append(issue)
                    preview.skipped_records.append(issue)
                    continue
                seen_numbers[number] = (row_index, values["name"], values["class_name"])
                existing = connection.execute("SELECT * FROM students WHERE student_number = ?", (number,)).fetchone()
                if not existing:
                    preview.new_students += 1
                    continue
                preview.existing_students += 1
                if self._student_identity_conflict(existing, values):
                    preview.student_conflicts.append(number)
                    issue = self._issue(row_index, row, "学号已存在，但姓名或班级不一致，已跳过以避免覆盖。")
                    preview.student_conflict_details.append(issue)
                    preview.skipped_records.append(issue)
                elif self._has_empty_fill(existing, values):
                    preview.updatable_students += 1
                if self._has_nonempty_conflict(existing, values):
                    preview.student_conflicts.append(number)
        preview.class_conflicts = sorted(set(preview.class_conflicts))
        preview.pending_dormitories = sorted(set(preview.pending_dormitories))
        preview.student_conflicts = sorted(set(preview.student_conflicts))
        return preview

    def apply(
        self,
        dataset: TableDataset,
        dormitory_corrections: dict[str, tuple[str, str] | None] | None = None,
    ) -> ImportPreview:
        preview = self.preview(dataset, dormitory_corrections)
        skipped_indexes = {issue.row_index for issue in preview.skipped_records}
        extra_columns = self._extra_columns(dataset)
        with self.database.transaction() as connection:
            # 1. 班级：只创建缺失项，已有的非空信息不被静默覆盖。
            for class_name, major, grade in self._class_rows(dataset):
                if not connection.execute("SELECT 1 FROM classes WHERE standard_name = ?", (class_name,)).fetchone():
                    connection.execute(
                        "INSERT INTO classes (standard_name, major, grade) VALUES (?, ?, ?)",
                        (class_name, major or None, grade or None),
                    )
            # 2. 寝室：仅可靠解析的值才创建。
            for row in dataset.rows:
                parsed = self._resolved_dormitory(self._values(row.values), dormitory_corrections)
                if parsed and not connection.execute("SELECT 1 FROM dormitories WHERE standard_name = ?", (parsed[2],)).fetchone():
                    connection.execute(
                        "INSERT INTO dormitories (building, room_number, standard_name) VALUES (?, ?, ?)", parsed
                    )
            # 3. 学生与扩展资料：同学号仅补全空值，任何冲突均不覆盖。
            for row_index, row in enumerate(dataset.rows):
                if row_index in skipped_indexes:
                    continue
                values = self._values(row.values)
                number, name, class_name = values.get("student_number", ""), values.get("name", ""), values.get("class_name", "")
                resolved_dormitory = self._resolved_dormitory(values, dormitory_corrections)
                if resolved_dormitory:
                    values["dormitory"] = resolved_dormitory[2]
                elif values.get("dormitory"):
                    values["dormitory"] = ""  # 未确认的原始寝室不写入学生核心资料。
                existing = connection.execute("SELECT * FROM students WHERE student_number = ?", (number,)).fetchone()
                if existing is None:
                    cursor = connection.execute(
                        """INSERT INTO students (name, student_number, class_name, major, grade, phone, dormitory, remark)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        tuple(values.get(field) or None for field in ("name", "student_number", "class_name", "major", "grade", "phone", "dormitory", "remark")),
                    )
                    student_id = int(cursor.lastrowid)
                elif self._student_identity_conflict(existing, values):
                    continue  # preview 已记录，防御性保留以避免并发数据变化时覆盖。
                else:
                    student_id = int(existing["id"])
                    assignments = {field: values[field] for field in CORE_FIELDS - {"name", "student_number", "class_name"} if values.get(field) and not existing[field]}
                    if assignments:
                        sql = ", ".join(f"{field} = ?" for field in assignments)
                        connection.execute(f"UPDATE students SET {sql}, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?", (*assignments.values(), student_id))
                for key, label in extra_columns.items():
                    value = self._text(row.values.get(key))
                    if not value:
                        continue
                    field_key = normalize_column_name(label)
                    present = connection.execute("SELECT field_value FROM student_extra_fields WHERE student_id = ? AND field_key = ?", (student_id, field_key)).fetchone()
                    if present is None:
                        connection.execute("INSERT INTO student_extra_fields (student_id, field_name, field_key, field_value) VALUES (?, ?, ?, ?)", (student_id, label, field_key, value))
                    elif not present["field_value"]:
                        connection.execute("UPDATE student_extra_fields SET field_value = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ','now') WHERE student_id = ? AND field_key = ?", (value, student_id, field_key))
            for (class_name,) in connection.execute("SELECT standard_name FROM classes").fetchall():
                connection.execute("UPDATE classes SET student_count = (SELECT COUNT(*) FROM students WHERE class_name = ?), updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ','now') WHERE standard_name = ?", (class_name, class_name))
        return preview

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value).strip()

    def _values(self, values: dict[str, Any]) -> dict[str, str]:
        keys = CORE_FIELDS | {"building", "room_number"}
        return {key: self._text(values.get(key)) for key in keys}

    def _class_rows(self, dataset: TableDataset):
        seen: set[str] = set()
        for row in dataset.rows:
            values = self._values(row.values)
            if values["class_name"] and values["class_name"] not in seen:
                seen.add(values["class_name"])
                yield values["class_name"], values["major"], values["grade"]

    @staticmethod
    def _parse_dormitory(values: dict[str, str]) -> tuple[str, str, str] | None:
        building, room = values.get("building", ""), values.get("room_number", "")
        if building and room:
            return building, room, f"{building}-{room}"
        raw = values.get("dormitory", "")
        match = re.fullmatch(r"\s*(.+?栋?)\s*(?:[-—_\s]+)?\s*(\d{2,4})\s*", raw)
        if not match:
            return None
        building, room = match.groups()
        if not building or not room:
            return None
        return building, room, f"{building}-{room}"

    def _resolved_dormitory(
        self,
        values: dict[str, str],
        corrections: dict[str, tuple[str, str] | None] | None,
    ) -> tuple[str, str, str] | None:
        parsed = self._parse_dormitory(values)
        if parsed:
            return parsed
        raw = values.get("dormitory", "")
        if not raw or not corrections or raw not in corrections:
            return None
        corrected = corrections[raw]
        if corrected is None:
            return None
        building, room = (part.strip() for part in corrected)
        if not building or not room:
            return None
        return building, room, f"{building}-{room}"

    @staticmethod
    def _issue(row_index: int, row, reason: str) -> ImportIssue:
        return ImportIssue(row_index, row.provenance.source_file, row.provenance.source_sheet, row.provenance.source_row, reason)

    @staticmethod
    def _conflict(existing: Any, incoming: str) -> bool:
        return bool(existing and incoming and str(existing).strip() != incoming)

    def _student_identity_conflict(self, existing, values: dict[str, str]) -> bool:
        return self._conflict(existing["name"], values.get("name", "")) or self._conflict(existing["class_name"], values.get("class_name", ""))

    def _has_empty_fill(self, existing, values: dict[str, str]) -> bool:
        return any(values.get(field) and not existing[field] for field in CORE_FIELDS - {"name", "student_number", "class_name"})

    def _has_nonempty_conflict(self, existing, values: dict[str, str]) -> bool:
        return any(self._conflict(existing[field], values.get(field, "")) for field in CORE_FIELDS - {"name", "student_number", "class_name"})

    @staticmethod
    def _extra_columns(dataset: TableDataset) -> dict[str, str]:
        columns: dict[str, str] = {}
        for key in dataset.columns:
            label = dataset.display_label(key).removeprefix("custom:")
            normalized_label = normalize_column_name(label)
            if key not in dataset.custom_fields or not key.startswith("custom:"):
                continue
            if key.removeprefix("custom:") in NON_EXTRA_FIELDS or normalized_label in {"楼栋", "房间号", "寝室号", "宿舍号", "日期", "课程", "状态", "迟到", "缺勤", "请假", "应到", "实到", "序号"}:
                continue
            columns[key] = label
        return columns
