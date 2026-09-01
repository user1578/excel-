"""班级学生查看、选择与普通名单生成界面。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QDoubleSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.class_record import ClassRecord
from app.models.student import Student
from app.services.class_export_service import (
    CORE_LABELS, SOURCE_AUTO, SOURCE_BLANK, SOURCE_CORE, SOURCE_EXTRA, SOURCE_FIXED,
    ClassExportService, ExportColumn,
)
from app.services.data_workspace_service import DataWorkspaceService
from app.services.master_data_service import MasterDataService
from app.template_engine.styles import standard_office_style
from app.ui.dialogs.style_dialog import StyleDialog


class ClassStudentsDialog(QDialog):
    def __init__(self, service: MasterDataService, class_record: ClassRecord, workspace: DataWorkspaceService | None = None, open_fill=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service, self.class_record, self.workspace, self.open_fill = service, class_record, workspace, open_fill
        self.students = service.list_students_by_class(class_record.standard_name)
        self._selected_ids = {student.id for student in self.students if student.id is not None}
        self.setWindowTitle(f"查看学生：{class_record.standard_name}")
        self.resize(820, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"班级名称：{class_record.standard_name}    学生总数：{len(self.students)}"))
        bar = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索姓名、学号、专业或寝室")
        select_all, clear = QPushButton("全选"), QPushButton("取消全选")
        self.search.textChanged.connect(self.refresh)
        select_all.clicked.connect(lambda: self._set_visible_checked(True))
        clear.clicked.connect(lambda: self._set_visible_checked(False))
        bar.addWidget(self.search, 1); bar.addWidget(select_all); bar.addWidget(clear)
        layout.addLayout(bar)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["选择", "姓名", "学号", "专业", "年级", "联系电话", "寝室"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        quick, template = QPushButton("生成表格"), QPushButton("按模板生成")
        quick.clicked.connect(self.open_export)
        template.clicked.connect(self.open_template_fill)
        actions.addWidget(quick); actions.addWidget(template); actions.addStretch()
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(self.reject)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        self._persist_visible_selection()
        keyword = self.search.text().strip()
        visible = [item for item in self.students if not keyword or keyword in " ".join(str(getattr(item, key) or "") for key in ("name", "student_number", "major", "dormitory"))]
        self.table.setRowCount(len(visible))
        for row, student in enumerate(visible):
            pick = QTableWidgetItem(); pick.setCheckState(Qt.CheckState.Checked if student.id in self._selected_ids else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, pick)
            values = [student.name, student.student_number, student.major, student.grade, student.phone, student.dormitory]
            for column, value in enumerate(values, 1):
                item = QTableWidgetItem(value or "")
                if column == 1:
                    item.setData(256, student.id)
                self.table.setItem(row, column, item)

    def _set_visible_checked(self, state: bool) -> None:
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Checked if state else Qt.CheckState.Unchecked)
        self._persist_visible_selection()

    def _persist_visible_selection(self) -> None:
        for row in range(self.table.rowCount()):
            student_id = self.table.item(row, 1).data(256)
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked:
                self._selected_ids.add(student_id)
            else:
                self._selected_ids.discard(student_id)

    def selected_students(self) -> list[Student]:
        self._persist_visible_selection()
        return [student for student in self.students if student.id in self._selected_ids]

    def open_export(self) -> None:
        students = self.selected_students()
        if not students:
            QMessageBox.information(self, "请选择学生", "请先选择至少一名学生。")
            return
        ClassExportDialog(self.service, self.class_record.standard_name, students, self).exec()

    def open_template_fill(self) -> None:
        students = self.selected_students()
        if not students:
            QMessageBox.information(self, "请选择学生", "请先选择至少一名学生。")
            return
        if self.workspace is None:
            return
        self.workspace.set_dataset(ClassExportService(self.service).students_dataset(students, self.class_record.standard_name))
        if callable(self.open_fill):
            self.open_fill()
        self.accept()


class ClassExportDialog(QDialog):
    def __init__(self, service: MasterDataService, class_name: str, students: list[Student], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service, self.class_name, self.students = service, class_name, students
        self.exporter = ClassExportService(service)
        self.style = standard_office_style()
        self.setWindowTitle("生成班级表格")
        self.resize(860, 520)
        layout = QVBoxLayout(self)
        title_bar = QHBoxLayout()
        self.title_input = QLineEdit(); self.title_input.setPlaceholderText("可选：表格主标题")
        self.title_mode = QComboBox(); self.title_mode.addItem("不使用大标题", "none"); self.title_mode.addItem("使用默认标题", "default"); self.title_mode.addItem("自定义标题", "custom")
        self.title_mode.currentIndexChanged.connect(self._title_mode_changed)
        self.title_input.textChanged.connect(lambda text: self._select_custom_title_if_needed(text))
        self._title_mode_changed()
        title_bar.addWidget(QLabel("大标题")); title_bar.addWidget(self.title_mode); title_bar.addWidget(self.title_input, 1)
        layout.addLayout(title_bar)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["显示标题", "数据来源", "来源字段", "固定值", "列宽", "操作"])
        layout.addWidget(self.table, 1)
        controls = QHBoxLayout()
        add = QPushButton("添加列"); add.clicked.connect(self.add_column)
        save = QPushButton("保存方案"); save.clicked.connect(self.save_scheme)
        load = QPushButton("加载方案"); load.clicked.connect(self.load_scheme)
        delete = QPushButton("删除方案"); delete.clicked.connect(self.delete_scheme)
        generate = QPushButton("生成 Excel"); generate.clicked.connect(self.generate)
        style = QPushButton("表格样式"); style.clicked.connect(self.edit_style)
        for widget in (add, save, load, delete, style, generate): controls.addWidget(widget)
        controls.addStretch(); layout.addLayout(controls)
        for column in [ExportColumn("序号", SOURCE_AUTO), ExportColumn("姓名", SOURCE_CORE, "name"), ExportColumn("学号", SOURCE_CORE, "student_number"), ExportColumn("联系电话", SOURCE_CORE, "phone"), ExportColumn("参赛", SOURCE_BLANK), ExportColumn("备注", SOURCE_BLANK)]:
            self.add_column(column)

    def _field_options(self) -> dict[str, str]:
        options = dict(CORE_LABELS)
        for student in self.students:
            if student.id:
                options.update({f"extra:{key}": item["name"] for key, item in self.service.get_student_extra_fields(student.id).items()})
        return options

    def add_column(self, definition: ExportColumn | None = None) -> None:
        definition = definition or ExportColumn("新列", SOURCE_BLANK)
        row = self.table.rowCount(); self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(definition.title))
        source = QComboBox()
        for label, key in (("自动序号", SOURCE_AUTO), ("学生资料", SOURCE_CORE), ("扩展资料", SOURCE_EXTRA), ("空白字段", SOURCE_BLANK), ("固定内容", SOURCE_FIXED)):
            source.addItem(label, key)
        source.setCurrentIndex(max(0, source.findData(definition.source_type)))
        self.table.setCellWidget(row, 1, source)
        field = QComboBox(); field.addItem("-", "")
        for key, label in self._field_options().items():
            field.addItem(label, key.removeprefix("extra:"))
        field.setCurrentIndex(max(0, field.findData(definition.source_field)))
        self.table.setCellWidget(row, 2, field)
        self.table.setItem(row, 3, QTableWidgetItem(definition.fixed_value))
        width = QDoubleSpinBox(); width.setRange(0, 80); width.setValue(definition.column_width or 0); width.setSpecialValueText("自动")
        self.table.setCellWidget(row, 4, width)
        actions = QWidget(); bar = QHBoxLayout(actions); bar.setContentsMargins(2, 1, 2, 1)
        up, down, remove = QPushButton("↑"), QPushButton("↓"), QPushButton("删除")
        up.clicked.connect(lambda _checked=False, widget=actions: self._move_action_row(widget, -1))
        down.clicked.connect(lambda _checked=False, widget=actions: self._move_action_row(widget, 1))
        remove.clicked.connect(lambda _checked=False, widget=actions: self._remove_action_row(widget))
        for button in (up, down, remove): bar.addWidget(button)
        self.table.setCellWidget(row, 5, actions)

    def move_row(self, row: int, delta: int) -> None:
        target = row + delta
        if 0 <= target < self.table.rowCount():
            definitions = self.columns(); definitions[row], definitions[target] = definitions[target], definitions[row]
            self.table.setRowCount(0)
            for item in definitions: self.add_column(item)

    def _action_row(self, actions: QWidget) -> int:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 5) is actions:
                return row
        return -1

    def _move_action_row(self, actions: QWidget, delta: int) -> None:
        row = self._action_row(actions)
        if row >= 0:
            self.move_row(row, delta)

    def _remove_action_row(self, actions: QWidget) -> None:
        row = self._action_row(actions)
        if row >= 0:
            self.table.removeRow(row)

    def columns(self) -> list[ExportColumn]:
        result: list[ExportColumn] = []
        for row in range(self.table.rowCount()):
            result.append(ExportColumn(self.table.item(row, 0).text().strip(), self.table.cellWidget(row, 1).currentData(), self.table.cellWidget(row, 2).currentData() or "", self.table.item(row, 3).text(), self.table.cellWidget(row, 4).value() or None))
        return [item for item in result if item.title]

    def save_scheme(self) -> None:
        name, accepted = QInputDialog.getText(self, "保存方案", "方案名称：")
        if not accepted or not name.strip(): return
        try:
            self.exporter.save_scheme(name, self.title_input.text(), self.columns())
        except ValueError as error:
            QMessageBox.warning(self, "无法保存", str(error)); return
        QMessageBox.information(self, "已保存", "方案未包含任何学生个人资料。")

    def load_scheme(self) -> None:
        schemes = self.exporter.list_schemes()
        names = [item.name for item in schemes]
        name, accepted = QInputDialog.getItem(self, "加载方案", "选择方案：", names, editable=False)
        if not accepted: return
        scheme = next(item for item in schemes if item.name == name)
        self.title_input.setText(scheme.title); self.table.setRowCount(0)
        for item in scheme.configuration: self.add_column(ExportColumn(**item))

    def delete_scheme(self) -> None:
        schemes = self.exporter.list_schemes(); names = [item.name for item in schemes]
        name, accepted = QInputDialog.getItem(self, "删除方案", "选择方案：", names, editable=False)
        if accepted:
            self.exporter.delete_scheme(next(item.id for item in schemes if item.name == name))

    def _title_mode_changed(self) -> None:
        self.title_input.setEnabled(self.title_mode.currentData() == "custom")

    def _select_custom_title_if_needed(self, text: str) -> None:
        if text.strip() and self.title_mode.currentData() == "none":
            self.title_mode.setCurrentIndex(self.title_mode.findData("custom"))

    def _resolved_title(self) -> str:
        if self.title_mode.currentData() == "default":
            return f"{self.class_name}学生名单"
        return self.title_input.text().strip() if self.title_mode.currentData() == "custom" else ""

    def edit_style(self) -> None:
        dialog = StyleDialog(self.style, self)
        if dialog.exec():
            self.style = dialog.result_style()

    def generate(self) -> None:
        try:
            output = self.exporter.export(self.class_name, self.students, self.columns(), self._resolved_title(), self.style)
        except ValueError as error:
            QMessageBox.warning(self, "无法生成", str(error)); return
        QMessageBox.information(self, "生成完成", f"已另存到：\n{output}")
        self.accept()
