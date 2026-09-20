"""通过 Microsoft Excel COM 原格式填写工作簿。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from app.models.fill_models import FillPreview, FillResult, TemplateAnalysis
from app.models.table_dataset import TableDataset
from app.services.atomic_workbook_output import AtomicFileOutput
from app.services.workbook_fill_service import (
    AUTO_SEQUENCE,
    KEEP_EXISTING,
    SEQUENCE_FILL_BLANK,
    SEQUENCE_NONE,
    SEQUENCE_RENUMBER,
    SKIP_CONFLICTING_ROW,
    USE_NEW_VALUE,
    MergedCellWriteError,
)
from app.utils.excel_safety import safe_excel_value
from app.utils.excel_images import constrained_photo
from app.utils.value_normalizer import normalize_text


class ExcelComServiceError(ValueError):
    """Microsoft Excel 自动化不可用或无法安全完成操作。"""


class ExcelComService:
    """仅按原扩展名保存的 Excel COM 引擎。"""

    _SUPPORTED_SUFFIXES = {".xls", ".xlsx", ".xlsm"}

    def __init__(self, com_client=None) -> None:
        self._runtime_client = com_client
        self._injected_client = com_client is not None

    def is_available(self) -> bool:
        if not self._injected_client and sys.platform != "win32":
            return False
        excel = None
        try:
            excel = self._open_excel(allow_import=True)
            return True
        except Exception:
            return False
        finally:
            self._quit(excel)

    def list_sheets(self, template_path: str | Path) -> list[str]:
        path = self._validate_template(template_path)
        excel = workbook = None
        try:
            excel = self._open_excel()
            workbook = excel.Workbooks.Open(str(path.resolve()), ReadOnly=True)
            return [sheet.Name for sheet in workbook.Worksheets]
        except ExcelComServiceError:
            raise
        except Exception as error:
            raise ExcelComServiceError(f"Microsoft Excel 无法读取模板：{error}") from error
        finally:
            self._close_workbook(workbook)
            self._quit(excel)

    def analyze(self, template_path: str | Path, sheet_name: str, header_row: int | None = None) -> TemplateAnalysis:
        path = self._validate_template(template_path)
        excel = workbook = None
        try:
            excel = self._open_excel()
            workbook = excel.Workbooks.Open(str(path.resolve()), ReadOnly=True)
            worksheet = workbook.Worksheets(sheet_name)
            first_row, last_row, first_column, last_column = self._used_bounds(worksheet)
            row_number = header_row or self._detect_header_row(worksheet, first_row, last_row, first_column, last_column)
            if row_number < first_row or row_number > last_row:
                raise ValueError("表头行不在模板范围内。")
            target_columns: dict[str, int] = {}
            non_anchors: set[int] = set()
            for column in range(first_column, last_column + 1):
                cell = worksheet.Cells(row_number, column)
                if self._is_non_anchor_merged(cell, row_number, column):
                    non_anchors.add(column)
                    continue
                label = normalize_text(cell.Value)
                if label:
                    unique = label if label not in target_columns else f"{label}（第{column}列）"
                    target_columns[unique] = column
            if not target_columns:
                raise ValueError("模板表头行没有可映射字段。")
            return TemplateAnalysis(path, sheet_name, row_number, target_columns, non_anchors)
        except ExcelComServiceError:
            raise
        except ValueError:
            raise
        except Exception as error:
            raise ExcelComServiceError(f"Microsoft Excel 无法分析模板：{error}") from error
        finally:
            self._close_workbook(workbook)
            self._quit(excel)

    def preview(
        self,
        analysis: TemplateAnalysis,
        dataset: TableDataset,
        mappings: dict[str, str],
        sequence_start: int = 1,
        sequence_mode: str = SEQUENCE_FILL_BLANK,
    ) -> FillPreview:
        self._validate_mappings(analysis, dataset, mappings)
        sequence_target = self._sequence_target(mappings, sequence_mode)
        self._validate_sequence(sequence_target, sequence_start, sequence_mode)
        active_mappings = {
            target: source for target, source in mappings.items()
            if source != AUTO_SEQUENCE or sequence_target is not None
        }
        self._reject_non_anchor_mappings(analysis, active_mappings)
        excel = workbook = None
        try:
            excel = self._open_excel()
            workbook = excel.Workbooks.Open(str(analysis.template_path.resolve()), ReadOnly=True)
            worksheet = workbook.Worksheets(analysis.sheet_name)
            conflicts = 0
            for offset, _row in enumerate(dataset.rows):
                for target, source in active_mappings.items():
                    if source == AUTO_SEQUENCE:
                        continue
                    if worksheet.Cells(analysis.header_row + 1 + offset, analysis.target_columns[target]).Value not in (None, ""):
                        conflicts += 1
            return FillPreview(
                len(dataset.rows), dict(mappings), conflicts, [], sequence_target,
                sequence_start if sequence_target else None,
                sequence_mode if sequence_target else SEQUENCE_NONE,
            )
        finally:
            self._close_workbook(workbook)
            self._quit(excel)

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
    ) -> FillResult:
        self._validate_mappings(analysis, dataset, mappings)
        if existing_value_strategy not in {KEEP_EXISTING, USE_NEW_VALUE, SKIP_CONFLICTING_ROW}:
            raise ValueError("未知的模板已有值处理策略。")
        sequence_target = self._sequence_target(mappings, sequence_mode)
        self._validate_sequence(sequence_target, sequence_start, sequence_mode)
        active_mappings = {
            target: source for target, source in mappings.items()
            if source != AUTO_SEQUENCE or sequence_target is not None
        }
        self._reject_non_anchor_mappings(analysis, active_mappings)

        with AtomicFileOutput(analysis.template_path, output_path) as transaction:
            shutil.copy2(analysis.template_path, transaction.temporary_path)
            excel = workbook = None
            try:
                excel = self._open_excel(allow_import=True)
                workbook = excel.Workbooks.Open(str(transaction.temporary_path.resolve()))
                worksheet = workbook.Worksheets(analysis.sheet_name)
                written_rows, skipped_rows, preserved_cells = self._write_rows(
                    worksheet,
                    analysis,
                    dataset,
                    mappings,
                    existing_value_strategy,
                    sequence_target,
                    sequence_start,
                    sequence_mode,
                )
                workbook.Save()
            except ExcelComServiceError:
                raise
            except Exception as error:
                raise ExcelComServiceError(f"Microsoft Excel 填写模板失败：{error}") from error
            finally:
                self._close_workbook(workbook)
                self._quit(excel)
            transaction.commit(self.validate_output)
        return FillResult(Path(output_path), written_rows, skipped_rows, preserved_cells, engine="com")

    def validate_output(self, output_path: str | Path) -> None:
        path = Path(output_path)
        if not path.is_file():
            raise ExcelComServiceError("临时输出文件不存在。")
        excel = workbook = None
        try:
            excel = self._open_excel()
            workbook = excel.Workbooks.Open(str(path.resolve()), ReadOnly=True)
            _ = [sheet.Name for sheet in workbook.Worksheets]
        except ExcelComServiceError:
            raise
        except Exception as error:
            raise ExcelComServiceError(f"Microsoft Excel 无法重新打开输出文件：{error}") from error
        finally:
            self._close_workbook(workbook)
            self._quit(excel)

    def _write_rows(self, worksheet, analysis, dataset, mappings, strategy, sequence_target, sequence_start, sequence_mode):
        data_start = analysis.header_row + 1
        written_rows = skipped_rows = preserved_cells = 0
        next_sequence = sequence_start
        for offset, source_row in enumerate(dataset.rows):
            row_number = data_start + offset
            if row_number > data_start:
                self._copy_example_row(worksheet, data_start, row_number)
            targets = [
                (target, analysis.target_columns[target], source_key, source_row.values.get(source_key, ""))
                for target, source_key in mappings.items()
                if source_key != AUTO_SEQUENCE
            ]
            existing = [worksheet.Cells(row_number, column).Value not in (None, "") for _target, column, _source, _value in targets]
            if strategy == SKIP_CONFLICTING_ROW and any(existing):
                skipped_rows += 1
                continue
            wrote = False
            for (target, column, source_key, value), has_existing in zip(targets, existing):
                if has_existing and strategy == KEEP_EXISTING:
                    preserved_cells += 1
                    continue
                cell = worksheet.Cells(row_number, column)
                if source_key == "photo" and value not in (None, ""):
                    self._insert_photo(worksheet, cell, value, target, row_number)
                else:
                    cell.Value = safe_excel_value(value)
                wrote = True
            if sequence_target is not None:
                cell = worksheet.Cells(row_number, analysis.target_columns[sequence_target])
                if sequence_mode == SEQUENCE_RENUMBER or cell.Value in (None, ""):
                    cell.Value = next_sequence
                    wrote = True
                next_sequence += 1
            if wrote:
                written_rows += 1
        return written_rows, skipped_rows, preserved_cells

    @staticmethod
    def _insert_photo(worksheet, cell, value, field_name: str, row_number: int) -> None:
        source, width, height = constrained_photo(value, cell.Width, cell.Height, field_name, row_number)
        shape = worksheet.Shapes.AddPicture(str(source.resolve()), False, True, cell.Left, cell.Top, width, height)
        shape.LockAspectRatio = True

    @staticmethod
    def _copy_example_row(worksheet, source_row: int, target_row: int) -> None:
        try:
            worksheet.Rows(source_row).Copy(worksheet.Rows(target_row))
        except (AttributeError, TypeError):
            return

    @staticmethod
    def _validate_mappings(analysis: TemplateAnalysis, dataset: TableDataset, mappings: dict[str, str]) -> None:
        if not mappings:
            raise ValueError("请至少配置一个字段映射。")
        unknown_targets = set(mappings) - set(analysis.target_columns)
        unknown_sources = set(mappings.values()) - set(dataset.columns) - {AUTO_SEQUENCE}
        if unknown_targets or unknown_sources:
            raise ValueError("字段映射包含不存在的模板字段或数据源字段。")

    @staticmethod
    def _sequence_target(mappings: dict[str, str], sequence_mode: str) -> str | None:
        targets = [target for target, source in mappings.items() if source == AUTO_SEQUENCE]
        if len(targets) > 1:
            raise ValueError("一次填充只能指定一个自动序号目标列。")
        return targets[0] if targets and sequence_mode != SEQUENCE_NONE else None

    @staticmethod
    def _validate_sequence(sequence_target: str | None, sequence_start: int, sequence_mode: str) -> None:
        if sequence_mode not in {SEQUENCE_FILL_BLANK, SEQUENCE_RENUMBER, SEQUENCE_NONE}:
            raise ValueError("序号处理方式不支持。")
        if sequence_target is not None and not 1 <= sequence_start <= 999999:
            raise ValueError("起始序号必须在 1 到 999999 之间。")

    @staticmethod
    def _reject_non_anchor_mappings(analysis: TemplateAnalysis, mappings: dict[str, str]) -> None:
        unsafe = [target for target in mappings if analysis.target_columns[target] in analysis.merged_non_anchor_columns]
        if unsafe:
            raise MergedCellWriteError(f"字段“{unsafe[0]}”位于合并单元格的非左上角，不能写入")

    @staticmethod
    def _used_bounds(worksheet) -> tuple[int, int, int, int]:
        used_range = worksheet.UsedRange
        first_row = int(used_range.Row)
        first_column = int(used_range.Column)
        last_row = first_row + int(used_range.Rows.Count) - 1
        last_column = first_column + int(used_range.Columns.Count) - 1
        return first_row, last_row, first_column, last_column

    @staticmethod
    def _detect_header_row(worksheet, first_row: int, last_row: int, first_column: int, last_column: int) -> int:
        candidates = range(first_row, min(last_row, first_row + 9) + 1)
        best_row = first_row
        best_count = -1
        for row in candidates:
            count = sum(bool(normalize_text(worksheet.Cells(row, column).Value)) for column in range(first_column, last_column + 1))
            if count > best_count:
                best_row, best_count = row, count
        if best_count <= 0:
            raise ValueError("无法判断表头行，请手动选择。")
        return best_row

    @staticmethod
    def _is_non_anchor_merged(cell, row: int, column: int) -> bool:
        try:
            if not cell.MergeCells:
                return False
            area = cell.MergeArea
            return (int(area.Row), int(area.Column)) != (row, column)
        except AttributeError:
            return False

    def _open_excel(self, *, allow_import: bool = False):
        try:
            excel = self._operation_client(allow_import).DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            return excel
        except Exception as error:
            raise ExcelComServiceError("未检测到可用的 Microsoft Excel 自动化服务。") from error

    def _operation_client(self, allow_import: bool):
        if self._runtime_client is not None:
            return self._runtime_client
        if not allow_import:
            raise ExcelComServiceError("Microsoft Excel 尚未完成可用性检测。")
        try:
            import win32com.client
        except ImportError as error:
            raise ExcelComServiceError("当前 Python 环境缺少 pywin32，无法使用 Microsoft Excel 自动化。") from error
        self._runtime_client = win32com.client
        return self._runtime_client

    @classmethod
    def _validate_template(cls, template_path: str | Path) -> Path:
        path = Path(template_path)
        if path.suffix.lower() not in cls._SUPPORTED_SUFFIXES:
            raise ValueError("仅支持 .xls、.xlsx 或 .xlsm Excel 模板。")
        if not path.is_file():
            raise ValueError("模板文件不存在。")
        return path

    @staticmethod
    def _close_workbook(workbook) -> None:
        if workbook is not None:
            try:
                workbook.Close(SaveChanges=False)
            except Exception:
                pass

    @staticmethod
    def _quit(excel) -> None:
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
