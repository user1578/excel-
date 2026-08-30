"""导入历史记录页面。"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.services.import_service import ImportService


class HistoryPage(QWidget):
    def __init__(self, service: ImportService, parent=None):
        super().__init__(parent)
        self.service = service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(QLabel("历史记录", objectName="pageTitle"))
        bar = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh); bar.addStretch()
        layout.addLayout(bar)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["时间", "任务", "来源文件", "工作表", "总行", "成功", "待确认", "重复", "冲突"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

    def refresh(self):
        logs = self.service.list_logs()
        self.table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            values = (log["created_at"], log["task_name"], log["original_name"], log["sheet_name"] or "CSV", log["total_rows"], log["success_count"], log["pending_count"], log["duplicate_count"], log["conflict_count"])
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
