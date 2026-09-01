"""表格填充页面：分析模板、选择来源、映射和另存输出。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from app.models.table_dataset import Provenance, TableDataset, TableRow
from app.parsers.workbook_template_analyzer import WorkbookTemplateAnalyzer
from app.services.data_workspace_service import DataWorkspaceService
from app.services.table_analysis_service import TableAnalysisService
from app.services.workbook_fill_service import AUTO_SEQUENCE, KEEP_EXISTING, SEQUENCE_FILL_BLANK, SEQUENCE_NONE, SEQUENCE_RENUMBER, SKIP_CONFLICTING_ROW, USE_NEW_VALUE, WorkbookFillService
from app.services.class_export_service import ClassExportService
from app.services.legacy_excel_converter import LegacyExcelConversionError, LegacyExcelConverter
from app.services.text_dataset_service import TextDatasetParseError, TextDatasetService
from app.ai.deepseek_client import DeepSeekClient, DeepSeekClientError, DeepSeekConfig


class WorkbookFillPage(QWidget):
    def __init__(self, workspace: DataWorkspaceService, master, parent=None) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.master = master
        self.template_analyzer = WorkbookTemplateAnalyzer()
        self.table_analyzer = TableAnalysisService()
        self.fill_service = WorkbookFillService()
        self.legacy_converter = LegacyExcelConverter()
        self.template_path: Path | None = None
        self.original_template_path: Path | None = None
        self.analysis = None
        self.dataset: TableDataset | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(QLabel("表格填充", objectName="pageTitle"))
        layout.addWidget(QLabel("支持 .xlsx 和旧版 .xls 模板；.xls 仅转换为临时 .xlsx 工作副本，原模板始终不改动。用户文本会安全转义，程序公式保持为公式。"))
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
        self.source_box.addItems(["当前资料汇总结果", "单独选择 xlsx/csv", "学生库", "班级学生", "粘贴文本", "TXT 文件"])
        choose_source = QPushButton("选择数据源")
        choose_source.clicked.connect(self.choose_source)
        self.source_label = QLabel("尚未选择数据源")
        source_bar.addWidget(QLabel("数据源")); source_bar.addWidget(self.source_box); source_bar.addWidget(choose_source); source_bar.addWidget(self.source_label, 1)
        layout.addLayout(source_bar)
        layout.addWidget(QLabel("字段映射", objectName="sectionTitle"))
        self.mapping_table = QTableWidget(0, 2)
        self.mapping_table.setHorizontalHeaderLabels(["模板字段", "数据源字段"])
        layout.addWidget(self.mapping_table, 1)
        self.sequence_bar = QHBoxLayout()
        self.sequence_notice = QLabel("")
        self.sequence_enabled = QCheckBox("自动补齐序号")
        self.sequence_start = QSpinBox(); self.sequence_start.setRange(1, 999999); self.sequence_start.setValue(1)
        self.sequence_mode = QComboBox(); self.sequence_mode.addItem("仅补空白", SEQUENCE_FILL_BLANK); self.sequence_mode.addItem("重新连续编号", SEQUENCE_RENUMBER); self.sequence_mode.addItem("不处理", SEQUENCE_NONE)
        self.sequence_enabled.toggled.connect(self._toggle_detected_sequence)
        self.sequence_mode.currentIndexChanged.connect(lambda _index: self._update_sequence_state())
        self.sequence_bar.addWidget(self.sequence_notice); self.sequence_bar.addWidget(self.sequence_enabled); self.sequence_bar.addWidget(QLabel("起始序号")); self.sequence_bar.addWidget(self.sequence_start); self.sequence_bar.addWidget(QLabel("处理方式")); self.sequence_bar.addWidget(self.sequence_mode); self.sequence_bar.addStretch()
        layout.addLayout(self.sequence_bar)
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
        text, _ = QFileDialog.getOpenFileName(self, "选择 Excel 模板", "", "Excel 模板 (*.xlsx *.xls)")
        if not text: return
        original = Path(text)
        try:
            working_copy = self.legacy_converter.convert(original) if self.legacy_converter.is_legacy_template(original) else original
        except LegacyExcelConversionError as error:
            QMessageBox.warning(self, "旧版模板不可用", str(error)); return
        self.template_path = working_copy
        self.original_template_path = original
        try:
            sheets = self.template_analyzer.sheets(self.template_path)
        except ValueError as error:
            self.template_path = self.original_template_path = None
            QMessageBox.warning(self, "模板不可用", str(error)); return
        self.template_label.setText(original.name + ("（已安全转换为临时 .xlsx 副本）" if working_copy != original else ""))
        self.sheet_box.clear(); self.sheet_box.addItems(sheets)
        self.analysis = None
        self._update_sequence_state()

    def analyze_template(self) -> None:
        if self.template_path is None or not self.sheet_box.currentText():
            QMessageBox.information(self, "请选择模板", "请先选择一个 Excel 模板。"); return
        try:
            self.analysis = self.template_analyzer.analyze(self.template_path, self.sheet_box.currentText(), self.header_spin.value() or None)
        except ValueError as error:
            QMessageBox.warning(self, "模板分析失败", str(error)); return
        explicit = self._detected_sequence_target()
        self.message.setText(f"模板已分析：{len(self.analysis.target_columns)} 个可映射字段。" + (f" 检测到模板包含“{explicit}”列。" if explicit else ""))
        self._refresh_mapping_table()

    def choose_source(self) -> None:
        choice = self.source_box.currentText()
        if choice == "当前资料汇总结果":
            if self.workspace.current_dataset is None:
                QMessageBox.information(self, "没有数据集", "请先完成资料汇总，或从班级库按模板生成。"); return
            self.dataset = self.workspace.current_dataset
        elif choice == "学生库":
            self.dataset = ClassExportService(self.master).students_dataset(self.master.list_students(), "学生库")
        elif choice == "班级学生":
            classes = self.master.list_classes()
            name, accepted = QInputDialog.getItem(self, "选择班级", "班级：", [item.standard_name for item in classes], editable=False)
            if not accepted:
                return
            self.dataset = ClassExportService(self.master).students_dataset(self.master.list_students_by_class(name), name)
        elif choice == "粘贴文本":
            dialog = TextSourceDialog(TextDatasetService(), self)
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            self.dataset = dialog.dataset
        elif choice == "TXT 文件":
            text, _ = QFileDialog.getOpenFileName(self, "选择 TXT 数据源", "", "文本文件 (*.txt)")
            if not text: return
            try:
                parsed = TextDatasetService().parse_file(text)
            except TextDatasetParseError as error:
                QMessageBox.warning(self, "文本解析失败", str(error)); return
            dialog = TextSourceDialog(TextDatasetService(), self, parsed)
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            self.dataset = dialog.dataset
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
            box.addItem("自动序号", AUTO_SEQUENCE)
            for key in self.dataset.columns:
                box.addItem(self.dataset.display_label(key), key)
            if target in defaults:
                box.setCurrentIndex(box.findData(defaults[target]))
            box.currentIndexChanged.connect(lambda _index: self._update_sequence_state())
            self.mapping_table.setCellWidget(row, 1, box)
        self._update_sequence_state()

    def _mappings(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in range(self.mapping_table.rowCount()):
            target = self.mapping_table.item(row, 0).text()
            key = self.mapping_table.cellWidget(row, 1).currentData()
            if key is not None: result[target] = key
        return result

    def _detected_sequence_target(self) -> str | None:
        if self.analysis is None:
            return None
        return next((target for target in self.analysis.target_columns if target in {"序号", "序", "编号"}), None)

    def _toggle_detected_sequence(self, enabled: bool) -> None:
        target = self._detected_sequence_target()
        if target is None:
            return
        for row in range(self.mapping_table.rowCount()):
            if self.mapping_table.item(row, 0).text() == target:
                box = self.mapping_table.cellWidget(row, 1)
                box.setCurrentIndex(box.findData(AUTO_SEQUENCE if enabled else None))
                break

    def _update_sequence_state(self) -> None:
        mappings = self._mappings() if self.mapping_table.rowCount() else {}
        target = next((name for name, source in mappings.items() if source == AUTO_SEQUENCE), None)
        detected = self._detected_sequence_target()
        self.sequence_notice.setText(f"检测到模板包含“{detected}”列。" if detected else (f"自动序号目标列：{target}" if target else ""))
        self.sequence_enabled.blockSignals(True)
        self.sequence_enabled.setChecked(target is not None)
        self.sequence_enabled.blockSignals(False)
        active = target is not None
        self.sequence_enabled.setEnabled(detected is not None)
        self.sequence_start.setEnabled(active)
        self.sequence_mode.setEnabled(active)

    def preview(self) -> None:
        if self.analysis is None or self.dataset is None:
            QMessageBox.information(self, "信息不完整", "请先分析模板并选择数据源。"); return
        try:
            result = self.fill_service.preview(self.analysis, self.dataset, self._mappings(), self.sequence_start.value(), self.sequence_mode.currentData())
        except ValueError as error:
            QMessageBox.warning(self, "无法预览", str(error)); return
        warning = f"；合并单元格风险 {len(result.merged_cell_warnings)} 项" if result.merged_cell_warnings else ""
        sequence = f"；自动序号：是，目标列 {result.sequence_target}，起始值 {result.sequence_start}" if result.sequence_target else "；自动序号：否"
        self.message.setText(f"数据行：{result.row_count}；字段映射：{len(result.mappings)}；模板已有值冲突 {result.existing_value_conflicts} 个{sequence}{warning}。")

    def output(self) -> None:
        if self.analysis is None or self.dataset is None:
            QMessageBox.information(self, "信息不完整", "请先分析模板并选择数据源。"); return
        try:
            result = self.fill_service.fill(self.analysis, self.dataset, self._mappings(), self.strategy_box.currentData(), self.sequence_start.value(), self.sequence_mode.currentData())
        except ValueError as error:
            QMessageBox.warning(self, "填写失败", str(error)); return
        QMessageBox.information(self, "填写完成", f"已另存到：\n{result.output_path}\n写入 {result.written_rows} 行，跳过 {result.skipped_rows} 行。")


class TextSourceDialog(QDialog):
    """本地解析后显示字段、行数与预览，确认前不改变页面数据源。"""
    def __init__(self, parser: TextDatasetService, parent=None, initial_dataset: TableDataset | None = None) -> None:
        super().__init__(parent)
        self.parser, self.dataset = parser, initial_dataset
        self.setWindowTitle("粘贴文本")
        self.resize(720, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("支持 TSV（第一行为表头）或键值记录（空行分隔）。内容仅在本机解析。"))
        self.editor = QTextEdit(); self.editor.setPlaceholderText("在此粘贴文本…")
        layout.addWidget(self.editor, 1)
        parse = QPushButton("解析并预览"); parse.clicked.connect(self.parse)
        layout.addWidget(parse)
        config = DeepSeekConfig.load()
        if config.enabled and config.api_key and config.base_url:
            ai_parse = QPushButton("AI 结构化解析")
            ai_parse.clicked.connect(self.parse_with_ai)
            layout.addWidget(ai_parse)
        self.message = QLabel("尚未解析")
        layout.addWidget(self.message)
        self.preview = QTableWidget(0, 0); self.preview.setMaximumHeight(160)
        layout.addWidget(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if self.dataset is not None:
            self._show_dataset()

    def parse(self) -> None:
        try:
            self.dataset = self.parser.parse_text(self.editor.toPlainText())
        except TextDatasetParseError as error:
            QMessageBox.warning(self, "文本解析失败", str(error)); return
        self._show_dataset()

    def parse_with_ai(self) -> None:
        text = self.editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "请输入文本", "只会发送您在当前输入框明确粘贴的文本。")
            return
        try:
            raw = DeepSeekClient().request_table_dataset_json(text)
            self.dataset = self.parser.parse_ai_json(raw)
        except (DeepSeekClientError, TextDatasetParseError) as error:
            QMessageBox.warning(self, "AI 解析失败", str(error)); return
        self._show_dataset()

    def _show_dataset(self) -> None:
        self.preview.setColumnCount(len(self.dataset.columns)); self.preview.setRowCount(min(10, len(self.dataset.rows)))
        self.preview.setHorizontalHeaderLabels([self.dataset.display_label(key) for key in self.dataset.columns])
        for row, item in enumerate(self.dataset.rows[:10]):
            for column, key in enumerate(self.dataset.columns): self.preview.setItem(row, column, QTableWidgetItem(str(item.values.get(key, ""))))
        self.message.setText(f"识别字段 {len(self.dataset.columns)} 个，数据 {len(self.dataset.rows)} 行；确认后才作为填充数据源。")

    def accept(self) -> None:
        if self.dataset is None:
            QMessageBox.information(self, "请先解析", "请先解析并检查预览。")
            return
        super().accept()
