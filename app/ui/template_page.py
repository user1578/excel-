"""手动模板编辑、AI 方案预览及本地模板管理页面。"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QDoubleSpinBox, QInputDialog, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from app.ai.deepseek_parser import DeepSeekParser
from app.models.field_mapping import FIELD_LABELS, StandardField
from app.services.template_service import TemplateService
from app.template_engine.schema import FIELD_TYPE_LABELS, FIELD_TYPES, FieldSchema, SheetSchema, TemplateSchema, core_field_schema
from app.template_engine.styles import standard_office_style
from app.ui.dialogs.style_dialog import StyleDialog


class FieldEditor(QDialog):
    def __init__(self, parent=None, field: FieldSchema | None = None):
        super().__init__(parent)
        self.setWindowTitle("字段配置")
        self.field = field or FieldSchema("新字段")
        layout = QVBoxLayout(self); form = QFormLayout()
        self.name = QLineEdit(self.field.name)
        self.type_box = QComboBox()
        for item in FIELD_TYPES: self.type_box.addItem(FIELD_TYPE_LABELS[item], item)
        self.type_box.setCurrentIndex(max(0, self.type_box.findData(self.field.field_type)))
        self.required = QCheckBox(); self.required.setChecked(self.field.required)
        self.default = QLineEdit(self.field.default_value or "")
        self.options = QLineEdit(",".join(self.field.options))
        self.formula = QLineEdit(self.field.formula or "")
        self.description = QLineEdit(self.field.description or "")
        self.standard = QComboBox(); self.standard.addItem("自定义字段", None)
        for standard in StandardField:
            if standard not in {StandardField.IGNORE, StandardField.OTHER, StandardField.SEQUENCE}:
                self.standard.addItem(FIELD_LABELS[standard], standard.value)
        self.standard.setCurrentIndex(max(0, self.standard.findData(self.field.standard_field)))
        self.allow_blank = QCheckBox(); self.allow_blank.setChecked(self.field.allow_blank)
        self.column_width = QDoubleSpinBox(); self.column_width.setRange(0, 80); self.column_width.setValue(self.field.column_width or 0); self.column_width.setSpecialValueText("自动")
        for label, widget in (("字段名称", self.name), ("字段类型", self.type_box), ("必填", self.required), ("默认值", self.default), ("下拉选项（逗号分隔）", self.options), ("公式", self.formula), ("提示说明", self.description), ("标准字段", self.standard), ("允许为空", self.allow_blank), ("列宽（自动/5-80）", self.column_width)): form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def result_field(self) -> FieldSchema:
        return FieldSchema(self.name.text().strip(), self.type_box.currentData(), self.required.isChecked(), self.default.text() or None, [item.strip() for item in self.options.text().split(",") if item.strip()], None, self.formula.text().strip() or None, self.description.text().strip() or None, self.standard.currentData(), self.allow_blank.isChecked(), self.column_width.value() or None)


class TemplatePage(QWidget):
    def __init__(self, service: TemplateService, parser: DeepSeekParser, parent=None):
        super().__init__(parent)
        self.service, self.parser = service, parser
        self.fields: list[FieldSchema] = []
        self.style = standard_office_style()
        root = QVBoxLayout(self); root.setContentsMargins(36, 32, 36, 32)
        root.addWidget(QLabel("模板生成", objectName="pageTitle"))
        splitter = QSplitter(); splitter.addWidget(self._build_editor()); splitter.addWidget(self._build_management()); splitter.setSizes([850, 330])
        root.addWidget(splitter, 1)
        self.refresh()

    def _build_editor(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page)
        form = QFormLayout()
        self.name = QLineEdit(); self.sheet_name = QLineEdit("数据录入"); self.description = QLineEdit(); self.rows = QSpinBox(); self.rows.setRange(1, 10000); self.rows.setValue(100)
        self.student_related = QCheckBox("学生相关模板（默认补充姓名、学号、班级）")
        self.student_related.toggled.connect(self._student_related_changed)
        form.addRow("模板名称", self.name); form.addRow("工作表名称", self.sheet_name); form.addRow("备注", self.description); form.addRow("预生成空白行数", self.rows); form.addRow("", self.student_related)
        layout.addLayout(form)
        style_button = QPushButton("表格样式（默认：标准办公表格）")
        style_button.clicked.connect(self.edit_style)
        layout.addWidget(style_button)
        field_bar = QHBoxLayout(); self.standard_box = QComboBox()
        for standard in StandardField:
            if standard not in {StandardField.IGNORE, StandardField.OTHER, StandardField.SEQUENCE}: self.standard_box.addItem(FIELD_LABELS[standard], standard)
        add_standard = QPushButton("添加标准字段"); add_custom = QPushButton("新增自定义字段"); edit = QPushButton("编辑字段"); up = QPushButton("上移"); down = QPushButton("下移"); remove = QPushButton("删除")
        add_standard.clicked.connect(self.add_standard); add_custom.clicked.connect(self.add_custom); edit.clicked.connect(self.edit_field); up.clicked.connect(lambda: self.move_field(-1)); down.clicked.connect(lambda: self.move_field(1)); remove.clicked.connect(self.remove_field)
        field_bar.addWidget(self.standard_box); [field_bar.addWidget(button) for button in (add_standard, add_custom, edit, up, down, remove)]; field_bar.addStretch(); layout.addLayout(field_bar)
        self.field_table = QTableWidget(0, 8); self.field_table.setHorizontalHeaderLabels(["字段名称", "类型", "必填", "默认值", "下拉选项", "公式", "列宽", "说明"]); self.field_table.horizontalHeader().setStretchLastSection(True); self.field_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); layout.addWidget(self.field_table, 1)
        layout.addWidget(QLabel("AI 生成方案（只生成 Schema，需在上方确认或修改后再生成 Excel）"))
        self.ai_input = QTextEdit(); self.ai_input.setPlaceholderText("例如：给我做一个9月份课堂查课表，要姓名、学号、班级、日期、课程、应到、实到和到课率。")
        layout.addWidget(self.ai_input)
        self.ai_generate_button = QPushButton("生成 AI 方案")
        self.ai_generate_button.clicked.connect(self.generate_ai_schema)
        self.ai_status = QLabel("")
        self.ai_status.setObjectName("subtitle")
        layout.addWidget(self.ai_generate_button)
        layout.addWidget(self.ai_status)
        actions = QHBoxLayout(); new = QPushButton("新建模板"); generate = QPushButton("生成 Excel 模板"); new.clicked.connect(self.new_template); generate.clicked.connect(self.generate_template); actions.addWidget(new); actions.addStretch(); actions.addWidget(generate); layout.addLayout(actions)
        return page

    def _build_management(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel("已有模板", objectName="sectionTitle"))
        self.template_table = QTableWidget(0, 2); self.template_table.setHorizontalHeaderLabels(["名称", "文件"]); self.template_table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.template_table, 1)
        for label, callback in (("打开并编辑", self.open_selected), ("复制", self.copy_selected), ("删除", self.delete_selected), ("刷新", self.refresh)):
            button = QPushButton(label); button.clicked.connect(callback); layout.addWidget(button)
        return page

    def refresh(self):
        artifacts = self.service.list(); self.template_table.setRowCount(len(artifacts))
        for row, artifact in enumerate(artifacts):
            self.template_table.setItem(row, 0, QTableWidgetItem(artifact.name)); self.template_table.setItem(row, 1, QTableWidgetItem(artifact.workbook_path.name))

    def new_template(self):
        self.name.clear(); self.sheet_name.setText("数据录入"); self.description.clear(); self.rows.setValue(100); self.student_related.blockSignals(True); self.student_related.setChecked(False); self.student_related.blockSignals(False); self.fields = []; self.style = standard_office_style(); self._render_fields()

    def edit_style(self):
        dialog = StyleDialog(self.style, self)
        if dialog.exec():
            self.style = dialog.result_style()

    def _student_related_changed(self, selected: bool):
        if selected:
            existing = {field.standard_field for field in self.fields}
            self.fields = [core_field_schema(item) for item in (StandardField.NAME.value, StandardField.STUDENT_NUMBER.value, StandardField.CLASS_NAME.value) if item not in existing] + self.fields
            self._render_fields()

    def add_standard(self):
        standard = self.standard_box.currentData()
        defaults = {StandardField.NAME: "name", StandardField.STUDENT_NUMBER: "student_number", StandardField.CLASS_NAME: "class_name", StandardField.DORMITORY: "dormitory"}
        field = FieldSchema(FIELD_LABELS[standard], defaults.get(standard, "text"), standard in {StandardField.NAME, StandardField.STUDENT_NUMBER, StandardField.CLASS_NAME}, None, [], "classes" if standard is StandardField.CLASS_NAME else "dormitories" if standard is StandardField.DORMITORY else None, None, None, standard.value, standard not in {StandardField.NAME, StandardField.STUDENT_NUMBER, StandardField.CLASS_NAME})
        self.fields.append(field); self._render_fields()

    def add_custom(self):
        dialog = FieldEditor(self)
        if dialog.exec(): self.fields.append(dialog.result_field()); self._render_fields()

    def edit_field(self):
        row = self.field_table.currentRow()
        if row < 0: return
        dialog = FieldEditor(self, self.fields[row])
        if dialog.exec(): self.fields[row] = dialog.result_field(); self._render_fields()

    def move_field(self, step: int):
        row = self.field_table.currentRow(); target = row + step
        if row < 0 or target < 0 or target >= len(self.fields): return
        self.fields[row], self.fields[target] = self.fields[target], self.fields[row]; self._render_fields(); self.field_table.selectRow(target)

    def remove_field(self):
        row = self.field_table.currentRow()
        if row >= 0: self.fields.pop(row); self._render_fields()

    def _render_fields(self):
        self.field_table.setRowCount(len(self.fields))
        for row, field in enumerate(self.fields):
            values = (field.name, FIELD_TYPE_LABELS[field.field_type], "是" if field.required else "否", field.default_value or "", ", ".join(field.options) or ({"classes": "班级库", "dormitories": "寝室库"}.get(field.data_source, "")), field.formula or "", str(field.column_width or "自动"), field.description or "")
            for column, value in enumerate(values): self.field_table.setItem(row, column, QTableWidgetItem(value))

    def _schema(self) -> TemplateSchema:
        return TemplateSchema(self.name.text().strip(), self.student_related.isChecked(), self.description.text().strip() or None, self.rows.value(), [SheetSchema(self.sheet_name.text().strip(), list(self.fields))], self.style)

    def generate_template(self):
        style = self._style_for_generation()
        if style is None:
            return
        self.style = style
        try: artifact = self.service.create(replace(self._schema(), style=style))
        except ValueError as error: QMessageBox.warning(self, "无法生成", str(error)); return
        QMessageBox.information(self, "生成完成", f"模板已生成：{artifact.workbook_path}"); self.refresh()

    def _style_for_generation(self):
        if self.style.title_mode != "ask":
            return self.style
        dialog = QMessageBox(self)
        dialog.setWindowTitle("添加大标题")
        dialog.setText("是否在第一行添加合并大标题？")
        add = dialog.addButton("添加", QMessageBox.ButtonRole.AcceptRole)
        omit = dialog.addButton("不添加", QMessageBox.ButtonRole.DestructiveRole)
        dialog.addButton("取消生成", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is add:
            choice, accepted = QInputDialog.getItem(self, "大标题内容", "标题：", ["使用模板名称", "自定义标题"], editable=False)
            if not accepted:
                return None
            if choice == "使用模板名称":
                return replace(self.style, title_mode="template_name", show_main_title=True, main_title="")
            title, accepted = QInputDialog.getText(self, "自定义标题", "标题文本：")
            if not accepted:
                return None
            return replace(self.style, title_mode="custom", show_main_title=True, main_title=title.strip())
        if dialog.clickedButton() is omit:
            return replace(self.style, title_mode="none", show_main_title=False, main_title="")
        return None

    def generate_ai_schema(self):
        self.ai_generate_button.setEnabled(False)
        self.ai_status.setText("正在生成模板……")
        QApplication.processEvents()
        try:
            schema = self.parser.generate_schema(self.ai_input.toPlainText())
        except Exception as error:
            self.ai_status.setText("AI 方案生成失败。")
            QMessageBox.warning(self, "AI 生成失败", str(error))
        else:
            self._load_schema(schema)
            self.ai_status.setText("AI 方案已生成，请确认后再生成 Excel 模板。")
            QMessageBox.information(self, "AI 方案已生成", "请检查并修改字段后，再点击“生成 Excel 模板”。")
        finally:
            self.ai_generate_button.setEnabled(True)

    def _load_schema(self, schema: TemplateSchema):
        self.name.setText(schema.template_name); self.description.setText(schema.description or ""); self.rows.setValue(schema.default_rows); self.sheet_name.setText(schema.sheets[0].name); self.student_related.blockSignals(True); self.student_related.setChecked(schema.student_related); self.student_related.blockSignals(False); self.fields = list(schema.sheets[0].fields); self.style = schema.style; self._render_fields()

    def _selected_name(self) -> str | None:
        row = self.template_table.currentRow(); return self.template_table.item(row, 0).text() if row >= 0 and self.template_table.item(row, 0) else None

    def open_selected(self):
        name = self._selected_name()
        if not name: return
        try: self._load_schema(self.service.load(name))
        except ValueError as error: QMessageBox.warning(self, "打开失败", str(error))

    def copy_selected(self):
        name = self._selected_name()
        if not name: return
        self.service.copy(name); self.refresh()

    def delete_selected(self):
        name = self._selected_name()
        if not name: return
        if QMessageBox.question(self, "确认删除", f"确定删除模板“{name}”及其 xlsx、schema.json 吗？") != QMessageBox.StandardButton.Yes: return
        self.service.delete(name); self.refresh()
