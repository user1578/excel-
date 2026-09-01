"""班级库维护页面。"""

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

from app.models.class_record import ClassRecord
from app.services.master_data_service import ClassInUseError, DuplicateClassNameError, MasterDataService
from app.ui.dialogs.alias_dialog import AliasDialog
from app.ui.dialogs.class_dialog import ClassDialog
from app.ui.dialogs.class_students_dialog import ClassStudentsDialog
from app.services.data_workspace_service import DataWorkspaceService


class ClassPage(QWidget):
    data_changed = Signal()

    def __init__(self, service: MasterDataService, workspace: DataWorkspaceService | None = None, open_fill=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.workspace = workspace
        self.open_fill = open_fill
        self._classes: list[ClassRecord] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(14)
        title = QLabel("班级库")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入班级名称、专业、年级或辅导员搜索")
        self.search_input.returnPressed.connect(self.refresh)
        search_button = QPushButton("搜索")
        reset_button = QPushButton("重置")
        add_button = QPushButton("新增班级")
        refresh_button = QPushButton("刷新")
        search_button.clicked.connect(self.refresh)
        reset_button.clicked.connect(self.reset_search)
        add_button.clicked.connect(self.add_class)
        refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(search_button)
        toolbar.addWidget(reset_button)
        toolbar.addStretch()
        toolbar.addWidget(add_button)
        toolbar.addWidget(refresh_button)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["标准班级名称", "专业", "年级", "人数", "辅导员", "备注", "操作"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        for column, width in enumerate((160, 150, 80, 70, 110, 180)):
            self.table.setColumnWidth(column, width)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        try:
            self._classes = self.service.search_classes(self.search_input.text())
        except Exception:
            QMessageBox.critical(self, "读取失败", "读取班级数据失败，请检查数据库后重试。")
            return
        self.table.setRowCount(len(self._classes))
        for row, class_record in enumerate(self._classes):
            values = [class_record.standard_name, class_record.major, class_record.grade,
                      str(class_record.student_count), class_record.counselor, class_record.remark]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value or "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, item)
            self.table.setCellWidget(row, 6, self._create_actions(class_record))

    def reset_search(self) -> None:
        self.search_input.clear()
        self.refresh()

    def add_class(self) -> None:
        dialog = ClassDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.service.create_class(dialog.to_model())
        except DuplicateClassNameError as error:
            QMessageBox.warning(self, "班级重复", str(error))
            return
        except ValueError as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return
        except Exception:
            QMessageBox.critical(self, "保存失败", "保存班级信息失败，请稍后重试。")
            return
        self.refresh()
        self.data_changed.emit()

    def edit_class(self, class_record: ClassRecord) -> None:
        dialog = ClassDialog(class_record, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.service.update_class(class_record.id, dialog.to_model())
        except DuplicateClassNameError as error:
            QMessageBox.warning(self, "班级重复", str(error))
            return
        except ValueError as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return
        except Exception:
            QMessageBox.critical(self, "保存失败", "更新班级信息失败，请稍后重试。")
            return
        self.refresh()
        self.data_changed.emit()

    def delete_class(self, class_record: ClassRecord) -> None:
        try:
            student_count = self.service.count_students_by_class(class_record.standard_name)
        except Exception:
            QMessageBox.critical(self, "检查失败", "无法检查班级关联学生，请稍后重试。")
            return
        if student_count:
            QMessageBox.warning(self, "无法删除", f"当前有{student_count}名学生属于该班级，请先调整学生班级后再删除。")
            return
        if QMessageBox.question(
            self,
            "确认删除",
            f"确定删除班级“{class_record.standard_name}”吗？对应别名也将一并删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_class(class_record.id)
        except ClassInUseError as error:
            QMessageBox.warning(self, "无法删除", str(error))
            return
        except Exception:
            QMessageBox.critical(self, "删除失败", "删除班级信息失败，请稍后重试。")
            return
        self.refresh()
        self.data_changed.emit()

    def manage_aliases(self, class_record: ClassRecord) -> None:
        AliasDialog(self.service, class_record, self).exec()

    def view_students(self, class_record: ClassRecord) -> None:
        ClassStudentsDialog(self.service, class_record, self.workspace, self.open_fill, self).exec()

    def _create_actions(self, class_record: ClassRecord) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        edit_button = QPushButton("编辑")
        alias_button = QPushButton("管理别名")
        students_button = QPushButton("查看学生")
        export_button = QPushButton("生成表格")
        delete_button = QPushButton("删除")
        edit_button.clicked.connect(lambda _checked=False, item=class_record: self.edit_class(item))
        alias_button.clicked.connect(lambda _checked=False, item=class_record: self.manage_aliases(item))
        students_button.clicked.connect(lambda _checked=False, item=class_record: self.view_students(item))
        export_button.clicked.connect(lambda _checked=False, item=class_record: self.view_students(item))
        delete_button.clicked.connect(lambda _checked=False, item=class_record: self.delete_class(item))
        layout.addWidget(edit_button)
        layout.addWidget(alias_button)
        layout.addWidget(students_button)
        layout.addWidget(export_button)
        layout.addWidget(delete_button)
        return container

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        if column != 6 and 0 <= row < len(self._classes):
            self.edit_class(self._classes[row])
