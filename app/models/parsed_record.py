"""标准化的导入预览记录。"""
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ParsedRecord:
    row_number: int
    raw_data: dict[str, Any]
    normalized_data: dict[str, Any]
    field_sources: dict[str, str] = field(default_factory=dict)
    student_id: int | None = None
    match_status: str = "待确认"
    issues: list[str] = field(default_factory=list)
    source_file: str = ""
    sheet_name: str | None = None
