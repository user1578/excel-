"""跨文件表格的内存数据模型，保留字段和来源追溯信息。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Provenance:
    source_file: str
    source_sheet: str | None
    source_row: int


@dataclass
class TableRow:
    values: dict[str, Any]
    provenance: Provenance


@dataclass
class TableDataset:
    """经分析的一张表；键是标准字段或稳定的自定义字段键。"""

    columns: list[str]
    rows: list[TableRow]
    source_file: str
    source_sheet: str | None
    detected_header: int
    field_mappings: dict[str, str] = field(default_factory=dict)
    column_labels: dict[str, str] = field(default_factory=dict)
    custom_fields: set[str] = field(default_factory=set)

    def display_label(self, key: str) -> str:
        return self.column_labels.get(key, key)

    def value_columns(self) -> list[tuple[str, str]]:
        return [(key, self.display_label(key)) for key in self.columns]
