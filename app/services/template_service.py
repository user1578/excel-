"""模板管理与基础数据下拉选项的服务层。"""

from __future__ import annotations

from pathlib import Path

from app.services.master_data_service import MasterDataService
from app.template_engine.template_manager import TemplateArtifact, TemplateManager
from app.template_engine.schema import TemplateSchema


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
