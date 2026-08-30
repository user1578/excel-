"""班级新增与编辑对话框。"""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.class_record import ClassRecord


class ClassDialog(QDialog):
    def __init__(self, class_record: ClassRecord | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑班级" if class_record else "新增班级")
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.major_input = QLineEdit()
        self.grade_input = QLineEdit()
        self.count_input = QSpinBox()
        self.count_input.setRange(0, 100000)
        self.counselor_input = QLineEdit()
        self.remark_input = QTextEdit()
        self.remark_input.setFixedHeight(78)
        form.addRow("班级标准名称 *", self.name_input)
        form.addRow("专业", self.major_input)
        form.addRow("年级", self.grade_input)
        form.addRow("人数", self.count_input)
        form.addRow("辅导员", self.counselor_input)
        form.addRow("备注", self.remark_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if class_record:
            self.name_input.setText(class_record.standard_name)
            self.major_input.setText(class_record.major or "")
            self.grade_input.setText(class_record.grade or "")
            self.count_input.setValue(class_record.student_count)
            self.counselor_input.setText(class_record.counselor or "")
            self.remark_input.setPlainText(class_record.remark or "")

    def accept(self) -> None:
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "请补全信息", "班级标准名称为必填项。")
            return
        super().accept()

    def to_model(self) -> ClassRecord:
        return ClassRecord(
            standard_name=self.name_input.text(),
            major=self.major_input.text().strip() or None,
            grade=self.grade_input.text().strip() or None,
            student_count=self.count_input.value(),
            counselor=self.counselor_input.text().strip() or None,
            remark=self.remark_input.toPlainText().strip() or None,
        )
