"""将 xlsx/csv 工作表分析为可安全合并的 TableDataset。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.models.field_mapping import StandardField
from app.models.table_dataset import Provenance, TableDataset, TableRow
from app.parsers.excel_reader import list_sheets, read_raw
from app.parsers.field_detector import detect_field
from app.parsers.header_detector import detect_header
from app.utils.value_normalizer import normalize_column_name, normalize_date, normalize_text


class TableAnalysisService:
    def sheets(self, path: str | Path) -> list[str | None]:
        source = Path(path)
        return list_sheets(source) if source.suffix.lower() == ".xlsx" else [None]

    def analyze(self, path: str | Path, sheet_name: str | None = None, header_row: int | None = None) -> TableDataset:
        source = Path(path)
        frame = read_raw(source, sheet_name)
        detected_index = detect_header(frame)[0] if header_row is None else header_row - 1
        if detected_index < 0 or detected_index >= len(frame):
            raise ValueError("表头行不在工作表范围内。")
        headers = [normalize_text(value) for value in frame.iloc[detected_index].tolist()]
        if not any(headers):
            raise ValueError("表头行没有可用字段。")

        columns: list[str] = []
        labels: dict[str, str] = {}
        mappings: dict[str, str] = {}
        custom_fields: set[str] = set()
        indexed_keys: dict[int, str] = {}
        used: set[str] = set()
        for index, header in enumerate(headers):
            if not header:
                continue
            detected = detect_field(index, header, frame.iloc[detected_index + 1:, index])
            key = self._field_key(header, detected.detected_field, used)
            used.add(key)
            columns.append(key)
            labels[key] = header
            mappings[header] = key
            indexed_keys[index] = key
            if detected.detected_field is StandardField.OTHER:
                custom_fields.add(key)

        rows: list[TableRow] = []
        for offset, row in enumerate(frame.iloc[detected_index + 1:].itertuples(index=False, name=None), start=detected_index + 2):
            values: dict[str, str] = {}
            for index, key in indexed_keys.items():
                value = row[index] if index < len(row) else None
                values[key] = normalize_date(value) if key == StandardField.DATE.value else normalize_text(value)
            if any(values.values()):
                rows.append(TableRow(values, Provenance(source.name, sheet_name, offset)))
        return TableDataset(columns, rows, source.name, sheet_name, detected_index + 1, mappings, labels, custom_fields)

    def analyze_all_sheets(self, path: str | Path, header_rows: dict[str | None, int] | None = None) -> list[TableDataset]:
        source = Path(path)
        return [self.analyze(source, sheet, (header_rows or {}).get(sheet)) for sheet in self.sheets(source)]

    @staticmethod
    def _field_key(header: str, field: StandardField, used: set[str]) -> str:
        if field not in (StandardField.OTHER, StandardField.IGNORE):
            return field.value
        base = f"custom:{normalize_column_name(header) or 'unnamed'}"
        key = base
        suffix = 2
        while key in used:
            key = f"{base}:{suffix}"
            suffix += 1
        return key
