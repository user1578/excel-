"""在 COM 高保真和 openpyxl 兼容引擎之间进行安全路由。"""

from __future__ import annotations

from pathlib import Path

from app.models.fill_models import FillPreview, FillResult, TemplateAnalysis
from app.models.table_dataset import TableDataset
from app.services.excel_com_service import ExcelComService
from app.services.workbook_fill_service import (
    KEEP_EXISTING,
    SEQUENCE_FILL_BLANK,
    WorkbookFillService,
)


class WorkbookFormatPreservationError(ValueError):
    """当前环境无法在不改变工作簿格式的前提下处理所选模板。"""


class WorkbookFillCoordinator:
    """为页面提供统一的模板分析、预览与填写入口。"""

    def __init__(self, com_service=None, compatibility_service: WorkbookFillService | None = None) -> None:
        self.com_service = com_service or ExcelComService()
        self.compatibility_service = compatibility_service or WorkbookFillService()

    def select_engine(self, template_path: str | Path, compatibility_accepted: bool) -> str:
        suffix = Path(template_path).suffix.lower()
        if suffix not in {".xls", ".xlsx", ".xlsm"}:
            raise WorkbookFormatPreservationError("仅支持 .xls、.xlsx 或 .xlsm Excel 模板。")
        if self.com_service.is_available():
            return "com"
        if suffix in {".xls", ".xlsm"}:
            raise WorkbookFormatPreservationError(
                "当前未检测到可用的 Microsoft Excel；为保留 .xls/.xlsm 格式与宏，无法使用兼容模式填写。"
            )
        if not compatibility_accepted:
            raise WorkbookFormatPreservationError(
                "当前未检测到 Microsoft Excel。请明确接受 openpyxl 兼容模式后再填写 .xlsx 模板。"
            )
        return "compatibility"

    def list_sheets(self, template_path: str | Path, compatibility_accepted: bool = False) -> list[str]:
        if self.select_engine(template_path, compatibility_accepted) == "com":
            return self.com_service.list_sheets(template_path)
        return self.compatibility_service_analyzer.sheets(template_path)

    def analyze(self, template_path: str | Path, sheet_name: str, header_row: int | None = None, compatibility_accepted: bool = False) -> TemplateAnalysis:
        if self.select_engine(template_path, compatibility_accepted) == "com":
            return self.com_service.analyze(template_path, sheet_name, header_row)
        return self.compatibility_service_analyzer.analyze(template_path, sheet_name, header_row)

    @property
    def compatibility_service_analyzer(self):
        from app.parsers.workbook_template_analyzer import WorkbookTemplateAnalyzer
        return WorkbookTemplateAnalyzer()

    def default_mappings(self, analysis: TemplateAnalysis, dataset: TableDataset) -> dict[str, str]:
        return self.compatibility_service.default_mappings(analysis, dataset)

    def preview(
        self,
        analysis: TemplateAnalysis,
        dataset: TableDataset,
        mappings: dict[str, str],
        sequence_start: int = 1,
        sequence_mode: str = SEQUENCE_FILL_BLANK,
        *,
        compatibility_accepted: bool = False,
    ) -> FillPreview:
        if self.select_engine(analysis.template_path, compatibility_accepted) == "com":
            return self.com_service.preview(analysis, dataset, mappings, sequence_start, sequence_mode)
        return self.compatibility_service.preview(analysis, dataset, mappings, sequence_start, sequence_mode)

    def fill(
        self,
        analysis: TemplateAnalysis,
        dataset: TableDataset,
        mappings: dict[str, str],
        existing_value_strategy: str = KEEP_EXISTING,
        sequence_start: int = 1,
        sequence_mode: str = SEQUENCE_FILL_BLANK,
        *,
        output_path: str | Path,
        compatibility_accepted: bool = False,
        merge_has_unresolved: bool = False,
        allow_unresolved_merge: bool = False,
    ) -> FillResult:
        if merge_has_unresolved and not allow_unresolved_merge:
            raise ValueError("当前资料汇总仍有未解决冲突或身份歧义，不能直接填写模板。")
        if self.select_engine(analysis.template_path, compatibility_accepted) == "com":
            return self.com_service.fill(
                analysis, dataset, mappings, existing_value_strategy, sequence_start, sequence_mode,
                output_path=output_path,
            )
        return self.compatibility_service.fill(
            analysis, dataset, mappings, existing_value_strategy, sequence_start, sequence_mode,
            output_path=output_path, compatibility_accepted=True,
        )
