"""只读学生库的可筛选、多选对话框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit, QTableWidget, QTableWidgetItem, QVBoxLayout

from app.models.student import Student
from app.services.master_data_service import MasterDataService


class StudentSelectionDialog(QDialog):
    def __init__(self, master: MasterDataService, selected_students: list[Student] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.master = master
        self._selected_ids = {student.id for student in selected_students or [] if student.id is not None}
        self.setWindowTitle("选择学生")
        self.resize(680, 460)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("按姓名、学号或班级搜索")
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["选择", "姓名", "学号", "班级"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._remember_selection)
        layout.addWidget(self.table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self) -> None:
        students = self.master.search_students(self.search.text())
        self.table.blockSignals(True)
        self.table.setRowCount(len(students))
        for row, student in enumerate(students):
            selected = QTableWidgetItem()
            selected.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            selected.setCheckState(Qt.CheckState.Checked if student.id in self._selected_ids else Qt.CheckState.Unchecked)
            selected.setData(Qt.ItemDataRole.UserRole, student.id)
            self.table.setItem(row, 0, selected)
            self.table.setItem(row, 1, QTableWidgetItem(student.name))
            self.table.setItem(row, 2, QTableWidgetItem(student.student_number))
            self.table.setItem(row, 3, QTableWidgetItem(student.class_name))
        self.table.blockSignals(False)

    def _remember_selection(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        student_id = item.data(Qt.ItemDataRole.UserRole)
        if student_id is None:
            return
        if item.checkState() == Qt.CheckState.Checked:
            self._selected_ids.add(student_id)
        else:
            self._selected_ids.discard(student_id)

    def selected_students(self) -> list[Student]:
        return [student for student in self.master.list_students() if student.id in self._selected_ids]
