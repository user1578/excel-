"""学生新增与编辑对话框。"""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
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

        layout.addWidget(QLabel("扩展资料（仅保存在本机数据库）"))
        self.extra_table = QTableWidget(0, 2)
        self.extra_table.setHorizontalHeaderLabels(["字段", "值"])
        self.extra_table.setMinimumHeight(130)
        layout.addWidget(self.extra_table)
        extra_controls = QHBoxLayout()
        add_extra = QPushButton("新增字段")
        remove_extra = QPushButton("删除字段")
        add_extra.clicked.connect(self.add_extra_field)
        remove_extra.clicked.connect(self.remove_extra_field)
        extra_controls.addWidget(add_extra); extra_controls.addWidget(remove_extra); extra_controls.addStretch()
        layout.addLayout(extra_controls)
        self._deleted_extra_keys: list[str] = []

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
        if student.id:
            for field_key, item in self.service.get_student_extra_fields(student.id).items():
                self._add_extra_row(item["name"], item["value"], field_key)

    def _add_extra_row(self, name: str = "", value: str = "", field_key: str = "") -> None:
        row = self.extra_table.rowCount()
        self.extra_table.insertRow(row)
        name_item = QTableWidgetItem(name)
        name_item.setData(256, field_key)
        self.extra_table.setItem(row, 0, name_item)
        self.extra_table.setItem(row, 1, QTableWidgetItem(value))

    def add_extra_field(self) -> None:
        self._add_extra_row()

    def remove_extra_field(self) -> None:
        row = self.extra_table.currentRow()
        if row < 0:
            return
        key = self.extra_table.item(row, 0).data(256)
        if key:
            self._deleted_extra_keys.append(str(key))
        self.extra_table.removeRow(row)

    def extra_fields(self) -> list[tuple[str, str]]:
        values: list[tuple[str, str]] = []
        for row in range(self.extra_table.rowCount()):
            name = self.extra_table.item(row, 0).text().strip()
            value = self.extra_table.item(row, 1).text()
            if name:
                values.append((name, value))
        return values

    def deleted_extra_keys(self) -> list[str]:
        return list(self._deleted_extra_keys)

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
