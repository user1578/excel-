"""将用户明确提供的纯文本安全转换为 TableDataset。"""

from __future__ import annotations

from pathlib import Path
import json

from app.models.table_dataset import Provenance, TableDataset, TableRow
from app.models.field_mapping import StandardField
from app.parsers.field_detector import ALIASES
from app.utils.value_normalizer import normalize_column_name


class TextDatasetParseError(ValueError):
    """文本不能可靠识别为 TSV 或键值记录。"""


class TextDatasetService:
    """不访问数据库，也不调用 AI；所有解析结果都由界面先预览确认。"""

    def parse_text(self, text: str, source_name: str = "粘贴文本") -> TableDataset:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff\n \t")
        if not normalized:
            raise TextDatasetParseError("文本为空，无法识别字段。")
        if "\t" in normalized.split("\n", 1)[0]:
            labels, records = self._parse_tsv(normalized)
        else:
            labels, records = self._parse_key_values(normalized)
        return self._dataset(labels, records, source_name)

    def parse_file(self, path: str | Path) -> TableDataset:
        file_path = Path(path)
        if file_path.suffix.lower() != ".txt":
            raise TextDatasetParseError("文本数据源仅支持 .txt 文件。")
        raw = file_path.read_bytes()
        decoded: str | None = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                decoded = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise TextDatasetParseError("无法按 UTF-8、UTF-8 BOM 或 GB18030 读取该 TXT 文件。")
        return self.parse_text(decoded, file_path.name)

    def parse_ai_json(self, raw: str, source_name: str = "AI 结构化解析") -> TableDataset:
        """只接受列/行 JSON 并交给同一数据集构造器，调用方仍需展示确认预览。"""
        try:
            value = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
            labels = value["columns"]
            records = value["rows"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise TextDatasetParseError("AI 未返回可用的列/行 JSON。") from error
        if not isinstance(labels, list) or not labels or not all(isinstance(item, str) and item.strip() for item in labels):
            raise TextDatasetParseError("AI 返回的字段列表无效。")
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise TextDatasetParseError("AI 返回的数据行无效。")
        return self._dataset([item.strip() for item in labels], [{label: str(record.get(label, "") or "") for label in labels} for record in records], source_name)

    @staticmethod
    def _parse_tsv(text: str) -> tuple[list[str], list[dict[str, str]]]:
        lines = [line for line in text.split("\n") if line.strip()]
        header = [value.strip() for value in lines[0].split("\t")]
        if not header or any(not item for item in header):
            raise TextDatasetParseError("TSV 第一行必须是完整表头。")
        if len(lines) < 2:
            raise TextDatasetParseError("TSV 缺少数据行。")
        records: list[dict[str, str]] = []
        for line_number, line in enumerate(lines[1:], start=2):
            values = [item.strip() for item in line.split("\t")]
            if len(values) != len(header):
                raise TextDatasetParseError(f"TSV 第 {line_number} 行列数与表头不一致。")
            records.append(dict(zip(header, values)))
        return header, records

    @staticmethod
    def _parse_key_values(text: str) -> tuple[list[str], list[dict[str, str]]]:
        blocks = [block for block in text.split("\n\n") if block.strip()]
        records: list[dict[str, str]] = []
        labels: list[str] = []
        for block in blocks:
            record: dict[str, str] = {}
            for line in block.split("\n"):
                line = line.strip()
                if not line:
                    continue
                separator = next((item for item in ("：", ":", "=") if item in line), None)
                if separator is None:
                    raise TextDatasetParseError("文本不是可识别的 TSV 或“字段：值”记录；可使用 AI 结构化解析。")
                key, value = (part.strip() for part in line.split(separator, 1))
                if not key:
                    raise TextDatasetParseError("键值记录包含空字段名称。")
                if key in record:
                    raise TextDatasetParseError(f"同一记录中字段“{key}”重复。")
                record[key] = value
                if key not in labels:
                    labels.append(key)
            if record:
                records.append(record)
        if not records:
            raise TextDatasetParseError("未识别到有效的键值记录。")
        return labels, records

    def _dataset(self, labels: list[str], records: list[dict[str, str]], source_name: str) -> TableDataset:
        columns: list[str] = []
        column_labels: dict[str, str] = {}
        source_keys: dict[str, str] = {}
        custom_fields: set[str] = set()
        for label in labels:
            detected = next((field for field, aliases in ALIASES.items() if label.strip() in aliases), StandardField.OTHER)
            key = detected.value if detected is not StandardField.OTHER else f"custom:{normalize_column_name(label) or label}"
            if key in columns:
                key = f"custom:{normalize_column_name(label) or label}"
            base_key = key
            suffix = 2
            while key in columns:
                key = f"{base_key}__{suffix}"
                suffix += 1
            columns.append(key)
            source_keys[label] = key
            column_labels[key] = label
            if key.startswith("custom:"):
                custom_fields.add(key)
        rows = [
            TableRow({source_keys[label]: record.get(label, "") for label in labels}, Provenance(source_name, None, index + 2))
            for index, record in enumerate(records)
        ]
        return TableDataset(columns, rows, source_name, None, 1, column_labels=column_labels, custom_fields=custom_fields)
