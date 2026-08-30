"""学生新增与编辑对话框。"""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.student import Student
from app.services.master_data_service import MasterDataService


class StudentDialog(QDialog):
    def __init__(self, service: MasterDataService, student: Student | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.student = student
        self.setWindowTitle("编辑学生" if student else "新增学生")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.number_input = QLineEdit()
        self.class_input = QComboBox()
        self.major_input = QLineEdit()
        self.grade_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.dormitory_input = QComboBox()
        self.dormitory_input.setEditable(True)
        self.remark_input = QTextEdit()
        self.remark_input.setFixedHeight(78)

        for class_record in self.service.list_classes():
            self.class_input.addItem(class_record.standard_name)
        self.dormitory_input.addItem("")
        for dormitory in self.service.list_dormitories():
            self.dormitory_input.addItem(dormitory.standard_name)

        form.addRow("姓名 *", self.name_input)
        form.addRow("学号 *", self.number_input)
        form.addRow("班级 *", self.class_input)
        form.addRow("专业", self.major_input)
        form.addRow("年级", self.grade_input)
        form.addRow("联系电话", self.phone_input)
        form.addRow("寝室", self.dormitory_input)
        form.addRow("备注", self.remark_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if student:
            self._load_student(student)

    def _load_student(self, student: Student) -> None:
        self.name_input.setText(student.name)
        self.number_input.setText(student.student_number)
        if self.class_input.findText(student.class_name) == -1:
            self.class_input.addItem(student.class_name)
        self.class_input.setCurrentText(student.class_name)
        self.major_input.setText(student.major or "")
        self.grade_input.setText(student.grade or "")
        self.phone_input.setText(student.phone or "")
        self.dormitory_input.setCurrentText(student.dormitory or "")
        self.remark_input.setPlainText(student.remark or "")

    def accept(self) -> None:
        if not self.name_input.text().strip() or not self.number_input.text().strip() or not self.class_input.currentText().strip():
            QMessageBox.warning(self, "请补全信息", "姓名、学号、班级为必填项。")
            return
        super().accept()

    def to_model(self) -> Student:
        return Student(
            name=self.name_input.text(),
            student_number=self.number_input.text(),
            class_name=self.class_input.currentText(),
            major=self.major_input.text().strip() or None,
            grade=self.grade_input.text().strip() or None,
            phone=self.phone_input.text().strip() or None,
            dormitory=self.dormitory_input.currentText().strip() or None,
            remark=self.remark_input.toPlainText().strip() or None,
        )
