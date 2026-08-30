"""班级别名管理对话框。"""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.class_record import ClassRecord
from app.services.master_data_service import MasterDataService


class AliasDialog(QDialog):
    def __init__(self, service: MasterDataService, class_record: ClassRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.class_record = class_record
        self._aliases = []
        self.setWindowTitle("管理班级别名")
        self.setMinimumSize(380, 300)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"标准名称：{class_record.standard_name}"))
        self.alias_list = QListWidget()
        layout.addWidget(self.alias_list)
        buttons = QHBoxLayout()
        add_button = QPushButton("新增别名")
        delete_button = QPushButton("删除别名")
        close_button = QPushButton("关闭")
        add_button.clicked.connect(self._add_alias)
        delete_button.clicked.connect(self._delete_alias)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(add_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        self._aliases = self.service.list_class_aliases(self.class_record.id)
        self.alias_list.clear()
        self.alias_list.addItems([alias.alias_name for alias in self._aliases])

    def _add_alias(self) -> None:
        alias_name, accepted = QInputDialog.getText(self, "新增别名", "班级别名：")
        if not accepted or not alias_name.strip():
            return
        try:
            self.service.add_class_alias(self.class_record.id, alias_name)
        except ValueError as error:
            QMessageBox.warning(self, "无法新增别名", str(error))
            return
        except Exception:
            QMessageBox.critical(self, "操作失败", "保存班级别名失败，请稍后重试。")
            return
        self.refresh()

    def _delete_alias(self) -> None:
        row = self.alias_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "请选择别名", "请先选择要删除的班级别名。")
            return
        alias = self._aliases[row]
        if QMessageBox.question(
            self,
            "确认删除",
            f"确定删除别名“{alias.alias_name}”吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.service.delete_class_alias(alias.id)
            self.refresh()
