"""模板页预填与学生选择的离屏测试。"""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.models.class_record import ClassRecord
from app.models.student import Student
from app.repositories.database import DatabaseManager
from app.services.master_data_service import MasterDataService
from app.services.template_service import TemplateService
from app.template_engine.schema import FieldSchema, SheetSchema, TemplateSchema
from app.ui.dialogs.student_selection_dialog import StudentSelectionDialog
from app.ui.template_page import TemplatePage


class Parser:
    def generate_schema(self, _text):
        raise AssertionError("本测试不调用 AI")


@pytest.fixture
def page_setup(tmp_path):
    application = QApplication.instance() or QApplication([])
    database = DatabaseManager(tmp_path / "templates.db")
    database.initialize()
    master = MasterDataService(database)
    master.create_class(ClassRecord("软件2401", major="软件工程", grade="2024"))
    first = master.create_student(Student("测试学生甲", "20260001", "软件2401", major="软件工程", grade="2024", phone="13800000001", dormitory="南3-402"))
    second = master.create_student(Student("测试学生乙", "20260002", "软件2401", major="软件工程", grade="2024", phone="13800000002", dormitory="南3-403"))
    service = TemplateService(master, tmp_path / "templates")
    page = TemplatePage(service, Parser())
    yield application, page, service, first, second
    page.close()


def schema_with(*fields: str) -> TemplateSchema:
    mapping = {
        "姓名": "name", "学号": "student_number", "班级": "class_name", "专业": "major",
        "年级": "grade", "电话": "phone", "寝室": "dormitory",
    }
    return TemplateSchema("预填表", sheets=[SheetSchema("录入", [FieldSchema(label, standard_field=mapping[label]) for label in fields])])


def test_template_page_has_scrollable_style_panel_and_collapsed_ai(page_setup):
    _application, page, _service, _first, _second = page_setup

    assert page.scroll_area.widget() is not None
    assert page.style_preview.rowCount() == 2
    assert page.ai_toggle.isChecked() is False


def test_selected_students_prefill_only_declared_fields(page_setup):
    _application, page, _service, student, _second = page_setup
    page.set_generation_mode("selected")
    page.set_selected_students([student])

    rows = page.prefill_rows(schema_with("姓名", "学号"))

    assert rows == [{"name": student.name, "student_number": student.student_number}]


def test_class_prefill_includes_only_declared_student_attributes(page_setup):
    _application, _page, service, first, second = page_setup
    schema = schema_with("姓名", "学号", "班级", "专业", "年级", "电话", "寝室")

    rows = service.prefill_rows(schema, "class", class_name="软件2401")

    assert rows == [
        {"name": first.name, "student_number": first.student_number, "class_name": first.class_name, "major": first.major, "grade": first.grade, "phone": first.phone, "dormitory": first.dormitory},
        {"name": second.name, "student_number": second.student_number, "class_name": second.class_name, "major": second.major, "grade": second.grade, "phone": second.phone, "dormitory": second.dormitory},
    ]


def test_student_selection_searches_and_preserves_multiple_checked_students(page_setup):
    application, _page, service, first, second = page_setup
    dialog = StudentSelectionDialog(service.master)
    dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    dialog.search.setText(second.student_number)
    application.processEvents()
    dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    dialog.search.clear()
    application.processEvents()

    assert [student.id for student in dialog.selected_students()] == [first.id, second.id]
    dialog.close()


def test_template_save_cancel_does_not_call_generator(page_setup, monkeypatch):
    _application, page, service, _first, _second = page_setup
    page.name.setText("取消保存")
    page.fields = [FieldSchema("事项")]
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: ("", ""))
    monkeypatch.setattr(service, "generate", lambda *_args, **_kwargs: pytest.fail("取消时不得生成模板"))

    page.generate_template()

    assert service.list() == []
