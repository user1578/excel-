"""整理任务的最小可用管理页面。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QInputDialog

from app.models.task import Task
from app.services.task_service import TaskInUseError, TaskService


class TaskPage(QWidget):
    data_changed = Signal()

    def __init__(self, service: TaskService, parent=None):
        super().__init__(parent)
        self.service = service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(QLabel("整理任务", objectName="pageTitle"))
        bar = QHBoxLayout()
        add = QPushButton("新建任务")
        remove = QPushButton("删除任务")
        refresh = QPushButton("刷新")
        add.clicked.connect(self.create_task)
        remove.clicked.connect(self.delete_task)
        refresh.clicked.connect(self.refresh)
        bar.addWidget(add); bar.addWidget(remove); bar.addWidget(refresh); bar.addStretch()
        layout.addLayout(bar)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "任务名称", "类型", "状态", "备注"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

    def refresh(self):
        tasks = self.service.list()
        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            for column, value in enumerate((task.id, task.name, task.task_type, task.status, task.remark or "")):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))

    def create_task(self):
        name, accepted = QInputDialog.getText(self, "新建整理任务", "任务名称：")
        if not accepted or not name.strip():
            return
        try:
            self.service.create(Task(name.strip()))
        except ValueError as error:
            QMessageBox.warning(self, "创建失败", str(error))
            return
        self.refresh()
        self.data_changed.emit()

    def delete_task(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "请选择任务", "请先选择要删除的任务。")
            return
        task_id = int(self.table.item(row, 0).text())
        try:
            self.service.delete(task_id)
        except TaskInUseError as error:
            QMessageBox.warning(self, "不能删除", str(error))
            return
        self.refresh()
        self.data_changed.emit()
