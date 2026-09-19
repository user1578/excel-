"""不依赖 GUI 自动化框架的基础界面冒烟测试。"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app.models.class_record import ClassRecord
from app.models.dormitory import Dormitory
from app.models.student import Student
from app.models.task import Task
from app.models.merge_models import ConflictResolution
from app.models.table_dataset import Provenance, TableDataset, TableRow
from app.repositories.database import DatabaseManager
from app.services.dataset_merge_service import DatasetMergeService
from app.services.master_data_service import MasterDataService
from app.ui.main_window import MainWindow
from app.ui.dialogs.class_students_dialog import ClassExportDialog, ClassStudentsDialog
from app.ui.merge_page import MergePage, SourceSelection
from app.services.data_workspace_service import DataWorkspaceService


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
        "home", "tasks", "imports", "pending", "students", "classes", "dormitories", "merge", "workbook_fill",
        "statistics", "templates", "history", "settings",
    ):
        window.navigate(page_key)
        application.processEvents()
        assert window.content_stack.currentWidget() is not None
        assert window._nav_buttons[page_key].isChecked()

    window.close()


def test_conflict_resolution_refreshes_workspace_used_by_workbook_fill_page(application, tmp_path):
    database = DatabaseManager(tmp_path / "workspace-smoke.db")
    database.initialize()
    window = MainWindow(MasterDataService(database))
    first = TableDataset(["name", "student_number", "phone"], [
        TableRow({"name": "测试学生甲", "student_number": "20260001", "phone": "13800000001"}, Provenance("A.xlsx", "资料", 2)),
    ], "A.xlsx", "资料", 1, column_labels={"name": "姓名", "student_number": "学号", "phone": "电话"})
    second = TableDataset(["name", "student_number", "phone"], [
        TableRow({"name": "测试学生甲", "student_number": "20260001", "phone": "13900000001"}, Provenance("B.xlsx", "资料", 2)),
    ], "B.xlsx", "资料", 1, column_labels={"name": "姓名", "student_number": "学号", "phone": "电话"})
    result = DatasetMergeService().merge_by_student([first, second])
    window.merge_page.result = result
    window.merge_page.workspace.set_merge_result(result)
    window.merge_page._render_result()
    window.merge_page.conflicts.setCurrentCell(0, 0)
    window.merge_page.resolve_selected(ConflictResolution.USE_B)
    window.workbook_fill_page.choose_source()
    assert window.data_workspace.current_dataset.rows[0].values["phone"] == "13900000001"
    assert window.workbook_fill_page.dataset.rows[0].values["phone"] == "13900000001"
    window.close()


def _merge_page_with_result(application):
    first = TableDataset(["name", "student_number", "class_name", "phone"], [
        TableRow({"name": "测试学生甲", "student_number": "20260001", "class_name": "测试班2401", "phone": "13800000001"}, Provenance("基础.xlsx", "资料", 2)),
        TableRow({"name": "测试学生乙", "student_number": "", "class_name": "测试班2401", "phone": ""}, Provenance("基础.xlsx", "资料", 3)),
    ], "基础.xlsx", "资料", 1, column_labels={"name": "姓名", "student_number": "学号", "class_name": "班级", "phone": "电话"})
    second = TableDataset(["name", "student_number", "class_name", "phone"], [
        TableRow({"name": "测试学生甲", "student_number": "20260001", "class_name": "测试班2401", "phone": "13900000001"}, Provenance("补充.xlsx", "资料", 2)),
        TableRow({"name": "测试学生丙", "student_number": "", "class_name": "测试班2401", "phone": ""}, Provenance("补充.xlsx", "资料", 3)),
    ], "补充.xlsx", "资料", 1, column_labels={"name": "姓名", "student_number": "学号", "class_name": "班级", "phone": "电话"})
    result = DatasetMergeService().merge_by_student([first, second])
    workspace = DataWorkspaceService()
    page = MergePage(workspace)
    page.sources = [
        SourceSelection(Path("基础.xlsx"), "资料", dataset=first),
        SourceSelection(Path("补充.xlsx"), "资料", dataset=second),
    ]
    page.result = result
    workspace.set_merge_result(result)
    page._render_result()
    return page, result, workspace


def test_merge_export_cancel_does_not_call_service(application, monkeypatch):
    page, _result, _workspace = _merge_page_with_result(application)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: ("", ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(page.export_service, "export", lambda *_args, **_kwargs: pytest.fail("取消时不得调用导出服务"))

    page.export_result()

    page.close()


def test_merge_export_passes_user_selected_path(application, monkeypatch, tmp_path):
    page, _result, _workspace = _merge_page_with_result(application)
    target = tmp_path / "用户选择" / "汇总.xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: (str(target), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *_: None)

    def export(_result, output_path, allow_unresolved=False):
        assert output_path == target
        assert allow_unresolved is True
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fake workbook")
        return target

    monkeypatch.setattr(page.export_service, "export", export)
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    page.export_result()

    assert target.exists()
    page.close()


def test_merge_page_filters_rendered_rows_and_summary_without_mutating_result(application):
    page, result, workspace = _merge_page_with_result(application)
    assert hasattr(page, "filter_box")
    assert page.preview.rowCount() == 3
    assert page.summary_values["source_files"].text() == "2"
    assert page.summary_values["raw_rows"].text() == "4"
    assert page.summary_values["matched"].text() == "1"
    assert page.summary_values["unmatched"].text() == "2"
    assert page.summary_values["conflicts"].text() == "1"
    assert page.summary_values["missing"].text() == "2"

    original_rows = [dict(record.values) for record in result.records]
    for key, expected_rows in (("conflicts", 1), ("missing", 2), ("unmatched", 2), ("all", 3)):
        page.filter_box.setCurrentIndex(page.filter_box.findData(key))
        assert page.preview.rowCount() == expected_rows
        assert [dict(record.values) for record in result.records] == original_rows
        assert workspace.current_merge_result is result
    page.close()


def test_v21_student_and_class_export_dialogs_smoke(application, tmp_path):
    database = DatabaseManager(tmp_path / "v21-dialogs.db")
    database.initialize()
    service = MasterDataService(database)
    class_record = service.create_class(ClassRecord("测试班2401"))
    student = service.create_student(Student("测试学生甲", "20260001", "测试班2401"))
    service.set_student_extra_field(student.id, "性别", "测试性别")
    students_dialog = ClassStudentsDialog(service, class_record)
    export_dialog = ClassExportDialog(service, class_record.standard_name, [student])
    assert students_dialog.table.rowCount() == 1
    assert export_dialog.table.rowCount() >= 1
    students_dialog.close(); export_dialog.close()


def test_class_student_selection_survives_filtering_and_export_rows_are_dynamic(application, tmp_path):
    database = DatabaseManager(tmp_path / "v211-dialogs.db")
    database.initialize()
    service = MasterDataService(database)
    class_record = service.create_class(ClassRecord("测试班2401"))
    first = service.create_student(Student("测试学生甲", "20260001", "测试班2401"))
    second = service.create_student(Student("测试学生乙", "20260002", "测试班2401"))
    students_dialog = ClassStudentsDialog(service, class_record)
    students_dialog.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    students_dialog.search.setText("乙")
    students_dialog.search.clear()
    assert [item.id for item in students_dialog.selected_students()] == [second.id]
    export_dialog = ClassExportDialog(service, class_record.standard_name, [first, second])
    original = [item.title for item in export_dialog.columns()]
    export_dialog._move_action_row(export_dialog.table.cellWidget(4, 5), -1)
    export_dialog._move_action_row(export_dialog.table.cellWidget(0, 5), 1)
    export_dialog._remove_action_row(export_dialog.table.cellWidget(2, 5))
    assert len(export_dialog.columns()) == len(original) - 1 and len({item.title for item in export_dialog.columns()}) == len(export_dialog.columns())
    students_dialog.close(); export_dialog.close()
