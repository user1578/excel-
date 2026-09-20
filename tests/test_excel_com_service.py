"""COM 填充路由与原格式原子输出的 mock 测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.fill_models import TemplateAnalysis
from app.models.table_dataset import Provenance, TableDataset, TableRow
from app.services.excel_com_service import ExcelComService
from app.services.workbook_fill_coordinator import (
    WorkbookFillCoordinator,
    WorkbookFormatPreservationError,
)


class FakeCell:
    def __init__(self, value=None):
        self.Value = value
        self.MergeCells = False


class FakeWorksheet:
    Name = "报名"

    def __init__(self):
        self._cells = {(1, 1): FakeCell("姓名"), (1, 2): FakeCell("班级")}
        self.UsedRange = type(
            "UsedRange", (), {
                "Row": 1,
                "Column": 1,
                "Rows": type("Rows", (), {"Count": 2})(),
                "Columns": type("Columns", (), {"Count": 2})(),
            }
        )()

    def Cells(self, row, column):
        return self._cells.setdefault((row, column), FakeCell())


class FakeWorksheets:
    def __init__(self, sheet):
        self.sheet = sheet

    def __iter__(self):
        return iter([self.sheet])

    def __call__(self, name):
        assert name == self.sheet.Name
        return self.sheet


class FakeWorkbook:
    def __init__(self):
        self.Worksheets = FakeWorksheets(FakeWorksheet())
        self.saved = False
        self.closed = False

    def Save(self):
        self.saved = True

    def Close(self, SaveChanges=False):
        self.closed = True


class FakeExcel:
    def __init__(self):
        self.Visible = True
        self.DisplayAlerts = True
        self.Workbooks = self
        self.opened_paths: list[Path] = []
        self.workbooks: list[FakeWorkbook] = []
        self.quit_called = False

    def Open(self, path, ReadOnly=False):
        self.opened_paths.append(Path(path))
        workbook = FakeWorkbook()
        self.workbooks.append(workbook)
        return workbook

    def Quit(self):
        self.quit_called = True


class FakeComClient:
    def __init__(self):
        self.instances: list[FakeExcel] = []

    def DispatchEx(self, name):
        assert name == "Excel.Application"
        excel = FakeExcel()
        self.instances.append(excel)
        return excel


class UnavailableComService:
    def is_available(self):
        return False


def dataset() -> TableDataset:
    return TableDataset(
        ["name"],
        [TableRow({"name": "测试学生"}, Provenance("虚构来源.xlsx", "报名", 2))],
        "虚构来源.xlsx",
        "报名",
        1,
        column_labels={"name": "姓名"},
    )


def test_com_available_routes_every_template_suffix(tmp_path):
    coordinator = WorkbookFillCoordinator(com_service=ExcelComService(FakeComClient()))
    for suffix in (".xls", ".xlsx", ".xlsm"):
        assert coordinator.select_engine(tmp_path / f"模板{suffix}", False) == "com"


def test_no_excel_rejects_legacy_and_macro_without_compatibility_fallback(tmp_path):
    coordinator = WorkbookFillCoordinator(com_service=UnavailableComService())
    for suffix in (".xls", ".xlsm"):
        with pytest.raises(WorkbookFormatPreservationError, match="Microsoft Excel"):
            coordinator.select_engine(tmp_path / f"模板{suffix}", False)
    with pytest.raises(WorkbookFormatPreservationError, match="兼容模式"):
        coordinator.select_engine(tmp_path / "模板.xlsx", False)
    assert coordinator.select_engine(tmp_path / "模板.xlsx", True) == "compatibility"


def test_com_analyzes_and_fills_original_suffix_using_save_and_atomic_copy(tmp_path):
    source = tmp_path / "报名模板.xlsm"
    source.write_bytes(b"fake macro workbook")
    output = tmp_path / "用户选择" / "报名结果.xlsm"
    client = FakeComClient()
    service = ExcelComService(client)
    coordinator = WorkbookFillCoordinator(com_service=service)

    assert coordinator.list_sheets(source) == ["报名"]
    analysis = coordinator.analyze(source, "报名", 1)
    assert analysis.target_columns == {"姓名": 1, "班级": 2}
    result = coordinator.fill(
        analysis,
        dataset(),
        {"姓名": "name"},
        output_path=output,
    )

    assert result.engine == "com"
    assert output.read_bytes() == b"fake macro workbook"
    assert source.read_bytes() == b"fake macro workbook"
    assert not list(output.parent.glob("*.partial.*"))
    opened_paths = [path for excel in client.instances for path in excel.opened_paths]
    assert opened_paths and all(path.suffix.lower() == ".xlsm" for path in opened_paths)
    assert all(excel.quit_called for excel in client.instances)
    assert all(workbook.closed for excel in client.instances for workbook in excel.workbooks)
    assert any(workbook.saved for excel in client.instances for workbook in excel.workbooks)


def test_coordinator_blocks_unresolved_merge_until_explicitly_allowed(tmp_path):
    source = tmp_path / "模板.xlsx"
    source.write_bytes(b"placeholder")
    analysis = TemplateAnalysis(source, "报名", 1, {"姓名": 1})
    coordinator = WorkbookFillCoordinator(com_service=UnavailableComService())

    with pytest.raises(ValueError, match="未解决"):
        coordinator.fill(
            analysis,
            dataset(),
            {"姓名": "name"},
            output_path=tmp_path / "结果.xlsx",
            compatibility_accepted=True,
            merge_has_unresolved=True,
        )
