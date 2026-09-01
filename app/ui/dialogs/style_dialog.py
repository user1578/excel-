"""新生成工作簿的样式配置；不作用于已有模板填充。"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QVBoxLayout

from app.template_engine.styles import STYLE_PRESETS, WorkbookStyleSchema, preset_style


class StyleDialog(QDialog):
    def __init__(self, style: WorkbookStyleSchema, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("表格样式")
        self.resize(460, 650)
        self._style = style
        layout = QVBoxLayout(self); form = QFormLayout()
        self.preset = QComboBox(); self.preset.addItems(STYLE_PRESETS); self.preset.setCurrentText(style.preset)
        self.font_name = QLineEdit(style.overall_font_name); self.font_size = self._spin(style.overall_font_size, 6, 72)
        self.show_title = self._check(style.show_main_title); self.title = QLineEdit(style.main_title); self.title_size = self._spin(style.title_font_size, 6, 72); self.title_bold = self._check(style.title_bold); self.title_height = self._double(style.title_row_height, 12, 120); self.title_align = self._alignment(style.title_horizontal_alignment)
        self.header_fill = self._check(style.header_fill_enabled); self.header_color = QLineEdit(style.header_fill_color); self.header_font_color = QLineEdit(style.header_font_color); self.header_bold = self._check(style.header_bold); self.header_height = self._double(style.header_row_height, 12, 120); self.header_align = self._alignment(style.header_horizontal_alignment); self.header_wrap = self._check(style.header_wrap_text)
        self.border_enabled = self._check(style.border_enabled); self.border_color = QLineEdit(style.border_color); self.border_style = QComboBox(); self.border_style.addItems(["thin", "medium", "thick"]); self.border_style.setCurrentText(style.border_style)
        self.body_height = self._double(style.body_row_height, 12, 120); self.body_align = self._alignment(style.body_horizontal_alignment); self.body_wrap = self._check(style.body_wrap_text)
        self.freeze = self._check(style.freeze_header); self.filter = self._check(style.auto_filter); self.gridlines = self._check(style.show_gridlines)
        self.default_width = self._double(style.default_column_width or 0, 0, 80); self.required_display = QComboBox(); self.required_display.addItems(["none", "asterisk", "header_color", "cell_fill"]); self.required_display.setCurrentText(style.required_display)
        for label, widget in (("样式预设", self.preset), ("整体字体", self.font_name), ("整体字号", self.font_size), ("启用主标题", self.show_title), ("主标题文本", self.title), ("标题字号", self.title_size), ("标题加粗", self.title_bold), ("标题行高", self.title_height), ("标题对齐", self.title_align), ("表头填充", self.header_fill), ("表头填充色（RRGGBB）", self.header_color), ("表头字体色（RRGGBB）", self.header_font_color), ("表头加粗", self.header_bold), ("表头行高", self.header_height), ("表头对齐", self.header_align), ("表头换行", self.header_wrap), ("边框", self.border_enabled), ("边框色（RRGGBB）", self.border_color), ("边框粗细", self.border_style), ("数据行高", self.body_height), ("数据对齐", self.body_align), ("数据换行", self.body_wrap), ("冻结表头", self.freeze), ("自动筛选", self.filter), ("显示网格线", self.gridlines), ("默认列宽（0=自动）", self.default_width), ("必填提示", self.required_display)):
            form.addRow(label, widget)
        layout.addLayout(form)
        self.preset.currentTextChanged.connect(self._apply_preset)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    @staticmethod
    def _check(value: bool) -> QCheckBox:
        widget = QCheckBox(); widget.setChecked(value); return widget

    @staticmethod
    def _spin(value: int, low: int, high: int) -> QSpinBox:
        widget = QSpinBox(); widget.setRange(low, high); widget.setValue(value); return widget

    @staticmethod
    def _double(value: float, low: float, high: float) -> QDoubleSpinBox:
        widget = QDoubleSpinBox(); widget.setRange(low, high); widget.setValue(value); return widget

    @staticmethod
    def _alignment(value: str) -> QComboBox:
        widget = QComboBox(); widget.addItems(["left", "center", "right"]); widget.setCurrentText(value); return widget

    def _apply_preset(self, name: str) -> None:
        if name == "自定义":
            return
        value = preset_style(name)
        self.font_name.setText(value.overall_font_name); self.font_size.setValue(value.overall_font_size)
        self.header_fill.setChecked(value.header_fill_enabled); self.header_color.setText(value.header_fill_color); self.header_font_color.setText(value.header_font_color); self.header_bold.setChecked(value.header_bold)
        self.border_enabled.setChecked(value.border_enabled); self.border_color.setText(value.border_color); self.border_style.setCurrentText(value.border_style)
        self.gridlines.setChecked(value.show_gridlines); self.required_display.setCurrentText(value.required_display)

    def result_style(self) -> WorkbookStyleSchema:
        value = WorkbookStyleSchema(
            preset=self.preset.currentText(), overall_font_name=self.font_name.text().strip() or "宋体", overall_font_size=self.font_size.value(),
            show_main_title=self.show_title.isChecked(), main_title=self.title.text().strip(), title_font_name=self.font_name.text().strip() or "宋体", title_font_size=self.title_size.value(), title_bold=self.title_bold.isChecked(), title_horizontal_alignment=self.title_align.currentText(), title_row_height=self.title_height.value(),
            header_fill_enabled=self.header_fill.isChecked(), header_fill_color=self.header_color.text().strip() or "FFFFFF", header_font_color=self.header_font_color.text().strip() or "000000", header_font_size=self.font_size.value(), header_bold=self.header_bold.isChecked(), header_horizontal_alignment=self.header_align.currentText(), header_row_height=self.header_height.value(), header_wrap_text=self.header_wrap.isChecked(),
            body_font_size=self.font_size.value(), body_horizontal_alignment=self.body_align.currentText(), body_row_height=self.body_height.value(), body_wrap_text=self.body_wrap.isChecked(),
            border_enabled=self.border_enabled.isChecked(), border_color=self.border_color.text().strip() or "000000", border_style=self.border_style.currentText(), show_gridlines=self.gridlines.isChecked(), freeze_header=self.freeze.isChecked(), auto_filter=self.filter.isChecked(), default_column_width=self.default_width.value() or None, required_display=self.required_display.currentText(),
        )
        value.validate()
        return value
