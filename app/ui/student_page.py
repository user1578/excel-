"""学生库维护页面。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.student import Student
from app.services.master_data_service import DuplicateStudentNumberError, MasterDataService
from app.ui.dialogs.student_dialog import StudentDialog


class StudentPage(QWidget):
    data_changed = Signal()

    def __init__(self, service: MasterDataService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._students: list[Student] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(14)

        title = QLabel("学生库")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入姓名、学号或班级搜索")
        self.search_input.returnPressed.connect(self.refresh)
        search_button = QPushButton("搜索")
        reset_button = QPushButton("重置")
        add_button = QPushButton("新增学生")
        refresh_button = QPushButton("刷新")
        search_button.clicked.connect(self.refresh)
        reset_button.clicked.connect(self.reset_search)
        add_button.clicked.connect(self.add_student)
        refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(search_button)
        toolbar.addWidget(reset_button)
        toolbar.addStretch()
        toolbar.addWidget(add_button)
        toolbar.addWidget(refresh_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["姓名", "学号", "班级", "专业", "年级", "联系电话", "寝室", "备注", "操作"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        for column, width in enumerate((90, 125, 135, 120, 75, 125, 110, 180)):
            self.table.setColumnWidth(column, width)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        try:
            self._students = self.service.search_students(self.search_input.text())
        except Exception:
            QMessageBox.critical(self, "读取失败", "读取学生数据失败，请检查数据库后重试。")
            return
        self.table.setRowCount(len(self._students))
        for row, student in enumerate(self._students):
            values = [student.name, student.student_number, student.class_name, student.major, student.grade,
                      student.phone, student.dormitory, student.remark]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value or "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, item)
            self.table.setCellWidget(row, 8, self._create_actions(student))

    def reset_search(self) -> None:
        self.search_input.clear()
        self.refresh()

    def add_student(self) -> None:
        if not self.service.list_classes():
            QMessageBox.information(self, "请先建立班级", "当前没有班级数据，请先在班级库新增班级。")
            return
        dialog = StudentDialog(self.service, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.service.create_student(dialog.to_model())
        except DuplicateStudentNumberError as error:
            QMessageBox.warning(self, "学号重复", str(error))
            return
        except ValueError as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return
        except Exception:
            QMessageBox.critical(self, "保存失败", "保存学生信息失败，请稍后重试。")
            return
        self.refresh()
        self.data_changed.emit()

    def edit_student(self, student: Student) -> None:
        dialog = StudentDialog(self.service, student, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.service.update_student(student.id, dialog.to_model())
        except DuplicateStudentNumberError as error:
            QMessageBox.warning(self, "学号重复", str(error))
            return
        except ValueError as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return
        except Exception:
            QMessageBox.critical(self, "保存失败", "更新学生信息失败，请稍后重试。")
            return
        self.refresh()
        self.data_changed.emit()

    def delete_student(self, student: Student) -> None:
        if QMessageBox.question(
            self,
            "确认删除",
            f"确定删除学生“{student.name}（{student.student_number}）”吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_student(student.id)
        except Exception:
            QMessageBox.critical(self, "删除失败", "删除学生信息失败，请稍后重试。")
            return
        self.refresh()
        self.data_changed.emit()

    def _create_actions(self, student: Student) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        edit_button = QPushButton("编辑")
        delete_button = QPushButton("删除")
        edit_button.clicked.connect(lambda _checked=False, item=student: self.edit_student(item))
        delete_button.clicked.connect(lambda _checked=False, item=student: self.delete_student(item))
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)
        return container

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        if column != 8 and 0 <= row < len(self._students):
            self.edit_student(self._students[row])
