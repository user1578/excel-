"""Excel 输出安全边界：只转义用户来源的文本。"""

from __future__ import annotations

from typing import Any


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_excel_value(value: Any) -> Any:
    """将可能被 Excel 解释为公式的用户文本显式写成文本。

    程序生成的公式不得通过此函数写入，而应由调用方直接赋值。
    """
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value
