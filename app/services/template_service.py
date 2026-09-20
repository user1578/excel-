"""模板管理与基础数据下拉选项的服务层。"""

from __future__ import annotations

from pathlib import Path

from app.services.master_data_service import MasterDataService
from app.template_engine.template_manager import TemplateArtifact, TemplateManager
from app.template_engine.schema import FieldSchema, TemplateSchema


class TemplateService:
    def __init__(self, master: MasterDataService, templates_directory: str | Path | None = None) -> None:
        self.master = master
        self.manager = TemplateManager(templates_directory or Path(__file__).resolve().parents[2] / "templates")

    def create(self, schema: TemplateSchema) -> TemplateArtifact:
        return self.manager.create(schema, [item.standard_name for item in self.master.list_classes()], [item.standard_name for item in self.master.list_dormitories()])

    def list(self) -> list[TemplateArtifact]:
        return self.manager.list()

    def load(self, name: str) -> TemplateSchema:
        return self.manager.load(name)

    def copy(self, name: str) -> TemplateArtifact:
        return self.manager.copy(name)

    def delete(self, name: str) -> None:
        self.manager.delete(name)

    def generate(self, schema: TemplateSchema, output_path: str | Path, prefill_rows: list[dict[str, object]] | None = None) -> Path:
        """保留内部可管理模板，并向用户选择的位置另存预填副本。"""
        self.create(schema)
        return self.manager.generator.generate(
            schema,
            Path(output_path),
            [item.standard_name for item in self.master.list_classes()],
            [item.standard_name for item in self.master.list_dormitories()],
            prefill_rows,
        )

    def prefill_rows(self, schema: TemplateSchema, mode: str, class_name: str | None = None, student_ids: list[int] | None = None) -> list[dict[str, object]]:
        if mode == "blank":
            return []
        if mode == "class":
            if not class_name:
                raise ValueError("请先选择要预填的班级。")
            students = self.master.list_students_by_class(class_name)
        elif mode == "selected":
            by_id = {student.id: student for student in self.master.list_students()}
            students = [by_id[student_id] for student_id in student_ids or [] if student_id in by_id]
        else:
            raise ValueError("预填方式仅支持 blank、class 或 selected。")
        return [self._student_prefill_row(schema, student) for student in students]

    @staticmethod
    def _student_prefill_row(schema: TemplateSchema, student) -> dict[str, object]:
        values = {
            "name": student.name,
            "student_number": student.student_number,
            "class_name": student.class_name,
            "major": student.major or "",
            "grade": student.grade or "",
            "phone": student.phone or "",
            "dormitory": student.dormitory or "",
        }
        allowed = {TemplateService._field_key(field) for field in schema.sheets[0].fields}
        return {key: value for key, value in values.items() if key in allowed}

    @staticmethod
    def _field_key(field: FieldSchema) -> str | None:
        if field.standard_field in {"name", "student_number", "class_name", "major", "grade", "phone", "dormitory"}:
            return field.standard_field
        if field.field_type in {"name", "student_number", "class_name", "dormitory"}:
            return field.field_type
        return {
            "姓名": "name", "学号": "student_number", "班级": "class_name", "专业": "major",
            "年级": "grade", "联系电话": "phone", "电话": "phone", "寝室": "dormitory",
        }.get(field.name)
