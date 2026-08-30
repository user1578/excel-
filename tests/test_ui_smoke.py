"""不依赖 GUI 自动化框架的基础界面冒烟测试。"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.models.class_record import ClassRecord
from app.models.dormitory import Dormitory
from app.models.student import Student
from app.models.task import Task
from app.repositories.database import DatabaseManager
from app.services.master_data_service import MasterDataService
from app.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def application():
    return QApplication.instance() or QApplication([])


def test_main_window_home_and_student_table_smoke(application, tmp_path):
    database = DatabaseManager(tmp_path / "ui-smoke.db")
    database.initialize()
    service = MasterDataService(database)
    service.create_class(ClassRecord("物联网2401"))
    service.create_dormitory(Dormitory("南3", "402", "南3-402"))
    service.create_student(Student("张三", "20260001", "物联网2401", dormitory="南3-402"))

    window = MainWindow(service)
    window.show()
    application.processEvents()
    window.navigate("students")

    assert window.isVisible()
    assert window.windowTitle() == "Excel资料整理助手"
    assert window.student_page.table.rowCount() == 1
    window.navigate("home")
    assert window.home_page._stat_values["students"].text() == "1"
    assert window.home_page._stat_values["classes"].text() == "1"
    assert window.home_page._stat_values["dormitories"].text() == "1"
    window.task_service.create(Task("九月课堂考勤"))
    window.navigate("tasks")
    assert window.task_page.table.rowCount() == 1
    window.import_page.refresh_tasks()
    assert window.import_page.task_box.currentData() is not None
    assert window.import_page.record_mode_box.currentText() == "仅异常名单"
    window.import_page.open_file(str(Path(__file__).parent / "data" / "normal.xlsx"))
    assert window.import_page.session is not None
    window.import_page.confirm()
    assert window.import_page.preview_table.rowCount() == 1
    window.navigate("history")
    assert window.history_page.table.rowCount() == 0
    window.close()


def test_all_navigation_pages_open_smoke(application, tmp_path):
    database = DatabaseManager(tmp_path / "navigation-smoke.db")
    database.initialize()
    window = MainWindow(MasterDataService(database))
    window.show()

    for page_key in (
        "home", "tasks", "imports", "pending", "students", "classes", "dormitories",
        "statistics", "templates", "history", "settings",
    ):
        window.navigate(page_key)
        application.processEvents()
        assert window.content_stack.currentWidget() is not None
        assert window._nav_buttons[page_key].isChecked()

    window.close()
