"""寝室新增与编辑对话框。"""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.dormitory import Dormitory


class DormitoryDialog(QDialog):
    def __init__(self, dormitory: Dormitory | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑寝室" if dormitory else "新增寝室")
        self.setMinimumWidth(420)
        self._last_suggestion = ""

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.building_input = QLineEdit()
        self.room_input = QLineEdit()
        self.name_input = QLineEdit()
        self.remark_input = QTextEdit()
        self.remark_input.setFixedHeight(78)
        self.building_input.textChanged.connect(self._update_name_suggestion)
        self.room_input.textChanged.connect(self._update_name_suggestion)
        form.addRow("楼栋 *", self.building_input)
        form.addRow("寝室号 *", self.room_input)
        form.addRow("标准寝室名称", self.name_input)
        form.addRow("备注", self.remark_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if dormitory:
            self.building_input.setText(dormitory.building)
            self.room_input.setText(dormitory.room_number)
            self.name_input.setText(dormitory.standard_name)
            self.remark_input.setPlainText(dormitory.remark or "")
            self._last_suggestion = self._suggested_name()

    def _suggested_name(self) -> str:
        building = self.building_input.text().strip()
        room = self.room_input.text().strip()
        return f"{building}-{room}" if building and room else ""

    def _update_name_suggestion(self) -> None:
        suggestion = self._suggested_name()
        if not self.name_input.text().strip() or self.name_input.text() == self._last_suggestion:
            self.name_input.setText(suggestion)
        self._last_suggestion = suggestion

    def accept(self) -> None:
        if not self.building_input.text().strip() or not self.room_input.text().strip():
            QMessageBox.warning(self, "请补全信息", "楼栋和寝室号为必填项。")
            return
        if not self.name_input.text().strip():
            self.name_input.setText(self._suggested_name())
        super().accept()

    def to_model(self) -> Dormitory:
        return Dormitory(
            building=self.building_input.text(),
            room_number=self.room_input.text(),
            standard_name=self.name_input.text(),
            remark=self.remark_input.toPlainText().strip() or None,
        )
