"""导入识别、持久化、重复判断与待确认处理的业务编排。"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.models.field_mapping import DetectedField, StandardField
from app.models.import_session import ImportSession
from app.models.parsed_record import ParsedRecord
from app.parsers.excel_reader import list_sheets, read_raw
from app.parsers.field_detector import detect_field
from app.parsers.header_detector import detect_header
from app.repositories.field_mapping_repository import FieldMappingRepository
from app.repositories.import_repository import ImportRepository
from app.repositories.task_repository import TaskRepository
from app.services.attendance_transformer import AttendanceEntry, AttendanceTransformer
from app.services.master_data_service import MasterDataService
from app.services.student_match_service import StudentMatchService
from app.utils.value_normalizer import normalize_date, normalize_text


CORE = {StandardField.NAME, StandardField.STUDENT_NUMBER, StandardField.CLASS_NAME, StandardField.DATE, StandardField.COURSE}


class FileDuplicateError(ValueError):
    """同一任务中已经导入过相同内容的同一工作表。"""


class PendingResolutionError(ValueError):
    """待确认记录不能按请求解决。"""


@dataclass(frozen=True)
class ImportResult:
    source_file_id: int
    success_count: int
    pending_count: int
    duplicate_count: int
    exact_duplicate_skip_count: int
    conflict_count: int


class ImportService:
    def __init__(self, database, master: MasterDataService, imports_directory: str | Path | None = None) -> None:
        self.database = database
        self.mappings = FieldMappingRepository(database)
        self.master = master
        self.matcher = StudentMatchService(master)
        self.repository = ImportRepository(database)
        self.tasks = TaskRepository(database)
        self.transformer = AttendanceTransformer()
        self.imports_directory = Path(imports_directory or Path(__file__).resolve().parents[2] / "imports")

    def sheets(self, path: str | Path) -> list[str]:
        return list_sheets(Path(path))

    def analyze(self, path: str | Path, sheet_name: str | None = None, header_row: int | None = None) -> ImportSession:
        source = Path(path)
        frame = read_raw(source, sheet_name)
        detected = detect_header(frame) if header_row is None else (header_row, 100, "人工选择")
        session = ImportSession(source, sheet_name, frame, *detected)
        session.fields = self._detect_fields(session)
        return session

    def _detect_fields(self, session: ImportSession) -> list[DetectedField]:
        return [
            detect_field(i, name, session.raw_frame.iloc[session.header_row + 1:, i], self.mappings.get(name).standard_field if self.mappings.get(name) else None)
            for i, name in enumerate(session.headers) if name
        ]

    def apply_mappings(self, session: ImportSession, mapping: dict[int, StandardField], save: bool = True) -> ImportSession:
        mapping = {index: field if isinstance(field, StandardField) else StandardField(field) for index, field in mapping.items()}
        seen: set[StandardField] = set()
        for field in mapping.values():
            if field in CORE and field in seen:
                raise ValueError(f"核心字段“{field.value}”不能重复映射")
            if field in CORE:
                seen.add(field)
        session.records = []
        for offset, row in enumerate(session.raw_frame.iloc[session.header_row + 1:].itertuples(index=False, name=None)):
            raw = {session.headers[i]: row[i] for i in range(len(session.headers)) if session.headers[i]}
            normalized: dict[str, str] = {}
            sources: dict[str, str] = {}
            for i, field in mapping.items():
                if field in (StandardField.IGNORE, StandardField.OTHER) or i >= len(row):
                    continue
                value = row[i]
                if value is not None and str(value) != "nan":
                    normalized[field.value] = normalize_date(value) if field is StandardField.DATE else normalize_text(value)
                    sources[field.value] = "原始数据"
            record = ParsedRecord(session.header_row + offset + 2, raw, normalized, sources, source_file=session.file_path.name, sheet_name=session.sheet_name)
            self.matcher.match(record)
            session.records.append(record)
        if save:
            for i, field in mapping.items():
                if field not in (StandardField.IGNORE, StandardField.OTHER) and i < len(session.headers):
                    self.mappings.save(session.headers[i], field)
        return session

    def default_mapping(self, session: ImportSession) -> dict[int, StandardField]:
        return {field.column_index: field.detected_field for field in session.fields}

    def import_session(self, task_id: int, session: ImportSession, failure_injector: Callable[[], None] | None = None) -> ImportResult:
        """复制原文件并原子写入业务表；任一步失败都会清理本次新副本。"""
        if not session.records:
            raise ValueError("请先确认字段映射并生成预览。")
        if self.tasks.get(task_id) is None:
            raise ValueError("导入任务不存在。")
        source = session.file_path.resolve()
        file_hash = self._sha256(source)
        if self.repository.find_source_duplicate(task_id, file_hash, session.sheet_name):
            raise FileDuplicateError("该任务的此工作表已导入完全相同的文件内容。")

        self.imports_directory.mkdir(parents=True, exist_ok=True)
        destination = self.imports_directory / f"task-{task_id}-{file_hash}{source.suffix.lower()}"
        copied_by_this_call = not destination.exists()
        try:
            if copied_by_this_call:
                shutil.copy2(source, destination)
            if failure_injector:
                failure_injector()
            with self.database.transaction() as connection:
                if self.repository.find_source_duplicate(task_id, file_hash, session.sheet_name):
                    raise FileDuplicateError("该任务的此工作表已导入完全相同的文件内容。")
                source_file_id = self.repository.create_source_file(connection, {
                    "task_id": task_id, "original_name": source.name, "original_path": str(source), "stored_path": str(destination),
                    "file_type": source.suffix.lower().lstrip("."), "file_size": source.stat().st_size, "file_hash": file_hash,
                    "sheet_name": session.sheet_name, "record_count": len(session.records), "status": "处理中",
                })
                result = self._persist_records(connection, task_id, source_file_id, session.records, session.record_mode)
                connection.execute("UPDATE source_files SET status = ? WHERE id = ?", ("部分导入" if result.pending_count else "已导入", source_file_id))
                message = "导入完成" if not result.pending_count else "部分记录已转入待确认"
                if result.exact_duplicate_skip_count:
                    message += f"；完全重复跳过 {result.exact_duplicate_skip_count} 条"
                self.repository.create_log(connection, {
                    "task_id": task_id, "source_file_id": source_file_id, "total_rows": len(session.records),
                    "success_count": result.success_count, "pending_count": result.pending_count, "duplicate_count": result.duplicate_count,
                    "conflict_count": result.conflict_count, "message": message,
                })
                return result
        except Exception:
            if copied_by_this_call and destination.exists():
                destination.unlink()
            raise

    def _persist_records(self, connection, task_id: int, source_file_id: int, records: list[ParsedRecord], record_mode: str) -> ImportResult:
        if record_mode not in {"完整考勤名单", "仅异常名单"}:
            raise ValueError("数据记录方式必须是“完整考勤名单”或“仅异常名单”。")
        success_count = pending_count = duplicate_count = exact_duplicate_skip_count = conflict_count = 0
        for record in records:
            for entry in self.transformer.transform(record, complete_attendance=record_mode == "完整考勤名单"):
                values = self._attendance_values(task_id, source_file_id, record, entry)
                issue_type = ";".join(record.issues) if record.match_status != "正常" else None
                if issue_type is None:
                    issue_type = self.repository.find_record_duplicate(connection, values)
                if issue_type == "EXACT_DUPLICATE":
                    duplicate_count += 1
                    exact_duplicate_skip_count += 1
                    continue
                if issue_type:
                    self.repository.create_pending(connection, self._pending_values(task_id, source_file_id, record, entry, issue_type))
                    pending_count += 1
                    if issue_type == "POSSIBLE_DUPLICATE":
                        duplicate_count += 1
                    if record.match_status == "冲突":
                        conflict_count += 1
                else:
                    self.repository.create_attendance(connection, values)
                    success_count += 1
        return ImportResult(source_file_id, success_count, pending_count, duplicate_count, exact_duplicate_skip_count, conflict_count)

    def list_pending(self, task_id: int | None = None):
        return self.repository.list_pending(task_id)

    def list_logs(self, task_id: int | None = None):
        return self.repository.list_logs(task_id)

    def resolve_and_import(
        self,
        pending_id: int,
        student_id: int | None = None,
        resolution_note: str = "人工确认后导入",
        confirm_possible_duplicate: bool = False,
    ) -> int | None:
        """人工确认单条待处理状态后写入正式考勤记录，并标记该待确认项已解决。"""
        with self.database.transaction() as connection:
            pending = self.repository.get_pending(pending_id, connection)
            if pending is None or pending["status"] != "待处理":
                raise PendingResolutionError("待确认记录不存在，或已经处理。")
            data = json.loads(pending["normalized_data"])
            entry_data = data.pop("attendance_entry", None)
            if not entry_data:
                raise PendingResolutionError("待确认记录缺少可导入的考勤状态。")
            if student_id is not None:
                student = self.master.students.get_by_id(student_id)
                if student is None:
                    raise PendingResolutionError("指定学生不存在。")
                data.update({"name": student.name, "student_number": student.student_number, "class_name": student.class_name})
            else:
                student_id = None
            entry = AttendanceEntry(**entry_data)
            record = ParsedRecord(int(pending["source_row_number"]), json.loads(pending["raw_data"]), data, student_id=student_id)
            values = self._attendance_values(int(pending["task_id"]), int(pending["source_file_id"]), record, entry)
            duplicate_kind = self.repository.find_record_duplicate(connection, values)
            if duplicate_kind == "EXACT_DUPLICATE":
                self.repository.resolve_pending(connection, pending_id, {
                    "action": "skipped_exact_duplicate", "note": resolution_note, "student_id": student_id,
                })
                return None
            if duplicate_kind == "POSSIBLE_DUPLICATE" and not confirm_possible_duplicate:
                raise PendingResolutionError("重新查重发现可能重复记录，请进行二次明确确认后再导入。")
            attendance_id = self.repository.create_attendance(connection, values)
            self.repository.resolve_pending(connection, pending_id, {
                "action": "imported_after_possible_duplicate_confirmation" if duplicate_kind else "imported",
                "note": resolution_note, "student_id": student_id, "attendance_record_id": attendance_id,
            })
            return attendance_id

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _json(data: object) -> str:
        return json.dumps(data, ensure_ascii=False, default=str, sort_keys=True)

    def _attendance_values(self, task_id: int, source_file_id: int, record: ParsedRecord, entry: AttendanceEntry) -> dict[str, object]:
        data = record.normalized_data
        return {
            "task_id": task_id, "source_file_id": source_file_id, "source_row_number": record.row_number,
            "date": data.get("date") or None, "attendance_type": entry.attendance_type, "student_id": record.student_id,
            "student_name": data.get("name", ""), "student_number": data.get("student_number", ""),
            "class_name": data.get("class_name", "") or None, "status": entry.status, "count": entry.count,
            "course": data.get("course") or None, "remark": data.get("remark") or None, "raw_data": self._json(record.raw_data),
        }

    def _pending_values(self, task_id: int, source_file_id: int, record: ParsedRecord, entry: AttendanceEntry, issue_type: str) -> dict[str, object]:
        normalized = dict(record.normalized_data)
        normalized["attendance_entry"] = {"status": entry.status, "count": entry.count, "attendance_type": entry.attendance_type}
        suggestion = "请选择正确学生后解决并导入" if record.match_status != "正常" else "请确认是否为重复记录后解决并导入"
        return {
            "task_id": task_id, "source_file_id": source_file_id, "source_row_number": record.row_number, "issue_type": issue_type,
            "raw_data": self._json(record.raw_data), "normalized_data": self._json(normalized), "suggestion": suggestion,
        }
