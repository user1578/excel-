"""V2 数据安全修复的回归测试；所有数据均为虚构数据。"""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from app.models.class_record import ClassRecord
from app.models.parsed_record import ParsedRecord
from app.models.student import Student
from app.models.task import Task
from app.repositories.database import DatabaseManager
from app.services.attendance_transformer import AttendanceTransformer
from app.services.import_service import ImportService, PendingResolutionError
from app.services.master_data_service import MasterDataService
from app.services.statistics_service import AttendanceQuery, StatisticsService
from app.services.task_service import TaskService
from app.utils.excel_safety import safe_excel_value
from app.utils.value_normalizer import normalize_date


@pytest.fixture
def imported_service(tmp_path):
    database = DatabaseManager(tmp_path / "test.db")
    database.initialize()
    master = MasterDataService(database)
    master.create_class(ClassRecord("测试班2401"))
    student = master.create_student(Student("测试学生甲", "20260001", "测试班2401"))
    task = TaskService(database).create(Task("虚构考勤任务"))
    service = ImportService(database, master, tmp_path / "imports")
    return service, database, task, student


@pytest.mark.parametrize("value, expected", [
    (datetime(2026, 9, 30, 8, 5), "2026-09-30"),
    (date(2026, 9, 30), "2026-09-30"),
    ("2026/9/30", "2026-09-30"),
    ("2026.9.30", "2026-09-30"),
    ("2026年9月30日", "2026-09-30"),
    ("2026-09-30 00:00:00", "2026-09-30"),
    ("20260930", "20260930"),
    ("not a date", "not a date"),
])
def test_normalize_date_is_conservative(value, expected):
    assert normalize_date(value) == expected


def _source_and_pending(database, task, *, data, issue_type="学生信息冲突"):
    with database.transaction() as connection:
        source_id = connection.execute(
            """INSERT INTO source_files (task_id, original_name, original_path, stored_path, file_type, file_size, file_hash, record_count, status)
            VALUES (?, '虚构.csv', '虚构.csv', '虚构.csv', 'csv', 1, 'v2-safety', 1, '已导入')""",
            (task.id,),
        ).lastrowid
        pending_id = connection.execute(
            """INSERT INTO pending_records
            (task_id, source_file_id, source_row_number, issue_type, raw_data, normalized_data, suggestion)
            VALUES (?, ?, 2, ?, '{}', ?, '请选择正确学生')""",
            (task.id, source_id, issue_type, json.dumps(data, ensure_ascii=False)),
        ).lastrowid
    return int(source_id), int(pending_id)


def _attendance(connection, task_id, source_id, student_id, *, number="20260001"):
    connection.execute(
        """INSERT INTO attendance_records
        (task_id, source_file_id, source_row_number, date, attendance_type, student_id, student_name,
         student_number, class_name, status, count, course, raw_data)
        VALUES (?, ?, 3, '2026-09-30', '课堂考勤', ?, '测试学生甲', ?, '测试班2401', '迟到', 1, 'Python', '{}')""",
        (task_id, source_id, student_id, number),
    )


def test_pending_resolution_rechecks_exact_duplicate(imported_service):
    service, database, task, student = imported_service
    data = {"date": "2026-09-30", "course": "Python", "attendance_entry": {"status": "迟到", "count": 1, "attendance_type": "课堂考勤"}}
    source_id, pending_id = _source_and_pending(database, task, data=data)
    with database.transaction() as connection:
        _attendance(connection, task.id, source_id, student.id)

    assert service.resolve_and_import(pending_id, student.id) is None
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM attendance_records").fetchone()[0] == 1
        resolution = json.loads(connection.execute("SELECT resolution FROM pending_records WHERE id = ?", (pending_id,)).fetchone()[0])
    assert resolution["action"] == "skipped_exact_duplicate"


def test_pending_resolution_requires_second_confirmation_for_possible_duplicate(imported_service):
    service, database, task, student = imported_service
    data = {"date": "2026-09-30", "course": "Python", "attendance_entry": {"status": "迟到", "count": 1, "attendance_type": "课堂考勤"}}
    source_id, pending_id = _source_and_pending(database, task, data=data)
    with database.transaction() as connection:
        _attendance(connection, task.id, source_id, None)

    with pytest.raises(PendingResolutionError, match="二次明确确认"):
        service.resolve_and_import(pending_id, student.id)
    with database.connection() as connection:
        assert connection.execute("SELECT status FROM pending_records WHERE id = ?", (pending_id,)).fetchone()[0] == "待处理"
    attendance_id = service.resolve_and_import(pending_id, student.id, confirm_possible_duplicate=True)
    assert attendance_id is not None


def test_status_split_uses_actual_newlines_without_splitting_n():
    entries = AttendanceTransformer().transform(ParsedRecord(2, {}, {"status": "normal\n早退\r\n旷课、请假,迟到；缺勤/病假"}))
    assert [item.status for item in entries] == ["normal", "早退", "旷课", "请假", "迟到", "缺勤", "病假"]


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-123abc", "@SUM(A1:A2)", "\tcmd", "\rcmd"])
def test_safe_excel_value_escapes_user_formula_prefixes(value):
    assert safe_excel_value(value) == "'" + value


def test_date_range_includes_normalized_imported_boundary(imported_service, tmp_path):
    service, database, task, _student = imported_service
    source = tmp_path / "日期格式.csv"
    source.write_text("姓名,学号,班级,日期,迟到\n测试学生甲,20260001,测试班2401,2026/9/30,是\n", encoding="utf-8-sig")
    session = service.analyze(source)
    session.record_mode = "仅异常名单"
    service.apply_mappings(session, service.default_mapping(session), save=False)
    service.import_session(task.id, session)

    with database.connection() as connection:
        assert connection.execute("SELECT date FROM attendance_records").fetchone()[0] == "2026-09-30"
    assert StatisticsService(database).summarize(AttendanceQuery(start_date="2026-09-30", end_date="2026-09-30")).overview["record_count"] == 1
