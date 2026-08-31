"""TableDataset 的纵向与按学生安全关联服务。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models.merge_models import ConflictResolution, MergeConflict, MergeMode, MergeResult, MergedRecord
from app.models.table_dataset import Provenance, TableDataset, TableRow
from app.utils.value_normalizer import normalize_class_name, normalize_text


class DatasetMergeService:
    def merge(self, datasets: list[TableDataset], mode: MergeMode) -> MergeResult:
        if not datasets:
            raise ValueError("请至少添加一份已分析的数据。")
        return self.merge_vertical(datasets) if mode is MergeMode.VERTICAL else self.merge_by_student(datasets)

    def merge_vertical(self, datasets: list[TableDataset]) -> MergeResult:
        columns, labels = self._columns(datasets)
        records = [
            MergedRecord({key: row.values.get(key, "") for key in columns}, {key: row.provenance for key, value in row.values.items() if value != ""})
            for dataset in datasets for row in dataset.rows
        ]
        return MergeResult(MergeMode.VERTICAL, columns, labels, records, source_datasets=self._sources(datasets))

    def merge_by_student(self, datasets: list[TableDataset]) -> MergeResult:
        columns, labels = self._columns(datasets)
        result = MergeResult(MergeMode.STUDENT, columns, labels, [], source_datasets=self._sources(datasets))
        all_rows = [row for dataset in datasets for row in dataset.rows]
        name_evidence = self._name_evidence(all_rows)
        for row in all_rows:
            candidates = self._find_candidates(result.records, row, name_evidence)
            if len(candidates) == 1:
                self._combine(result, candidates[0], row)
            else:
                index = len(result.records)
                status = "unresolved" if len(candidates) > 1 else "unmatched"
                result.records.append(MergedRecord(dict(row.values), {key: row.provenance for key, value in row.values.items() if value != ""}, status))
                if len(candidates) > 1:
                    result.unresolved_record_indexes.append(index)
        return result

    def resolve_conflict(self, result: MergeResult, conflict_id: int, resolution: ConflictResolution, manual_value: Any | None = None) -> None:
        conflict = next((item for item in result.conflicts if item.id == conflict_id), None)
        if conflict is None:
            raise ValueError("合并冲突不存在。")
        if resolution is ConflictResolution.UNRESOLVED:
            conflict.resolution = resolution
            conflict.resolved_value = None
            return
        if resolution is ConflictResolution.MANUAL and manual_value is None:
            raise ValueError("手工解决冲突时必须提供值。")
        chosen = conflict.value_a if resolution is ConflictResolution.USE_A else conflict.value_b if resolution is ConflictResolution.USE_B else manual_value
        record = result.records[conflict.record_index]
        record.values[conflict.field] = chosen
        if resolution is ConflictResolution.USE_A:
            record.provenance[conflict.field] = conflict.source_a
        elif resolution is ConflictResolution.USE_B:
            record.provenance[conflict.field] = conflict.source_b
        else:
            record.provenance[conflict.field] = Provenance("人工解决", "冲突处理", 0)
        conflict.resolution = resolution
        conflict.resolved_value = chosen

    @staticmethod
    def _columns(datasets: list[TableDataset]) -> tuple[list[str], dict[str, str]]:
        columns: list[str] = []
        labels: dict[str, str] = {}
        for dataset in datasets:
            for key in dataset.columns:
                if key not in columns:
                    columns.append(key)
                    labels[key] = dataset.display_label(key)
        return columns, labels

    @staticmethod
    def _sources(datasets: list[TableDataset]) -> list[tuple[str, str | None]]:
        return [(dataset.source_file, dataset.source_sheet) for dataset in datasets]

    @staticmethod
    def _name_evidence(rows: list[TableRow]) -> dict[str, set[tuple[str, str]]]:
        evidence: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for row in rows:
            name = normalize_text(row.values.get("name"))
            if name:
                evidence[name].add((normalize_text(row.values.get("student_number")), normalize_class_name(row.values.get("class_name"))))
        return evidence

    def _find_candidates(self, records: list[MergedRecord], row: TableRow, name_evidence: dict[str, set[tuple[str, str]]]) -> list[int]:
        values = row.values
        number = normalize_text(values.get("student_number"))
        if number:
            matches = [i for i, item in enumerate(records) if normalize_text(item.values.get("student_number")) == number]
            if matches:
                return matches

        name = normalize_text(values.get("name"))
        class_name = normalize_class_name(values.get("class_name"))
        if not name:
            return []
        named = [i for i, item in enumerate(records) if normalize_text(item.values.get("name")) == name]
        if class_name:
            return [
                i for i in named
                if normalize_class_name(records[i].values.get("class_name")) == class_name
                and (not number or not normalize_text(records[i].values.get("student_number")))
            ]
        # 唯一姓名只在全量输入没有任何相互矛盾身份线索且候选唯一时才关联。
        safe_named = [i for i in named if not number or not normalize_text(records[i].values.get("student_number"))]
        return safe_named if len(safe_named) == 1 and len(name_evidence[name]) == 1 else []

    def _combine(self, result: MergeResult, record_index: int, incoming: TableRow) -> None:
        target = result.records[record_index]
        for field, value in incoming.values.items():
            if value in (None, ""):
                continue
            existing = target.values.get(field, "")
            if existing in (None, ""):
                target.values[field] = value
                target.provenance[field] = incoming.provenance
            elif existing != value:
                result.conflicts.append(MergeConflict(
                    id=len(result.conflicts) + 1,
                    record_index=record_index,
                    field=field,
                    value_a=existing,
                    value_b=value,
                    source_a=target.provenance[field],
                    source_b=incoming.provenance,
                ))
