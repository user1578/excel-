"""表格填充页面：分析模板、选择来源、映射和另存输出。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.table_dataset import TableDataset, TableRow
from app.parsers.workbook_template_analyzer import WorkbookTemplateAnalyzer
from app.services.data_workspace_service import DataWorkspaceService
from app.services.table_analysis_service import TableAnalysisService
from app.services.workbook_fill_service import KEEP_EXISTING, SKIP_CONFLICTING_ROW, USE_NEW_VALUE, WorkbookFillService


class WorkbookFillPage(QWidget):
    def __init__(self, workspace: DataWorkspaceService, master, parent=None) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.master = master
        self.template_analyzer = WorkbookTemplateAnalyzer()
        self.table_analyzer = TableAnalysisService()
        self.fill_service = WorkbookFillService()
        self.template_path: Path | None = None
        self.analysis = None
        self.dataset: TableDataset | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(QLabel("表格填充", objectName="pageTitle"))
        layout.addWidget(QLabel("仅支持 .xlsx；模板始终另存。用户文本会安全转义，程序公式保持为公式。"))
        template_bar = QHBoxLayout()
        choose = QPushButton("选择模板")
        choose.clicked.connect(self.choose_template)
        self.template_label = QLabel("尚未选择模板")
        self.sheet_box = QComboBox()
        self.header_spin = QSpinBox(); self.header_spin.setRange(0, 1000); self.header_spin.setSpecialValueText("自动表头")
        analyze = QPushButton("分析模板")
        analyze.clicked.connect(self.analyze_template)
        template_bar.addWidget(choose); template_bar.addWidget(self.template_label, 1); template_bar.addWidget(QLabel("目标 Sheet")); template_bar.addWidget(self.sheet_box); template_bar.addWidget(QLabel("表头行")); template_bar.addWidget(self.header_spin); template_bar.addWidget(analyze)
        layout.addLayout(template_bar)
        source_bar = QHBoxLayout()
        self.source_box = QComboBox()
        self.source_box.addItems(["当前资料汇总结果", "单独选择 xlsx/csv", "学生库"])
        choose_source = QPushButton("选择数据源")
        choose_source.clicked.connect(self.choose_source)
        self.source_label = QLabel("尚未选择数据源")
        source_bar.addWidget(QLabel("数据源")); source_bar.addWidget(self.source_box); source_bar.addWidget(choose_source); source_bar.addWidget(self.source_label, 1)
        layout.addLayout(source_bar)
        layout.addWidget(QLabel("字段映射", objectName="sectionTitle"))
        self.mapping_table = QTableWidget(0, 2)
        self.mapping_table.setHorizontalHeaderLabels(["模板字段", "数据源字段"])
        layout.addWidget(self.mapping_table, 1)
        controls = QHBoxLayout()
        self.strategy_box = QComboBox()
        self.strategy_box.addItem("保留模板已有值", KEEP_EXISTING)
        self.strategy_box.addItem("使用新值", USE_NEW_VALUE)
        self.strategy_box.addItem("跳过有冲突的行", SKIP_CONFLICTING_ROW)
        preview = QPushButton("预览")
        output = QPushButton("另存填写结果")
        preview.clicked.connect(self.preview)
        output.clicked.connect(self.output)
        controls.addWidget(QLabel("已有值策略")); controls.addWidget(self.strategy_box); controls.addWidget(preview); controls.addWidget(output); controls.addStretch()
        layout.addLayout(controls)
        self.message = QLabel("请先选择模板和数据源。")
        layout.addWidget(self.message)

    def choose_template(self) -> None:
        text, _ = QFileDialog.getOpenFileName(self, "选择 .xlsx 模板", "", "Excel 模板 (*.xlsx)")
        if not text: return
        self.template_path = Path(text)
        try:
            sheets = self.template_analyzer.sheets(self.template_path)
        except ValueError as error:
            QMessageBox.warning(self, "模板不可用", str(error)); return
        self.template_label.setText(self.template_path.name)
        self.sheet_box.clear(); self.sheet_box.addItems(sheets)
        self.analysis = None

    def analyze_template(self) -> None:
        if self.template_path is None or not self.sheet_box.currentText():
            QMessageBox.information(self, "请选择模板", "请先选择一个 .xlsx 模板。"); return
        try:
            self.analysis = self.template_analyzer.analyze(self.template_path, self.sheet_box.currentText(), self.header_spin.value() or None)
        except ValueError as error:
            QMessageBox.warning(self, "模板分析失败", str(error)); return
        self.message.setText(f"模板已分析：{len(self.analysis.target_columns)} 个可映射字段。")
        self._refresh_mapping_table()

    def choose_source(self) -> None:
        choice = self.source_box.currentText()
        if choice == "当前资料汇总结果":
            result = self.workspace.current_merge_result
            if result is None or self.workspace.current_dataset is None:
                QMessageBox.information(self, "没有汇总结果", "请先在“资料汇总”完成一次汇总。"); return
            self.dataset = self.workspace.current_dataset
        elif choice == "学生库":
            students = self.master.list_students()
            columns = ["name", "student_number", "class_name", "major", "grade", "phone", "dormitory", "remark"]
            rows = [TableRow({key: getattr(student, key) or "" for key in columns}, Provenance("学生库", None, index)) for index, student in enumerate(students, 1)]
            self.dataset = TableDataset(columns, rows, "学生库", None, 1, column_labels={"name": "姓名", "student_number": "学号", "class_name": "班级", "major": "专业", "grade": "年级", "phone": "手机号", "dormitory": "寝室", "remark": "备注"})
        else:
            text, _ = QFileDialog.getOpenFileName(self, "选择数据源", "", "资料文件 (*.xlsx *.csv)")
            if not text: return
            try:
                path = Path(text)
                sheets = self.table_analyzer.sheets(path)
                self.dataset = self.table_analyzer.analyze(path, sheets[0])
            except ValueError as error:
                QMessageBox.warning(self, "数据源分析失败", str(error)); return
        self.source_label.setText(f"{self.dataset.source_file}，{len(self.dataset.rows)} 行")
        self._refresh_mapping_table()

    def _refresh_mapping_table(self) -> None:
        self.mapping_table.setRowCount(0)
        if self.analysis is None or self.dataset is None:
            return
        defaults = self.fill_service.default_mappings(self.analysis, self.dataset)
        for row, target in enumerate(self.analysis.target_columns):
            self.mapping_table.insertRow(row)
            self.mapping_table.setItem(row, 0, QTableWidgetItem(target))
            box = QComboBox(); box.addItem("不填充", None)
            for key in self.dataset.columns:
                box.addItem(self.dataset.display_label(key), key)
            if target in defaults:
                box.setCurrentIndex(box.findData(defaults[target]))
            self.mapping_table.setCellWidget(row, 1, box)

    def _mappings(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in range(self.mapping_table.rowCount()):
            target = self.mapping_table.item(row, 0).text()
            key = self.mapping_table.cellWidget(row, 1).currentData()
            if key is not None: result[target] = key
        return result

    def preview(self) -> None:
        if self.analysis is None or self.dataset is None:
            QMessageBox.information(self, "信息不完整", "请先分析模板并选择数据源。"); return
        try:
            result = self.fill_service.preview(self.analysis, self.dataset, self._mappings())
        except ValueError as error:
            QMessageBox.warning(self, "无法预览", str(error)); return
        warning = f"；合并单元格风险 {len(result.merged_cell_warnings)} 项" if result.merged_cell_warnings else ""
        self.message.setText(f"将处理 {result.row_count} 行；模板已有值冲突 {result.existing_value_conflicts} 个{warning}。")

    def output(self) -> None:
        if self.analysis is None or self.dataset is None:
            QMessageBox.information(self, "信息不完整", "请先分析模板并选择数据源。"); return
        try:
            result = self.fill_service.fill(self.analysis, self.dataset, self._mappings(), self.strategy_box.currentData())
        except ValueError as error:
            QMessageBox.warning(self, "填写失败", str(error)); return
        QMessageBox.information(self, "填写完成", f"已另存到：\n{result.output_path}\n写入 {result.written_rows} 行，跳过 {result.skipped_rows} 行。")
