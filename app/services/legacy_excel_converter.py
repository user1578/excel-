"""将旧版 .xls 模板只读转换为临时 .xlsx 工作副本。"""

from __future__ import annotations

import tempfile
from pathlib import Path


class LegacyExcelConversionError(ValueError):
    """旧 Excel 模板无法安全转换时给界面展示的中文错误。"""


class LegacyExcelConverter:
    """仅在本机 Microsoft Excel 可用时处理 .xls，绝不改写原文件。"""

    def __init__(self, com_client=None, temporary_root: str | Path | None = None) -> None:
        self.com_client = com_client
        self.temporary_root = Path(temporary_root) if temporary_root else None

    @staticmethod
    def is_legacy_template(path: str | Path) -> bool:
        return Path(path).suffix.lower() == ".xls"

    def convert(self, source: str | Path) -> Path:
        source_path = Path(source)
        if not self.is_legacy_template(source_path):
            raise LegacyExcelConversionError("仅可转换 .xls 旧版 Excel 模板。")
        if not source_path.is_file():
            raise LegacyExcelConversionError("找不到所选的 .xls 模板文件。")
        client = self.com_client or self._import_com_client()
        workdir = Path(tempfile.mkdtemp(prefix="excel_legacy_", dir=str(self.temporary_root) if self.temporary_root else None))
        destination = workdir / f"{source_path.stem}.xlsx"
        excel = workbook = None
        try:
            excel = client.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            workbook = excel.Workbooks.Open(str(source_path.resolve()), ReadOnly=True)
            workbook.SaveAs(str(destination.resolve()), FileFormat=51)  # xlOpenXMLWorkbook
        except Exception as error:
            raise LegacyExcelConversionError(f"旧版 .xls 模板转换失败：{error}") from error
        finally:
            if workbook is not None:
                try:
                    workbook.Close(SaveChanges=False)
                except Exception:
                    pass
            if excel is not None:
                try:
                    excel.Quit()
                except Exception:
                    pass
        if not destination.is_file():
            raise LegacyExcelConversionError("旧版 .xls 模板转换失败：Microsoft Excel 未生成 .xlsx 工作副本。")
        return destination

    @staticmethod
    def _import_com_client():
        try:
            import win32com.client
        except ImportError as error:
            raise LegacyExcelConversionError("当前环境未安装 Microsoft Excel 自动化组件，无法打开 .xls 模板；请安装 Microsoft Excel，或将模板另存为 .xlsx 后再选择。") from error
        return win32com.client
