"""当前导入会话的内存状态。"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import pandas as pd
from app.models.field_mapping import DetectedField, StandardField
from app.models.parsed_record import ParsedRecord

@dataclass
class ImportSession:
    file_path: Path
    sheet_name: str | None
    raw_frame: pd.DataFrame
    header_row: int
    header_score: int
    header_reason: str
    fields: list[DetectedField] = field(default_factory=list)
    records: list[ParsedRecord] = field(default_factory=list)
    record_mode: str = "仅异常名单"
    error: str | None = None

    @property
    def headers(self) -> list[str]:
        return [str(value).strip() if value is not None else "" for value in self.raw_frame.iloc[self.header_row].tolist()]

    @property
    def total_rows(self) -> int: return max(0, len(self.raw_frame) - self.header_row - 1)
