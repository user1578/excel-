"""资料汇总页面：选择来源、预览、安全解决冲突并导出。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.merge_models import ConflictResolution, MergeMode, MergeResult
from app.models.table_dataset import TableDataset
from app.services.data_workspace_service import DataWorkspaceService
from app.services.dataset_merge_service import DatasetMergeService
from app.services.merge_export_service import MergeExportService
from app.services.master_data_import_service import MasterDataImportService
from app.services.table_analysis_service import TableAnalysisService


@dataclass
class SourceSelection:
    path: Path
    sheet_name: str | None
    header_row: int | None = None
    dataset: TableDataset | None = None

    @property
    def label(self) -> str:
        return f"{self.path.name} / {self.sheet_name or 'CSV'}"


class MergePage(QWidget):
    def __init__(self, workspace: DataWorkspaceService, master=None, parent=None) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.analysis_service = TableAnalysisService()
        self.merge_service = DatasetMergeService()
        self.export_service = MergeExportService()
        self.master_import = MasterDataImportService(master.students.database) if master else None
        self.sources: list[SourceSelection] = []
        self.result: MergeResult | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(QLabel("资料汇总", objectName="pageTitle"))
        layout.addWidget(QLabel("分析多个 .xlsx/.csv 来源后，可纵向追加或按学生安全关联；同名不会被静默合并。"))
        bar = QHBoxLayout()
        add = QPushButton("添加文件")
        remove = QPushButton("删除文件")
        add.clicked.connect(self.add_files)
        remove.clicked.connect(self.remove_selected)
        bar.addWidget(add); bar.addWidget(remove); bar.addStretch()
        layout.addLayout(bar)
        self.source_list = QListWidget()
        self.source_list.currentRowChanged.connect(self._show_source_settings)
        layout.addWidget(self.source_list)
        setting = QHBoxLayout()
        self.sheet_box = QComboBox()
        self.header_spin = QSpinBox(); self.header_spin.setRange(0, 1000); self.header_spin.setSpecialValueText("自动表头")
        apply = QPushButton("应用 Sheet / 表头")
        apply.clicked.connect(self.apply_source_settings)
        setting.addWidget(QLabel("Sheet")); setting.addWidget(self.sheet_box)
        setting.addWidget(QLabel("表头行（0=自动）")); setting.addWidget(self.header_spin); setting.addWidget(apply); setting.addStretch()
        layout.addLayout(setting)
        action = QHBoxLayout()
        self.mode_box = QComboBox()
        self.mode_box.addItem("直接纵向合并", MergeMode.VERTICAL)
        self.mode_box.addItem("按学生关联合并", MergeMode.STUDENT)
        analyze = QPushButton("分析全部来源")
        merge = QPushButton("执行汇总")
        export = QPushButton("导出汇总")
        import_master = QPushButton("导入基础库")
        analyze.clicked.connect(self.analyze_all)
        merge.clicked.connect(self.run_merge)
        export.clicked.connect(self.export_result)
        import_master.clicked.connect(self.import_master_data)
        action.addWidget(QLabel("模式")); action.addWidget(self.mode_box); action.addWidget(analyze); action.addWidget(merge); action.addWidget(export); action.addWidget(import_master); action.addStretch()
        layout.addLayout(action)
        self.message = QLabel("尚未添加来源文件。")
        layout.addWidget(self.message)
        self.preview = QTableWidget(0, 0)
        layout.addWidget(self.preview, 1)
        layout.addWidget(QLabel("字段冲突", objectName="sectionTitle"))
        self.conflicts = QTableWidget(0, 5)
        self.conflicts.setHorizontalHeaderLabels(["字段", "值 A", "值 B", "来源", "状态"])
        layout.addWidget(self.conflicts)
        resolution = QHBoxLayout()
        use_a = QPushButton("使用 A")
        use_b = QPushButton("使用 B")
        manual = QPushButton("手动输入")
        defer = QPushButton("暂不解决")
        use_a.clicked.connect(lambda: self.resolve_selected(ConflictResolution.USE_A))
        use_b.clicked.connect(lambda: self.resolve_selected(ConflictResolution.USE_B))
        manual.clicked.connect(lambda: self.resolve_selected(ConflictResolution.MANUAL))
        defer.clicked.connect(lambda: self.resolve_selected(ConflictResolution.UNRESOLVED))
        for button in (use_a, use_b, manual, defer): resolution.addWidget(button)
        resolution.addStretch(); layout.addLayout(resolution)

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择资料文件", "", "Excel/CSV (*.xlsx *.csv)")
        for text in paths:
            path = Path(text)
            try:
                sheets = self.analysis_service.sheets(path)
            except ValueError as error:
                QMessageBox.warning(self, "无法添加", str(error)); continue
            self.sources.append(SourceSelection(path, sheets[0]))
        self._refresh_sources()

    def remove_selected(self) -> None:
        row = self.source_list.currentRow()
        if row >= 0:
            self.sources.pop(row)
            self._refresh_sources()

    def _refresh_sources(self) -> None:
        current = self.source_list.currentRow()
        self.source_list.clear()
        self.source_list.addItems([source.label for source in self.sources])
        if self.sources:
            self.source_list.setCurrentRow(min(max(current, 0), len(self.sources) - 1))

    def _show_source_settings(self, row: int) -> None:
        self.sheet_box.clear()
        if row < 0 or row >= len(self.sources):
            return
        source = self.sources[row]
        self.sheet_box.addItems([sheet or "CSV" for sheet in self.analysis_service.sheets(source.path)])
        self.sheet_box.setCurrentText(source.sheet_name or "CSV")
        self.header_spin.setValue(source.header_row or 0)

    def apply_source_settings(self) -> None:
        row = self.source_list.currentRow()
        if row < 0:
            return
        source = self.sources[row]
        source.sheet_name = None if source.path.suffix.lower() == ".csv" else self.sheet_box.currentText()
        source.header_row = self.header_spin.value() or None
        source.dataset = None
        self._refresh_sources()

    def analyze_all(self) -> None:
        try:
            for source in self.sources:
                source.dataset = self.analysis_service.analyze(source.path, source.sheet_name, source.header_row)
            count = sum(len(source.dataset.rows) for source in self.sources if source.dataset)
            self.message.setText(f"已分析 {len(self.sources)} 个来源，共 {count} 行；字段在预览和汇总时保留。")
        except ValueError as error:
            QMessageBox.warning(self, "分析失败", str(error))

    def run_merge(self) -> None:
        if not self.sources:
            QMessageBox.information(self, "请添加文件", "请先添加至少一个 xlsx 或 csv 来源。"); return
        if any(source.dataset is None for source in self.sources):
            self.analyze_all()
        datasets = [source.dataset for source in self.sources if source.dataset is not None]
        try:
            self.result = self.merge_service.merge(datasets, self.mode_box.currentData())
        except ValueError as error:
            QMessageBox.warning(self, "汇总失败", str(error)); return
        self.workspace.set_merge_result(self.result)
        self._render_result()

    def _render_result(self) -> None:
        if self.result is None:
            return
        self.preview.setColumnCount(len(self.result.columns)); self.preview.setRowCount(len(self.result.records))
        self.preview.setHorizontalHeaderLabels([self.result.column_labels[key] for key in self.result.columns])
        for row, record in enumerate(self.result.records):
            for column, key in enumerate(self.result.columns):
                self.preview.setItem(row, column, QTableWidgetItem(str(record.values.get(key, ""))))
        self.conflicts.setRowCount(len(self.result.conflicts))
        for row, conflict in enumerate(self.result.conflicts):
            origin = f"{conflict.source_a.source_file}:{conflict.source_a.source_row} / {conflict.source_b.source_file}:{conflict.source_b.source_row}"
            values = [self.result.column_labels.get(conflict.field, conflict.field), conflict.value_a, conflict.value_b, origin, conflict.resolution.value]
            for column, value in enumerate(values): self.conflicts.setItem(row, column, QTableWidgetItem(str(value)))
        unlinked = MergeExportService._unlinked_count(self.result)
        self.message.setText(f"汇总 {len(self.result.records)} 行；未解决冲突 {len(self.result.unresolved_conflicts)} 个；未关联 {unlinked} 行。")

    def import_master_data(self) -> None:
        if self.master_import is None or self.workspace.current_dataset is None:
            QMessageBox.information(self, "没有可导入资料", "请先完成一次资料汇总。")
            return
        preview = self.master_import.preview(self.workspace.current_dataset)
        details = (
            f"新增班级：{preview.new_classes}；已有班级：{preview.existing_classes}；班级冲突：{len(preview.class_conflicts)}\n"
            f"新增寝室：{preview.new_dormitories}；已有寝室：{preview.existing_dormitories}；待确认：{len(preview.pending_dormitories)}\n"
            f"新增学生：{preview.new_students}；已有学生：{preview.existing_students}；可补全：{preview.updatable_students}；学生冲突：{len(preview.student_conflicts)}\n"
            f"扩展字段：{preview.extra_field_count} 个\n\n"
            "仅补全已有学生的空字段；已有非空冲突不会覆盖。确认后才写入本机数据库。"
        )
        if QMessageBox.question(self, "导入基础库预览", details, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.master_import.apply(self.workspace.current_dataset)
        except Exception as error:
            QMessageBox.critical(self, "导入失败", f"导入已回滚，未写入部分数据：{error}")
            return
        QMessageBox.information(self, "导入完成", "基础库已按班级、寝室、学生顺序原子写入。待确认寝室与冲突项未自动覆盖。")

    def resolve_selected(self, resolution: ConflictResolution) -> None:
        if self.result is None or self.conflicts.currentRow() < 0:
            QMessageBox.information(self, "请选择冲突", "请先选择一条字段冲突。"); return
        conflict = self.result.conflicts[self.conflicts.currentRow()]
        manual_value = None
        if resolution is ConflictResolution.MANUAL:
            manual_value, accepted = QInputDialog.getText(self, "手动解决", "请输入要保留的值：")
            if not accepted: return
        self.merge_service.resolve_conflict(self.result, conflict.id, resolution, manual_value)
        self.workspace.set_merge_result(self.result)
        self._render_result()

    def export_result(self) -> None:
        if self.result is None:
            QMessageBox.information(self, "尚未汇总", "请先执行汇总并检查预览。"); return
        allow = False
        if self.result.unresolved_conflicts:
            answer = QMessageBox.question(self, "存在未解决冲突", "未解决冲突将随冲突清单导出，确认继续吗？")
            if answer != QMessageBox.StandardButton.Yes: return
            allow = True
        try:
            path = self.export_service.export(self.result, allow)
        except ValueError as error:
            QMessageBox.warning(self, "导出失败", str(error)); return
        QMessageBox.information(self, "导出完成", f"已另存到：\n{path}")
