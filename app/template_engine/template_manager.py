"""模板工作簿及 schema.json 的本地文件管理。"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.template_engine.generator import TemplateGenerator
from app.template_engine.schema import TemplateSchema


@dataclass(frozen=True)
class TemplateArtifact:
    name: str
    directory: Path
    workbook_path: Path
    schema_path: Path


class TemplateManager:
    def __init__(self, templates_directory: str | Path, generator: TemplateGenerator | None = None) -> None:
        self.templates_directory = Path(templates_directory)
        self.generator = generator or TemplateGenerator()

    def create(self, schema: TemplateSchema, classes: list[str], dormitories: list[str]) -> TemplateArtifact:
        schema.validate()
        directory = self._unique_directory(schema.template_name)
        directory.mkdir(parents=True, exist_ok=False)
        try:
            workbook_path = directory / f"{self._safe_name(schema.template_name)}.xlsx"
            self.generator.generate(schema, workbook_path, classes, dormitories)
            schema_path = directory / "schema.json"
            schema_path.write_text(schema.to_json(), encoding="utf-8")
            return TemplateArtifact(directory.name, directory, workbook_path, schema_path)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def list(self) -> list[TemplateArtifact]:
        if not self.templates_directory.exists():
            return []
        artifacts = []
        for directory in sorted(path for path in self.templates_directory.iterdir() if path.is_dir()):
            schema_path = directory / "schema.json"
            workbooks = list(directory.glob("*.xlsx"))
            if schema_path.exists() and workbooks:
                artifacts.append(TemplateArtifact(directory.name, directory, workbooks[0], schema_path))
        return artifacts

    def load(self, name: str) -> TemplateSchema:
        artifact = self._artifact(name)
        return TemplateSchema.from_json(artifact.schema_path.read_text(encoding="utf-8"))

    def copy(self, name: str) -> TemplateArtifact:
        source = self._artifact(name)
        destination = self._unique_directory(f"{source.name}_副本")
        shutil.copytree(source.directory, destination)
        workbook = next(destination.glob("*.xlsx"))
        return TemplateArtifact(destination.name, destination, workbook, destination / "schema.json")

    def delete(self, name: str) -> None:
        shutil.rmtree(self._artifact(name).directory)

    def _artifact(self, name: str) -> TemplateArtifact:
        for artifact in self.list():
            if artifact.name == name:
                return artifact
        raise ValueError("模板不存在。")

    def _unique_directory(self, template_name: str) -> Path:
        self.templates_directory.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_name(template_name)
        candidate = self.templates_directory / safe_name
        if not candidate.exists():
            return candidate
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = self.templates_directory / f"{safe_name}_{timestamp}"
        suffix = 2
        while candidate.exists():
            candidate = self.templates_directory / f"{safe_name}_{timestamp}_{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = "".join("_" if character in '\\/:*?\"<>|' else character for character in value).strip().strip(".")
        return cleaned or "未命名模板"
