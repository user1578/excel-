"""寝室库维护页面。"""

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

from app.models.dormitory import Dormitory
from app.services.master_data_service import DormitoryInUseError, DuplicateDormitoryError, MasterDataService
from app.ui.dialogs.dormitory_dialog import DormitoryDialog


class DormitoryPage(QWidget):
    data_changed = Signal()

    def __init__(self, service: MasterDataService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._dormitories: list[Dormitory] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(14)
        title = QLabel("寝室库")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入标准寝室名称、楼栋或寝室号搜索")
        self.search_input.returnPressed.connect(self.refresh)
        search_button = QPushButton("搜索")
        reset_button = QPushButton("重置")
        add_button = QPushButton("新增寝室")
        refresh_button = QPushButton("刷新")
        search_button.clicked.connect(self.refresh)
        reset_button.clicked.connect(self.reset_search)
        add_button.clicked.connect(self.add_dormitory)
        refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(search_button)
        toolbar.addWidget(reset_button)
        toolbar.addStretch()
        toolbar.addWidget(add_button)
        toolbar.addWidget(refresh_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["标准寝室名称", "楼栋", "寝室号", "备注", "操作"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        for column, width in enumerate((170, 100, 100, 220)):
            self.table.setColumnWidth(column, width)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        try:
            self._dormitories = self.service.search_dormitories(self.search_input.text())
        except Exception:
            QMessageBox.critical(self, "读取失败", "读取寝室数据失败，请检查数据库后重试。")
            return
        self.table.setRowCount(len(self._dormitories))
        for row, dormitory in enumerate(self._dormitories):
            values = [dormitory.standard_name, dormitory.building, dormitory.room_number, dormitory.remark]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value or "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, item)
            self.table.setCellWidget(row, 4, self._create_actions(dormitory))

    def reset_search(self) -> None:
        self.search_input.clear()
        self.refresh()

    def add_dormitory(self) -> None:
        dialog = DormitoryDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.service.create_dormitory(dialog.to_model())
        except DuplicateDormitoryError as error:
            QMessageBox.warning(self, "寝室重复", str(error))
            return
        except ValueError as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return
        except Exception:
            QMessageBox.critical(self, "保存失败", "保存寝室信息失败，请稍后重试。")
            return
        self.refresh()
        self.data_changed.emit()

    def edit_dormitory(self, dormitory: Dormitory) -> None:
        dialog = DormitoryDialog(dormitory, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.service.update_dormitory(dormitory.id, dialog.to_model())
        except DuplicateDormitoryError as error:
            QMessageBox.warning(self, "寝室重复", str(error))
            return
        except ValueError as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return
        except Exception:
            QMessageBox.critical(self, "保存失败", "更新寝室信息失败，请稍后重试。")
            return
        self.refresh()
        self.data_changed.emit()

    def delete_dormitory(self, dormitory: Dormitory) -> None:
        try:
            student_count = self.service.count_students_by_dormitory(dormitory.standard_name)
        except Exception:
            QMessageBox.critical(self, "检查失败", "无法检查寝室关联学生，请稍后重试。")
            return
        if student_count:
            QMessageBox.warning(self, "无法删除", f"当前有{student_count}名学生使用该寝室，请先处理学生寝室信息。")
            return
        if QMessageBox.question(
            self,
            "确认删除",
            f"确定删除寝室“{dormitory.standard_name}”吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_dormitory(dormitory.id)
        except DormitoryInUseError as error:
            QMessageBox.warning(self, "无法删除", str(error))
            return
        except Exception:
            QMessageBox.critical(self, "删除失败", "删除寝室信息失败，请稍后重试。")
            return
        self.refresh()
        self.data_changed.emit()

    def _create_actions(self, dormitory: Dormitory) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        edit_button = QPushButton("编辑")
        delete_button = QPushButton("删除")
        edit_button.clicked.connect(lambda _checked=False, item=dormitory: self.edit_dormitory(item))
        delete_button.clicked.connect(lambda _checked=False, item=dormitory: self.delete_dormitory(item))
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)
        return container

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        if column != 4 and 0 <= row < len(self._dormitories):
            self.edit_dormitory(self._dormitories[row])
