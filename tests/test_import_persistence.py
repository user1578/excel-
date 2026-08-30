"""正式导入、重复处理、待确认和文件回滚测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.class_record import ClassRecord
from app.models.parsed_record import ParsedRecord
from app.models.student import Student
from app.models.task import Task
from app.repositories.database import DatabaseManager
from app.services.attendance_transformer import AttendanceTransformer
from app.services.import_service import FileDuplicateError, ImportService
from app.services.master_data_service import MasterDataService
from app.services.task_service import TaskService


DATA = Path(__file__).parent / "data"


@pytest.fixture
def import_service(tmp_path):
    database = DatabaseManager(tmp_path / "data" / "database.db")
    database.initialize()
    master = MasterDataService(database)
    master.create_class(ClassRecord("物联网2401"))
    master.create_class(ClassRecord("软件2401"))
    master.create_student(Student("张三", "20260001", "物联网2401"))
    master.create_student(Student("李四", "20260002", "软件2401"))
    task = TaskService(database).create(Task("九月课堂考勤"))
    return ImportService(database, master, tmp_path / "imports"), task, database, master


def parsed(service: ImportService, source: Path, record_mode: str = "仅异常名单"):
    session = service.analyze(source)
    session.record_mode = record_mode
    return service.apply_mappings(session, service.default_mapping(session), save=False)


def test_transformer_splits_multiple_attendance_statuses():
    record = ParsedRecord(2, {}, {"late": "是", "absent": "2", "leave": "否", "status": "早退；旷课"})
    entries = AttendanceTransformer().transform(record)
    assert [(item.status, item.count) for item in entries] == [("迟到", 1), ("缺勤", 2), ("早退", 1), ("旷课", 1)]


def test_normal_status_requires_complete_attendance_mode():
    record = ParsedRecord(2, {}, {"name": "张三", "student_number": "20260001"})
    assert AttendanceTransformer().transform(record) == []
    assert [(item.status, item.count) for item in AttendanceTransformer().transform(record, complete_attendance=True)] == [("正常", 1)]


def test_import_persists_source_attendance_and_log(import_service):
    service, task, database, _master = import_service
    result = service.import_session(task.id, parsed(service, DATA / "normal.xlsx"))

    assert (result.success_count, result.pending_count, result.duplicate_count) == (1, 0, 0)
    with database.connection() as connection:
        source = connection.execute("SELECT * FROM source_files").fetchone()
        attendance = connection.execute("SELECT status, student_number FROM attendance_records").fetchone()
        log = connection.execute("SELECT success_count, pending_count FROM import_logs").fetchone()
    assert source["file_hash"] and Path(source["stored_path"]).exists()
    assert (attendance["status"], attendance["student_number"]) == ("迟到", "20260001")
    assert tuple(log) == (1, 0)


def test_source_hash_duplicate_and_record_duplicate_become_safe_pending(import_service, tmp_path):
    service, task, database, _master = import_service
    service.import_session(task.id, parsed(service, DATA / "normal.xlsx"))
    with pytest.raises(FileDuplicateError):
        service.import_session(task.id, parsed(service, DATA / "normal.xlsx"))

    alternate = tmp_path / "same-record.csv"
    alternate.write_text("姓名,学号,班级,迟到\n张三,20260001,物联网2401,是\n", encoding="utf-8-sig")
    result = service.import_session(task.id, parsed(service, alternate))
    assert (result.success_count, result.pending_count, result.duplicate_count) == (0, 1, 1)
    assert service.list_pending(task.id)[0]["issue_type"] == "POSSIBLE_DUPLICATE"
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM attendance_records").fetchone()[0] == 1


def test_exact_duplicate_requires_date_or_course_anchor(import_service, tmp_path):
    service, task, database, _master = import_service
    first = tmp_path / "dated-first.csv"
    second = tmp_path / "dated-second.csv"
    first.write_text("姓名,学号,班级,日期,课程,迟到\n张三,20260001,物联网2401,2026-09-01,Python,是\n", encoding="utf-8-sig")
    second.write_text("姓名,学号,班级,日期,课程,迟到,说明\n张三,20260001,物联网2401,2026-09-01,Python,是,另一来源文件\n", encoding="utf-8-sig")
    service.import_session(task.id, parsed(service, first))
    result = service.import_session(task.id, parsed(service, second))
    assert (result.success_count, result.pending_count, result.duplicate_count, result.exact_duplicate_skip_count) == (0, 0, 1, 1)
    assert service.list_pending(task.id) == []
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM attendance_records").fetchone()[0] == 1
        log = connection.execute("SELECT duplicate_count, pending_count, message FROM import_logs ORDER BY id DESC").fetchone()
    assert tuple(log) == (1, 0, "导入完成；完全重复跳过 1 条")


def test_possible_duplicate_is_not_auto_imported(import_service):
    service, task, database, _master = import_service
    with database.transaction() as connection:
        source_id = connection.execute(
            """INSERT INTO source_files (task_id, original_name, original_path, stored_path, file_type, file_size, file_hash, record_count, status)
            VALUES (?, 'old.csv', 'old.csv', 'old.csv', 'csv', 1, 'old-hash', 1, '已导入')""", (task.id,)
        ).lastrowid
        connection.execute(
            """INSERT INTO attendance_records
            (task_id, source_file_id, source_row_number, attendance_type, student_name, student_number, status, raw_data)
            VALUES (?, ?, 2, '课堂考勤', '张三', '20260001', '迟到', '{}')""", (task.id, source_id)
        )
    result = service.import_session(task.id, parsed(service, DATA / "normal.xlsx"))
    assert (result.success_count, result.pending_count, result.duplicate_count) == (0, 1, 1)
    assert service.list_pending(task.id)[0]["issue_type"] == "POSSIBLE_DUPLICATE"


def test_pending_can_be_resolved_and_imported(import_service):
    service, task, database, master = import_service
    result = service.import_session(task.id, parsed(service, DATA / "conflict.xlsx", "完整考勤名单"))
    assert (result.success_count, result.pending_count, result.conflict_count) == (0, 1, 1)

    pending = service.list_pending(task.id)[0]
    attendance_id = service.resolve_and_import(pending["id"], master.get_student_by_number("20260001").id)
    with database.connection() as connection:
        status = connection.execute("SELECT status, student_id FROM attendance_records WHERE id = ?", (attendance_id,)).fetchone()
        resolved = connection.execute("SELECT status FROM pending_records WHERE id = ?", (pending["id"],)).fetchone()[0]
    assert tuple(status) == ("正常", master.get_student_by_number("20260001").id)
    assert resolved == "已解决"


def test_database_failure_cleans_the_new_import_copy(import_service):
    service, task, database, _master = import_service
    with database.transaction() as connection:
        connection.execute("""CREATE TRIGGER reject_attendance BEFORE INSERT ON attendance_records
        BEGIN SELECT RAISE(ABORT, '模拟数据库失败'); END""")
    with pytest.raises(Exception, match="模拟数据库失败"):
        service.import_session(task.id, parsed(service, DATA / "normal.xlsx"))
    assert not list(service.imports_directory.glob("*"))
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM attendance_records").fetchone()[0] == 0
