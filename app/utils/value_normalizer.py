"""用于导入和跨表处理的保守值规范化工具。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
import re
from typing import Any

from openpyxl.utils.datetime import from_excel


_DATE_PATTERNS = (
    "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y.%m.%d %H:%M:%S",
)


@dataclass(frozen=True)
class DateNormalization:
    """日期标准化结果，保留无法可靠识别时的原始显示值。"""

    value: str
    is_valid: bool
    reason: str | None = None


def normalize_text(value: object) -> str:
    """将可显示值转成去除两端空白的文本，不将缺失值变成 ``nan``。"""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def normalize_date(
    value: Any,
    *,
    date_semantic: bool = False,
    excel_epoch: datetime | None = None,
) -> DateNormalization:
    """将可可靠识别的日期转为 ISO 日期；未知格式保留原始文本。

    不猜测八位数字或模糊月日顺序，避免把用户数据改成错误日期。
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return DateNormalization("", True)
    if isinstance(value, datetime):
        return DateNormalization(value.date().isoformat(), True)
    if isinstance(value, date):
        return DateNormalization(value.isoformat(), True)
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat) and value.__class__.__module__.startswith("pandas"):
        try:
            return DateNormalization(value.date().isoformat(), True)
        except (AttributeError, TypeError, ValueError):
            text = normalize_text(value)
            return DateNormalization(text, not text, None if not text else "unrecognized_date")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 1 <= value <= 100000:
            if not (date_semantic and excel_epoch is not None):
                return DateNormalization(normalize_text(value), False, "missing_date_semantics")
            try:
                parsed = from_excel(value, epoch=excel_epoch)
                normalized = parsed.date() if isinstance(parsed, datetime) else parsed
                if isinstance(normalized, date):
                    return DateNormalization(normalized.isoformat(), True)
            except (TypeError, ValueError, OverflowError):
                pass
        return DateNormalization(normalize_text(value), False, "unrecognized_date")
    text = normalize_text(value)
    if not text:
        return DateNormalization("", True)
    chinese = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s+.*)?", text)
    if chinese:
        try:
            return DateNormalization(date(*(int(part) for part in chinese.groups())).isoformat(), True)
        except ValueError:
            return DateNormalization(text, False, "unrecognized_date")
    for pattern in _DATE_PATTERNS:
        try:
            return DateNormalization(datetime.strptime(text, pattern).date().isoformat(), True)
        except ValueError:
            continue
    if "T" in text and "-" in text:
        try:
            return DateNormalization(datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat(), True)
        except ValueError:
            pass
    return DateNormalization(text, False, "unrecognized_date")


def normalize_class_name(value: object) -> str:
    """仅做安全的文本标准化；班级别名解析仍由基础数据服务负责。"""
    return normalize_text(value).replace(" ", "")


def normalize_column_name(value: object) -> str:
    """用于判断同一自定义列，保留原列名供显示与导出。"""
    return re.sub(r"[\s_\-（）()]", "", normalize_text(value)).casefold()
