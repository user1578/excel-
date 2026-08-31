"""工作簿模板分析、映射和填充结果模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TemplateAnalysis:
    template_path: Path
    sheet_name: str
    header_row: int
    target_columns: dict[str, int]
    merged_non_anchor_columns: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class FillPreview:
    row_count: int
    mappings: dict[str, str]
    existing_value_conflicts: int
    merged_cell_warnings: list[str]


@dataclass(frozen=True)
class FillResult:
    output_path: Path
    written_rows: int
    skipped_rows: int
    preserved_cells: int
