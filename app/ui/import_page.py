"""资料导入：选择、原始预览、字段映射与标准化预览。"""
from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtWidgets import *
from app.models.field_mapping import FIELD_LABELS, StandardField
from app.services.import_service import ImportService
from app.services.task_service import TaskService

class ImportPage(QWidget):
 session_changed=Signal(object)
 imported=Signal()
 def __init__(self,service:ImportService,task_service:TaskService,parent=None):
  super().__init__(parent); self.service=service; self.task_service=task_service; self.session=None; self.files=[]; self.stack=QStackedWidget(); root=QVBoxLayout(self); root.setContentsMargins(36,32,36,32); root.addWidget(QLabel("资料导入",objectName="pageTitle")); root.addWidget(self.stack,1); self._build_files(); self._build_mapping(); self._build_preview(); self.refresh_tasks()
 def _build_files(self):
  page=QWidget(); l=QVBoxLayout(page); task_bar=QHBoxLayout();task_bar.addWidget(QLabel("目标整理任务："));self.task_box=QComboBox();task_bar.addWidget(self.task_box,1);refresh_tasks=QPushButton("刷新任务");refresh_tasks.clicked.connect(self.refresh_tasks);task_bar.addWidget(refresh_tasks);task_bar.addWidget(QLabel("数据记录方式："));self.record_mode_box=QComboBox();self.record_mode_box.addItems(["仅异常名单","完整考勤名单"]);self.record_mode_box.currentTextChanged.connect(self._record_mode_changed);task_bar.addWidget(self.record_mode_box);l.addLayout(task_bar);bar=QHBoxLayout(); add=QPushButton("选择文件"); clear=QPushButton("清空列表"); add.clicked.connect(self.choose_files); clear.clicked.connect(self.clear); bar.addWidget(add);bar.addWidget(clear);bar.addStretch();l.addLayout(bar); self.file_table=QTableWidget(0,5);self.file_table.setHorizontalHeaderLabels(["文件名","类型","路径","大小","状态"]);self.file_table.horizontalHeader().setStretchLastSection(True);self.file_table.itemSelectionChanged.connect(self._selected);l.addWidget(self.file_table); self.sheet_box=QComboBox();self.sheet_box.currentTextChanged.connect(self._sheet_changed);l.addWidget(QLabel("工作表（CSV 无需选择）："));l.addWidget(self.sheet_box); self.raw_info=QLabel("请选择 .xlsx 或 .csv 文件。");l.addWidget(self.raw_info);self.header_box=QComboBox();self.header_box.currentIndexChanged.connect(self._header_changed);l.addWidget(QLabel("实际表头行（可人工修正）："));l.addWidget(self.header_box);self.raw_table=QTableWidget();l.addWidget(self.raw_table,1); next=QPushButton("进入字段映射");next.clicked.connect(lambda:self.stack.setCurrentIndex(1));l.addWidget(next);self.stack.addWidget(page)
 def _build_mapping(self):
  page=QWidget();l=QVBoxLayout(page);l.addWidget(QLabel("字段映射确认",objectName="pageTitle"));self.mapping_table=QTableWidget(0,5);self.mapping_table.setHorizontalHeaderLabels(["原始字段","自动识别","来源","置信度","最终映射"]);self.mapping_table.horizontalHeader().setStretchLastSection(True);l.addWidget(self.mapping_table,1);bar=QHBoxLayout();back=QPushButton("返回原始预览");redo=QPushButton("重新识别");confirm=QPushButton("确认映射并预览");back.clicked.connect(lambda:self.stack.setCurrentIndex(0));redo.clicked.connect(self._populate_mapping);confirm.clicked.connect(self.confirm);bar.addWidget(back);bar.addWidget(redo);bar.addStretch();bar.addWidget(confirm);l.addLayout(bar);self.stack.addWidget(page)
 def _build_preview(self):
  page=QWidget();l=QVBoxLayout(page);l.addWidget(QLabel("标准化数据预览",objectName="pageTitle"));self.summary=QLabel();l.addWidget(self.summary);self.preview_table=QTableWidget();l.addWidget(self.preview_table,1);bar=QHBoxLayout();back=QPushButton("返回字段映射");back.clicked.connect(lambda:self.stack.setCurrentIndex(1));commit=QPushButton("正式导入");commit.clicked.connect(self.commit);bar.addWidget(back);bar.addStretch();bar.addWidget(commit);l.addLayout(bar);self.stack.addWidget(page)
 def choose_files(self):
  paths,_=QFileDialog.getOpenFileNames(self,"选择资料",str(Path.cwd()),"Excel/CSV (*.xlsx *.csv)")
  for p in paths:
   if p not in self.files:self.files.append(p)
  self._render_files()
 def open_file(self,path:str):
  if Path(path).suffix.lower() not in (".xlsx",".csv"): raise ValueError("仅支持 .xlsx 和 .csv 文件")
  self.files=[path];self._render_files();self.file_table.selectRow(0);self._selected()
 def clear(self): self.files=[];self.session=None;self.file_table.setRowCount(0);self.raw_table.setRowCount(0)
 def refresh_tasks(self):
  selected=self.task_box.currentData() if hasattr(self,"task_box") else None
  self.task_box.clear()
  for task in self.task_service.list():self.task_box.addItem(f"#{task.id}　{task.name}（{task.status}）",task.id)
  if selected is not None:
   index=self.task_box.findData(selected)
   if index>=0:self.task_box.setCurrentIndex(index)
 def _render_files(self):
  self.file_table.setRowCount(len(self.files))
  for r,p in enumerate(self.files):
   f=Path(p);vals=[f.name,f.suffix.lower(),str(f),str(f.stat().st_size),"待读取"]
   for c,v in enumerate(vals):self.file_table.setItem(r,c,QTableWidgetItem(v))
 def _selected(self):
  rows=self.file_table.selectionModel().selectedRows()
  if not rows:return
  self._load(self.files[rows[0].row()])
 def _load(self,path):
  try:
   sheets=self.service.sheets(path);self.sheet_box.blockSignals(True);self.sheet_box.clear();self.sheet_box.addItems(sheets or [""]);self.sheet_box.blockSignals(False);self.session=self.service.analyze(path,sheets[0] if sheets else None);self.session.record_mode=self.record_mode_box.currentText();self._render_raw();self._populate_mapping()
  except ValueError as e: QMessageBox.warning(self,"读取失败",str(e))
 def _sheet_changed(self,name):
  if self.session and name and name!=self.session.sheet_name:
   self.session=self.service.analyze(self.session.file_path,name);self.session.record_mode=self.record_mode_box.currentText();self._render_raw();self._populate_mapping()
 def _record_mode_changed(self,mode):
  if self.session:self.session.record_mode=mode
 def _render_raw(self):
  s=self.session;self.raw_info.setText(f"文件：{s.file_path.name}　Sheet：{s.sheet_name or 'CSV'}　总行数：{s.total_rows}　总列数：{len(s.headers)}　自动表头：第{s.header_row+1}行（{s.header_reason}）")
  self.header_box.blockSignals(True);self.header_box.clear();self.header_box.addItems([f"第{i+1}行" for i in range(min(10,len(s.raw_frame)))]);self.header_box.setCurrentIndex(s.header_row);self.header_box.blockSignals(False)
  frame=s.raw_frame.head(100);self.raw_table.setRowCount(len(frame));self.raw_table.setColumnCount(len(frame.columns));self.raw_table.setHorizontalHeaderLabels([str(i+1) for i in range(len(frame.columns))])
  for r,row in enumerate(frame.itertuples(index=False,name=None)):
   for c,v in enumerate(row):self.raw_table.setItem(r,c,QTableWidgetItem("" if v is None else str(v)))
 def _header_changed(self,index):
  if self.session and index != self.session.header_row:
   self.session=self.service.analyze(self.session.file_path,self.session.sheet_name,index);self._render_raw();self._populate_mapping()
 def _populate_mapping(self):
  if not self.session:return
  self.mapping_table.setRowCount(len(self.session.fields))
  for r,f in enumerate(self.session.fields):
   for c,v in enumerate((f.source_name,FIELD_LABELS[f.detected_field],f.source,str(f.confidence))):self.mapping_table.setItem(r,c,QTableWidgetItem(v))
   box=QComboBox();
   for field in StandardField:box.addItem(FIELD_LABELS[field],field)
   box.setCurrentIndex(list(StandardField).index(f.detected_field));self.mapping_table.setCellWidget(r,4,box)
 def confirm(self):
  if not self.session:return
  mapping={f.column_index:self.mapping_table.cellWidget(r,4).currentData() for r,f in enumerate(self.session.fields)}
  try:self.service.apply_mappings(self.session,mapping);self._render_preview();self.session_changed.emit(self.session);self.stack.setCurrentIndex(2)
  except ValueError as e:QMessageBox.warning(self,"映射无效",str(e))
 def _render_preview(self):
  records=self.session.records;cols=["状态","姓名","学号","班级","原始行号","匹配结果","异常原因"]+sorted({k for x in records for k in x.normalized_data if k not in {"name","student_number","class_name"}})
  self.preview_table.setColumnCount(len(cols));self.preview_table.setHorizontalHeaderLabels(cols);self.preview_table.setRowCount(min(500,len(records)))
  for r,record in enumerate(records[:500]):
   values=[record.match_status,record.normalized_data.get("name",""),record.normalized_data.get("student_number",""),record.normalized_data.get("class_name",""),str(record.row_number),str(record.student_id or ""),"；".join(record.issues)]+[str(record.normalized_data.get(k,"")) for k in cols[7:]]
   for c,v in enumerate(values):self.preview_table.setItem(r,c,QTableWidgetItem(v))
  normal=sum(x.match_status=="正常" for x in records); conflict=sum(x.match_status=="冲突" for x in records);self.summary.setText(f"共{len(records)}条；正常{normal}条；待确认{sum(x.match_status=='待确认' for x in records)}条；冲突{conflict}条。保存方式：{self.session.record_mode}。当前最多显示前500条。")
 def commit(self):
  if not self.session:return
  task_id=self.task_box.currentData()
  if task_id is None:QMessageBox.warning(self,"无法导入","请先在“整理任务”中新建并选择一个目标任务。");return
  try:
   result=self.service.import_session(int(task_id),self.session)
  except ValueError as error:QMessageBox.warning(self,"导入失败",str(error));return
  QMessageBox.information(self,"导入完成",f"正式写入 {result.success_count} 条；待确认 {result.pending_count} 条；重复 {result.duplicate_count} 条；完全重复跳过 {result.exact_duplicate_skip_count} 条。")
  self.imported.emit()
