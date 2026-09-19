"""日期规范化只在来源提供可靠语义时转换 Excel 序列值。"""

from __future__ import annotations

from datetime import date, datetime
from importlib import import_module

import pandas as pd
import pytest
from openpyxl import Workbook

from app.models.class_record import ClassRecord
from app.models.student import Student
from app.models.task import Task
from app.repositories.database import DatabaseManager
from app.services.import_service import ImportService
from app.services.master_data_service import MasterDataService
from app.services.task_service import TaskService
from app.utils.value_normalizer import normalize_date


def _assert_normalization(result, value: str, is_valid: bool, reason: str | None = None) -> None:
    module = import_module("app.utils.value_normalizer")
    assert hasattr(module, "DateNormalization")
    assert isinstance(result, module.DateNormalization)
    assert (result.value, result.is_valid, result.reason) == (value, is_valid, reason)


@pytest.fixture
def imported_service(tmp_path):
    database = DatabaseManager(tmp_path / "test.db")
    database.initialize()
    master = MasterDataService(database)
    master.create_class(ClassRecord("测试班2401"))
    student = master.create_student(Student("测试学生甲", "20260001", "测试班2401"))
    task = TaskService(database).create(Task("虚构考勤任务"))
    return ImportService(database, master, tmp_path / "imports"), database, task, student


def test_numeric_value_is_not_a_date_without_excel_context():
    _assert_normalization(normalize_date(45200), "45200", False, "missing_date_semantics")


def test_serial_date_requires_epoch_and_date_semantics():
    try:
        result = normalize_date(
            45200,
            date_semantic=True,
            excel_epoch=datetime(1899, 12, 30),
        )
    except TypeError as error:
        pytest.fail(f"normalize_date must accept Excel 日期上下文：{error}")
    _assert_normalization(result, "2023-10-01", True)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 2, 28, 8, 5), "2026-02-28"),
        (date(2026, 2, 28), "2026-02-28"),
        (pd.Timestamp("2026-02-28 08:05:00"), "2026-02-28"),
        ("2026-02-28", "2026-02-28"),
        ("2026/2/28", "2026-02-28"),
        ("2026.2.28", "2026-02-28"),
    ],
)
def test_known_date_values_normalize_to_their_month_end(value, expected):
    _assert_normalization(normalize_date(value), expected, True)


def test_xlsx_date_number_format_supplies_session_context(tmp_path, imported_service):
    workbook_path = tmp_path / "虚构日期格式.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["姓名", "学号", "班级", "日期", "迟到"])
    sheet.append(["测试学生甲", "20260001", "测试班2401", 45200, "是"])
    sheet["D2"].number_format = "yyyy-mm-dd"
    workbook.save(workbook_path)

    service, _database, _task, _student = imported_service
    session = service.analyze(workbook_path)

    assert hasattr(session, "date_context")
    context = session.date_context[(1, 3)]
    assert context.date_semantic is True
    assert context.excel_epoch is not None
    service.apply_mappings(session, service.default_mapping(session), save=False)
    assert session.records[0].normalized_data["date"] == "2023-10-01"
