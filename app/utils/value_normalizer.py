"""用于导入和跨表处理的保守值规范化工具。"""

from __future__ import annotations

from datetime import date, datetime
import math
import re
from typing import Any

from openpyxl.utils.datetime import from_excel


_DATE_PATTERNS = (
    "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y.%m.%d %H:%M:%S",
)


def normalize_text(value: object) -> str:
    """将可显示值转成去除两端空白的文本，不将缺失值变成 ``nan``。"""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def normalize_date(value: Any) -> str:
    """将可可靠识别的日期转为 ISO 日期；未知格式保留原始文本。

    不猜测八位数字或模糊月日顺序，避免把用户数据改成错误日期。
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat) and value.__class__.__module__.startswith("pandas"):
        try:
            return value.date().isoformat()
        except (AttributeError, TypeError, ValueError):
            return normalize_text(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 1 <= value <= 100000:
            try:
                parsed = from_excel(value)
                return (parsed.date() if isinstance(parsed, datetime) else parsed).isoformat()
            except (TypeError, ValueError, OverflowError):
                pass
        return normalize_text(value)
    text = normalize_text(value)
    if not text:
        return ""
    chinese = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s+.*)?", text)
    if chinese:
        try:
            return date(*(int(part) for part in chinese.groups())).isoformat()
        except ValueError:
            return text
    for pattern in _DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    if "T" in text and "-" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return text


def normalize_class_name(value: object) -> str:
    """仅做安全的文本标准化；班级别名解析仍由基础数据服务负责。"""
    return normalize_text(value).replace(" ", "")


def normalize_column_name(value: object) -> str:
    """用于判断同一自定义列，保留原列名供显示与导出。"""
    return re.sub(r"[\s_\-（）()]", "", normalize_text(value)).casefold()
