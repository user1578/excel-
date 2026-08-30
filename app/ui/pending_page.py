"""持久化待确认记录的查看与人工解决页面。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QInputDialog

from app.services.import_service import ImportService, PendingResolutionError
from app.services.master_data_service import MasterDataService


class PendingPage(QWidget):
    def __init__(self, service: ImportService, master: MasterDataService, parent=None):
        super().__init__(parent)
        self.service = service
        self.master = master
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(QLabel("待确认", objectName="pageTitle"))
        self.tip = QLabel("暂无待处理记录。")
        layout.addWidget(self.tip)
        bar = QHBoxLayout()
        resolve = QPushButton("解决并导入")
        refresh = QPushButton("刷新")
        resolve.clicked.connect(self.resolve_selected)
        refresh.clicked.connect(self.refresh)
        bar.addWidget(resolve); bar.addWidget(refresh); bar.addStretch()
        layout.addLayout(bar)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "任务", "原始行", "异常", "姓名", "学号", "建议", "状态"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

    def set_session(self, _session):
        """兼容导入页信号；正式数据以数据库为准。"""
        self.refresh()

    def refresh(self):
        rows = self.service.list_pending()
        self.tip.setText(f"当前共有 {sum(row['status'] == '待处理' for row in rows)} 条待处理记录。")
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            import json
            data = json.loads(row["normalized_data"])
            values = (row["id"], row["task_id"], row["source_row_number"], row["issue_type"], data.get("name", ""), data.get("student_number", ""), row["suggestion"] or "", row["status"])
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))

    def resolve_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "请选择记录", "请先选择一条待确认记录。")
            return
        if self.table.item(row, 7).text() != "待处理":
            QMessageBox.information(self, "无需处理", "该记录已经解决。")
            return
        students = self.master.list_students()
        labels = [f"#{student.id}　{student.name}（{student.student_number}，{student.class_name}）" for student in students]
        if not labels:
            QMessageBox.warning(self, "无法解决", "学生库为空，请先维护学生基础资料。")
            return
        choice, accepted = QInputDialog.getItem(self, "选择正确学生", "解决后将按选定学生写入正式考勤：", labels, 0, False)
        if not accepted:
            return
        student_id = students[labels.index(choice)].id
        try:
            self.service.resolve_and_import(int(self.table.item(row, 0).text()), student_id)
        except PendingResolutionError as error:
            QMessageBox.warning(self, "解决失败", str(error))
            return
        QMessageBox.information(self, "已解决", "已写入正式考勤记录。")
        self.refresh()
