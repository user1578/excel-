"""只读考勤统计、来源追溯与 Excel 导出界面。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from app.services.excel_export_service import ExcelExportService
from app.services.master_data_service import MasterDataService
from app.services.statistics_service import AttendanceQuery, StatisticsService
from app.services.task_service import TaskService


class StatisticsPage(QWidget):
    def __init__(self, service: StatisticsService, exporter: ExcelExportService, master: MasterDataService, tasks: TaskService, parent=None):
        super().__init__(parent)
        self.service, self.exporter, self.master, self.tasks = service, exporter, master, tasks
        self.current_query = AttendanceQuery()
        self.personal_rows: list[dict] = []
        self.class_rows: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(QLabel("汇总统计", objectName="pageTitle"))
        layout.addWidget(self._build_filters())
        self.notice = QLabel("请选择条件后点击“生成统计”。")
        layout.addWidget(self.notice)
        self.overview = self._build_overview()
        layout.addLayout(self.overview)
        self.tabs = QTabWidget()
        self.personal_table = self._build_table(["姓名", "学号", "班级", "迟到次数", "缺勤次数", "请假次数", "正常次数", "其他次数", "异常总次数", "记录总数"])
        self.class_table = self._build_table(["班级", "班级人数", "记录学生数", "迟到次数", "缺勤次数", "请假次数", "正常次数", "其他次数", "异常总次数", "记录总数"])
        self.personal_table.cellDoubleClicked.connect(self.open_student_detail)
        self.class_table.cellDoubleClicked.connect(self.open_class_detail)
        self.tabs.addTab(self.personal_table, "个人汇总")
        self.tabs.addTab(self.class_table, "班级汇总")
        layout.addWidget(self.tabs, 1)
        self.refresh()

    def _build_filters(self) -> QWidget:
        container = QWidget()
        form = QGridLayout(container)
        self.task_box = QComboBox()
        self.class_box = QComboBox()
        self.student_box = QComboBox()
        self.type_box = QComboBox()
        self.status_box = QComboBox()
        self.period_box = QComboBox()
        self.period_box.addItems(["全部", "本周", "本月", "自定义"])
        self.period_box.currentTextChanged.connect(self._period_changed)
        self.start_date = QDateEdit(QDate.currentDate())
        self.end_date = QDateEdit(QDate.currentDate())
        for widget in (self.start_date, self.end_date):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy-MM-dd")
            widget.setEnabled(False)
        form.addWidget(QLabel("任务"), 0, 0); form.addWidget(self.task_box, 0, 1)
        form.addWidget(QLabel("日期范围"), 0, 2); form.addWidget(self.period_box, 0, 3)
        form.addWidget(self.start_date, 0, 4); form.addWidget(QLabel("至"), 0, 5); form.addWidget(self.end_date, 0, 6)
        form.addWidget(QLabel("班级"), 1, 0); form.addWidget(self.class_box, 1, 1)
        form.addWidget(QLabel("学生"), 1, 2); form.addWidget(self.student_box, 1, 3)
        form.addWidget(QLabel("考勤类型"), 1, 4); form.addWidget(self.type_box, 1, 5)
        form.addWidget(QLabel("考勤状态"), 1, 6); form.addWidget(self.status_box, 1, 7)
        query_button = QPushButton("生成统计")
        export_button = QPushButton("导出当前统计结果")
        query_button.clicked.connect(self.run_query)
        export_button.clicked.connect(self.export_current)
        form.addWidget(query_button, 2, 6); form.addWidget(export_button, 2, 7)
        return container

    def _build_overview(self) -> QGridLayout:
        layout = QGridLayout()
        self.overview_labels: dict[str, QLabel] = {}
        for index, (key, label) in enumerate((
            ("record_count", "记录总数"), ("student_count", "涉及学生数"), ("class_count", "涉及班级数"),
            ("late_count", "迟到次数"), ("absent_count", "缺勤次数"), ("leave_count", "请假次数"), ("abnormal_count", "异常总次数"),
        )):
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.addWidget(QLabel(label))
            value = QLabel("0")
            value.setObjectName("statValue")
            card_layout.addWidget(value)
            self.overview_labels[key] = value
            layout.addWidget(card, 0, index)
        return layout

    @staticmethod
    def _build_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        table.setSortingEnabled(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return table

    def refresh(self):
        self._populate_filters()

    def _populate_filters(self):
        self._reset_box(self.task_box, "全部", None, [(f"#{task.id}　{task.name}", task.id) for task in self.tasks.list()])
        self._reset_box(self.class_box, "全部", None, [(item.standard_name, item.standard_name) for item in self.master.list_classes()])
        self._reset_box(self.student_box, "全部", None, [(f"{item.name}（{item.student_number}，{item.class_name}）", item.id) for item in self.master.list_students()])
        self._reset_box(self.type_box, "全部", None, [(item, item) for item in self.service.attendance_types()])
        self._reset_box(self.status_box, "全部", None, [(item, item) for item in ("正常", "迟到", "缺勤", "请假", "其他")])

    @staticmethod
    def _reset_box(box: QComboBox, all_label: str, all_value, values: list[tuple[str, object]]):
        selected = box.currentData()
        box.blockSignals(True)
        box.clear(); box.addItem(all_label, all_value)
        for label, value in values:
            box.addItem(label, value)
        index = box.findData(selected)
        if index >= 0:
            box.setCurrentIndex(index)
        box.blockSignals(False)

    def _period_changed(self, period: str):
        custom = period == "自定义"
        self.start_date.setEnabled(custom)
        self.end_date.setEnabled(custom)

    def _query(self) -> AttendanceQuery:
        period = self.period_box.currentText()
        if period == "自定义":
            start, end = self.start_date.date().toString("yyyy-MM-dd"), self.end_date.date().toString("yyyy-MM-dd")
        else:
            start, end = self.service.dates_for_period(period)
        return AttendanceQuery(self.task_box.currentData(), start, end, self.class_box.currentData(), self.student_box.currentData(), self.type_box.currentData(), self.status_box.currentData())

    def run_query(self):
        try:
            self.current_query = self._query()
            result = self.service.summarize(self.current_query)
        except ValueError as error:
            QMessageBox.warning(self, "筛选条件无效", str(error))
            return
        self.personal_rows, self.class_rows = result.personal_rows, result.class_rows
        for key, label in self.overview_labels.items():
            label.setText(str(result.overview[key]))
        self._fill_table(self.personal_table, self.personal_rows, ["name", "student_number", "class_name", "late_count", "absent_count", "leave_count", "normal_count", "other_count", "abnormal_count", "record_count"])
        self._fill_table(self.class_table, self.class_rows, ["class_name", "class_student_count", "record_student_count", "late_count", "absent_count", "leave_count", "normal_count", "other_count", "abnormal_count", "record_count"])
        self.notice.setText("当前条件下暂无考勤记录" if not result.overview["record_count"] else f"当前条件下共 {result.overview['record_count']} 条考勤记录。双击汇总行可查看明细。")

    @staticmethod
    def _fill_table(table: QTableWidget, rows: list[dict], keys: list[str]):
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, key in enumerate(keys):
                value = row.get(key, "")
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, "" if value is None else value)
                table.setItem(row_index, column, item)
            table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row)
        table.setSortingEnabled(True)

    def open_student_detail(self, row_index: int, _column: int = 0):
        if row_index < 0 or not self.personal_table.item(row_index, 0):
            return
        row = self.personal_table.item(row_index, 0).data(Qt.ItemDataRole.UserRole)
        if row.get("student_id") is None:
            QMessageBox.information(self, "无法追溯", "该历史记录没有关联学生库，无法按学生打开明细。")
            return
        StudentDetailDialog(self, self.service, self.exporter, self.current_query, int(row["student_id"]), row["name"]).exec()

    def open_class_detail(self, row_index: int, _column: int = 0):
        if row_index < 0 or not self.class_table.item(row_index, 0):
            return
        class_name = self.class_table.item(row_index, 0).data(Qt.ItemDataRole.UserRole)["class_name"]
        rows = self.service.summarize(replace(self.current_query, class_name=class_name)).personal_rows
        SummaryDialog(self, f"{class_name} — 学生个人汇总", ["姓名", "学号", "迟到", "缺勤", "请假", "正常", "其他", "异常总次数", "记录总数"], rows, ["name", "student_number", "late_count", "absent_count", "leave_count", "normal_count", "other_count", "abnormal_count", "record_count"]).exec()

    def export_current(self, show_message: bool = True) -> Path | None:
        try:
            path = self.exporter.export_summaries(self.current_query)
        except ValueError as error:
            if show_message:
                QMessageBox.information(self, "无法导出", str(error))
            return None
        if show_message:
            QMessageBox.information(self, "导出完成", f"已导出：{path}");
        return path


class SummaryDialog(QDialog):
    def __init__(self, parent, title: str, headers: list[str], rows: list[dict], keys: list[str]):
        super().__init__(parent)
        self.setWindowTitle(title); self.resize(900, 500)
        layout = QVBoxLayout(self)
        table = StatisticsPage._build_table(headers)
        StatisticsPage._fill_table(table, rows, keys)
        layout.addWidget(table)


class StudentDetailDialog(QDialog):
    def __init__(self, parent, service: StatisticsService, exporter: ExcelExportService, query: AttendanceQuery, student_id: int, student_name: str):
        super().__init__(parent)
        self.exporter, self.query, self.student_id, self.student_name = exporter, query, student_id, student_name
        self.setWindowTitle(f"{student_name} — 考勤明细"); self.resize(980, 540)
        layout = QVBoxLayout(self)
        rows = service.student_detail(query, student_id)
        table = StatisticsPage._build_table(["日期", "考勤类型", "课程", "状态", "次数", "任务", "来源文件", "工作表", "原始行号", "备注"])
        StatisticsPage._fill_table(table, rows, ["date", "attendance_type", "course", "status", "count", "task_name", "source_file_name", "sheet_name", "source_row_number", "remark"])
        layout.addWidget(table)
        export = QPushButton("导出当前学生明细")
        export.clicked.connect(self.export_detail)
        layout.addWidget(export)

    def export_detail(self):
        try:
            path = self.exporter.export_student_detail(self.query, self.student_id, self.student_name)
        except ValueError as error:
            QMessageBox.information(self, "无法导出", str(error)); return
        QMessageBox.information(self, "导出完成", f"已导出：{path}")
