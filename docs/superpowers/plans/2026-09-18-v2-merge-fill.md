# V2 资料汇总与表格填充 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在不重写既有 V2 模块的前提下，完成安全导入、资料汇总、格式保真模板填写、模板预填和照片字段，并让所有 Excel 输出由用户选择最终位置。

**Architecture:** 保留现有 Repository、TableDataset、DatasetMergeService、WorkbookFillService 与模板 Schema 的职责边界。新增日期上下文、结构化 pending 结果、原子输出事务和可选 COM 引擎；Windows 有 Microsoft Excel 时所有模板格式优先 COM，无 Excel 时仅 .xlsx 在明确接受的兼容模式下走 openpyxl。

**Tech Stack:** Python 3.11、PySide6、SQLite、pandas、openpyxl、Pillow、pywin32（仅 Windows）、pytest。

**Spec:** docs/superpowers/specs/2026-09-18-v2-merge-fill-design.md

## Global Constraints

- 从 codex/v2-merge-fill 实施，禁止修改或合并 main，禁止 git reset --hard、force push 和删除/弱化既有测试。
- 初始基线为 149 passed；每个 A–F 阶段结束必须运行完整 python -m pytest -q，不得以局部测试替代；所有新测试使用 tmp_path 或 tests/data 的虚构数据。
- 用户模板永远不改写；Service 层拒绝输出路径等于源模板路径，所有填充写入使用临时副本、重开校验、os.replace() 原子落盘、失败清理临时文件。
- Windows 检测到 Microsoft Excel 时 .xls/.xlsx/.xlsm 默认 COM；无 Excel 仅 .xlsx 可在用户单次明确接受后用 openpyxl 兼容模式，.xls/.xlsm 永不转换或降级。
- 所有用户来源文本写入 Excel 必须经 safe_excel_value()；只有代码生成且受控的公式可以直接写入。
- Excel 数字日期必须同时具备已知工作簿日期系统和原单元格日期语义才允许转换；普通数字禁止按范围推断日期。
- pywin32 只能以 sys_platform == "win32" 条件依赖、按需导入；无 pywin32 或 Excel 不得影响其它功能启动。
- photo 第一版只承诺等比例缩放且限制于目标单元格区域；只有实现并测试实际居中后才展示“居中”文案。

---

## File Structure

| 路径 | 职责 |
| --- | --- |
| app/utils/value_normalizer.py | 日期结果、日期语义校验与 ISO 日期规范化。 |
| app/models/import_session.py | 在分析时持有显式 date_context，并原样传给 apply_mappings()。 |
| app/parsers/excel_reader.py | 读取 .xlsx 时提取单元格日期语义与 workbook epoch。 |
| app/models/pending_resolution.py | PendingResolutionOutcome 与 PendingResolutionResult。 |
| app/services/import_service.py | 将日期失败转为 pending；返回结构化解决结果。 |
| app/services/atomic_workbook_output.py | 同路径拒绝、临时输出、重开校验、原子提交和清理。 |
| app/services/excel_com_service.py | COM 可用性、COM 分析与三种 Excel 格式的原格式填写。 |
| app/services/workbook_fill_coordinator.py | 按环境、后缀与确认状态选择 COM 或兼容引擎。 |
| app/services/workbook_fill_service.py | 明确标记的 openpyxl .xlsx 兼容引擎。 |
| app/services/merge_export_service.py | 接收明确目标路径的安全汇总导出。 |
| app/template_engine/schema.py / generator.py | photo 字段、预填行和受限图片插入。 |
| app/ui/merge_page.py / workbook_fill_page.py / template_page.py | 另存为、兼容模式同意、汇总状态、样式和预填工作流。 |
| app/ui/dialogs/student_selection_dialog.py | 按姓名、学号、班级筛选的学生多选。 |

### Task 1: 日期上下文与保守日期入库（阶段 A）

**Files:**
- Create: tests/test_date_normalization_context.py
- Modify: app/utils/value_normalizer.py
- Modify: app/models/import_session.py
- Modify: app/parsers/excel_reader.py
- Modify: app/services/import_service.py
- Modify: app/services/table_analysis_service.py
- Test: tests/test_v2_safety.py

**Interfaces:**
- Produces: DateNormalization(value: str, is_valid: bool, reason: str | None)。
- Produces: normalize_date(value, *, date_semantic=False, excel_epoch=None) -> DateNormalization。
- Produces: RawWorkbookData(frame, date_context)，其中 date_context 用 (row, column) 索引 ExcelCellDateContext。
- Produces: ImportSession.date_context: dict[tuple[int, int], ExcelCellDateContext]，由 analyze() 构造一次且不可动态附加。
- Consumes: ImportService.apply_mappings() 通过 session.date_context 和当前原始行/列坐标取得 StandardField.DATE 的上下文；不得重新读取工作簿或重新猜测日期。

- [ ] **Step 1: 写入失败测试**

~~~python
def test_numeric_value_is_not_a_date_without_excel_context():
    result = normalize_date(45200)
    assert result.value == "45200"
    assert result.is_valid is False
    assert result.reason == "missing_date_semantics"

def test_serial_date_requires_epoch_and_date_semantics():
    result = normalize_date(
        45200,
        date_semantic=True,
        excel_epoch=datetime(1899, 12, 30),
    )
    assert result.value == "2023-10-01"
    assert result.is_valid is True
~~~

另加 datetime、date、Pandas Timestamp、ISO、斜杠、点号、月底筛选，以及含日期 number format 的真实 xlsx 测试。

- [ ] **Step 2: 运行测试确认失败**

Run: python -m pytest tests/test_date_normalization_context.py tests/test_v2_safety.py -q

Expected: FAIL，因为当前 normalize_date() 会按数值范围推断日期，且不存在 DateNormalization 与上下文读取。

- [ ] **Step 3: 实现最小日期接口**

~~~python
@dataclass(frozen=True)
class DateNormalization:
    value: str
    is_valid: bool
    reason: str | None = None

def normalize_date(value, *, date_semantic=False, excel_epoch=None):
    if isinstance(value, datetime):
        return DateNormalization(value.date().isoformat(), True)
    if isinstance(value, date):
        return DateNormalization(value.isoformat(), True)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not (date_semantic and excel_epoch is not None):
            return DateNormalization(normalize_text(value), False, "missing_date_semantics")
        converted = from_excel(value, epoch=excel_epoch)
        return DateNormalization(converted.date().isoformat(), True)
~~~

保留 read_raw() 的 DataFrame 返回以免破坏其它调用点；增加供 ImportService 使用的上下文读取函数。ImportSession 新增带 default_factory 的 date_context 字段，并由 analyze() 用 RawWorkbookData 显式传入。xlsx 上下文只标记原单元格具有日期 number format 且可取得 workbook epoch 的数值单元格。CSV 与无元数据输入不提供日期序列上下文；禁止在 session 上动态挂属性或在 apply_mappings() 中二次读取源文件。

- [ ] **Step 4: 将无效日期转入 pending**

在 apply_mappings() 中将非空且 is_valid 为 False 的日期保留原文、追加 INVALID_DATE issue，并在 student match 后保持非“正常”状态，使 _persist_records() 创建 pending 而不是 attendance_records。空白日期仍按当前可选字段规则处理。

- [ ] **Step 5: 验证并提交**

Run: python -m pytest tests/test_date_normalization_context.py tests/test_v2_safety.py -q

Expected: PASS，且普通 45200 从不被保存为日期。

~~~bash
git add app/utils/value_normalizer.py app/parsers/excel_reader.py app/services/import_service.py app/services/table_analysis_service.py tests/test_date_normalization_context.py tests/test_v2_safety.py
git commit -m "fix: 严格校验导入日期语义"
~~~

### Task 2: 结构化 pending、换行状态与统一文本安全（阶段 A）

**Files:**
- Create: app/models/pending_resolution.py
- Modify: app/services/import_service.py
- Modify: app/ui/pending_page.py
- Modify: app/services/attendance_transformer.py
- Modify: app/services/excel_export_service.py
- Modify: app/services/class_export_service.py
- Test: tests/test_v2_safety.py, tests/test_statistics.py, tests/test_v21_features.py

**Interfaces:**
- Produces: PendingResolutionOutcome.IMPORTED、EXACT_DUPLICATE_SKIPPED、POSSIBLE_DUPLICATE_REQUIRES_CONFIRMATION。
- Produces: PendingResolutionResult(outcome, attendance_record_id=None, message="")。
- Consumes: resolve_and_import(pending_id, student_id, resolution_note, confirm_possible_duplicate)。
- Guarantees: 只有 IMPORTED 结果携带 attendance_record_id。

- [ ] **Step 1: 写入失败测试**

~~~python
def test_exact_duplicate_returns_structured_skip(imported_service):
    result = imported_service.resolve_and_import(pending_id, student.id)
    assert result.outcome is PendingResolutionOutcome.EXACT_DUPLICATE_SKIPPED
    assert result.attendance_record_id is None

def test_possible_duplicate_requests_confirmation_without_resolving(imported_service):
    result = imported_service.resolve_and_import(pending_id, student.id)
    assert result.outcome is PendingResolutionOutcome.POSSIBLE_DUPLICATE_REQUIRES_CONFIRMATION
    assert pending_status(imported_service.database, pending_id) == "待处理"
~~~

另加 “迟到
缺勤” 与 “迟到
缺勤” 产生两条记录的测试，以及 =SUM(A1:A2)、+CMD、@value 在统计和班级输出中均被转义的测试。

- [ ] **Step 2: 运行测试确认失败**

Run: python -m pytest tests/test_v2_safety.py tests/test_statistics.py tests/test_v21_features.py -q

Expected: FAIL，因为 resolve_and_import() 目前返回 int | None，可能重复依赖异常文本。

- [ ] **Step 3: 实现结果分支**

~~~python
if duplicate_kind == "EXACT_DUPLICATE":
    self.repository.resolve_pending(connection, pending_id, resolution)
    return PendingResolutionResult(EXACT_DUPLICATE_SKIPPED, message=EXACT_MESSAGE)
if duplicate_kind == "POSSIBLE_DUPLICATE" and not confirm_possible_duplicate:
    return PendingResolutionResult(POSSIBLE_DUPLICATE_REQUIRES_CONFIRMATION, message=CONFIRM_MESSAGE)
attendance_id = self.repository.create_attendance(connection, values)
self.repository.resolve_pending(connection, pending_id, resolution)
return PendingResolutionResult(IMPORTED, attendance_id, "已写入正式考勤记录。")
~~~

PendingPage 按 outcome 分支显示和二次确认，绝不以 attendance_record_id 是否为空推断全部状态。异常只保留给不存在/已解决 pending、无效学生等非法调用。保留实际换行的 regex 分隔符，不添加字面反斜杠 n 的错误拆分。

- [ ] **Step 4: 统一导出安全值**

检查 statistics、class export、merge export、template prefill 与 workbook fill 的用户值写入；字符串一律调用 safe_excel_value()，数值计数保持 numeric，受控公式保持公式。

- [ ] **Step 5: 验证并提交**

Run: python -m pytest tests/test_v2_safety.py tests/test_statistics.py tests/test_v21_features.py -q

Expected: PASS，完全重复不会新增记录，可能重复不形成 pending 循环。

- [ ] **Step 6: 完成阶段 A 全量验证**

Run: python -m pytest -q

Expected: 所有既有和新增测试 PASS；局部安全修复不得破坏资料汇总、填表或模板生成测试。

- [ ] **Step 7: 提交阶段 A**

~~~bash
git add app/models/pending_resolution.py app/services/import_service.py app/ui/pending_page.py app/services/attendance_transformer.py app/services/excel_export_service.py app/services/class_export_service.py tests/test_v2_safety.py tests/test_statistics.py tests/test_v21_features.py
git commit -m "fix: 结构化处理待确认重复记录"
~~~

### Task 3: 汇总服务、匹配状态与显式导出（阶段 B）

**Files:**
- Modify: app/services/dataset_merge_service.py
- Modify: app/models/merge_models.py
- Modify: app/services/merge_export_service.py
- Test: tests/test_dataset_merge.py

**Interfaces:**
- Consumes: MergeExportService.export(result, output_path, allow_unresolved=False)。
- Produces: 一个可重新打开且路径严格等于 output_path 的 .xlsx。
- Guarantees: 资料汇总仍只存在于 DataWorkspaceService，不写入 attendance_records。

- [ ] **Step 1: 写入失败测试**

~~~python
def test_export_writes_to_requested_path_with_traceability(tmp_path):
    target = tmp_path / "用户选择" / "汇总.xlsx"
    path = MergeExportService().export(result, target)
    assert path == target
    workbook = load_workbook(path, data_only=False)
    assert "汇总说明" in workbook.sheetnames

~~~

保留/补齐纵向字段并集、学号优先、姓名加班级、唯一姓名、重名不自动合并、空值加非空、冲突和来源追溯测试。新增一个初始 unmatched 记录在后续来源按学号或姓名加班级成功合并后必须变为 matched 的统计测试；未匹配计数只统计最终仍 unmatched 的记录。

- [ ] **Step 2: 运行测试确认失败**

Run: python -m pytest tests/test_dataset_merge.py -q

Expected: FAIL，因为当前导出路径由服务生成，且后续成功关联不会修正最初 unmatched 的统计状态。

- [ ] **Step 3: 实现显式路径与最终匹配状态**

MergeExportService 验证 .xlsx 后缀、未解决冲突的明确许可、保存并重开目标。DatasetMergeService 在任何后续来源记录并入既有结果时同步把该结果记录的 match_status 设为 matched，并基于最终 records 重新计算 unmatched 统计；不得保留历史中间状态。

- [ ] **Step 4: 验证并提交**

Run: python -m pytest tests/test_dataset_merge.py -q

Expected: PASS，导出保留 汇总结果、汇总说明、字段冲突 工作表与安全文本，最终匹配数不计入已成功合并记录。

- [ ] **Step 5: 完成阶段 B 全量验证**

Run: python -m pytest -q

Expected: 所有测试 PASS；资料汇总服务更改不得影响导入、模板或 UI。

- [ ] **Step 6: 提交阶段 B**

~~~bash
git add app/services/dataset_merge_service.py app/models/merge_models.py app/services/merge_export_service.py tests/test_dataset_merge.py
git commit -m "feat: 完善资料汇总匹配与导出"
~~~

### Task 4: 资料汇总页面另存为与筛选验收（阶段 C）

**Files:**
- Modify: app/ui/merge_page.py
- Test: tests/test_dataset_merge.py, tests/test_ui_smoke.py

**Interfaces:**
- Consumes: QFileDialog.getSaveFileName(parent, "导出汇总结果", suggested_path, "Excel 工作簿 (*.xlsx)")。
- Produces: 取消时不调用 MergeExportService.export()，选择路径时传入精确路径。
- Guarantees: 页面统计使用阶段 B 已修正的最终 matched/unmatched 状态；筛选仅改变可见行。

- [ ] **Step 1: 写入失败的页面测试**

~~~python
def test_merge_export_cancel_does_not_call_service(page, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: ("", ""))
    monkeypatch.setattr(page.export_service, "export", pytest.fail)
    page.export_result()

def test_merge_export_passes_user_selected_path(page, monkeypatch, tmp_path):
    target = tmp_path / "汇总.xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_: (str(target), ""))
    page.export_result()
    assert target.exists()
~~~

补充全部、有冲突、缺失信息、无法匹配四个筛选的行数和摘要卡片测试。

- [ ] **Step 2: 运行测试确认失败**

Run: python -m pytest tests/test_dataset_merge.py tests/test_ui_smoke.py -q

Expected: FAIL，因为 MergePage 当前没有保存对话框、摘要卡片或筛选控件。

- [ ] **Step 3: 实现页面交互**

使用 exports/资料汇总.xlsx 仅作建议路径；取消立即返回。保留未解决冲突的明确确认对话框后再调用服务。渲染来源文件数、原始行数、最终人数、完整匹配数、无法匹配数、冲突数、缺失信息数；筛选基于不可变的 MergeResult 计算视图，不修改数据或工作区快照。

- [ ] **Step 4: 完成阶段 C 全量验证**

Run: python -m pytest -q

Expected: 所有测试 PASS；离屏 UI 测试确认取消不生成文件，页面不会改变合并结果。

- [ ] **Step 5: 提交阶段 C**

~~~bash
git add app/ui/merge_page.py tests/test_dataset_merge.py tests/test_ui_smoke.py
git commit -m "feat: 完善资料汇总预览与另存为"
~~~

### Task 5: 原子输出与 .xlsx 兼容填充（阶段 D）

**Files:**
- Create: app/services/atomic_workbook_output.py
- Modify: app/models/fill_models.py
- Modify: app/services/workbook_fill_service.py
- Modify: app/parsers/workbook_template_analyzer.py
- Test: tests/test_workbook_fill.py, tests/test_v221_template_visual_sequence.py

**Interfaces:**
- Produces: 通用 AtomicFileOutput(source_path: Path | None, output_path)，提供 temporary_path、commit(validate) 和 cleanup()；保留 AtomicWorkbookOutput 作为该通用事务的兼容别名或删除后统一迁移调用点。
- Consumes: WorkbookFillService.fill(..., output_path, compatibility_accepted=True)。
- Produces: FillResult(output_path, written_rows, skipped_rows, preserved_cells, engine="compatibility")。

- [ ] **Step 1: 写入失败测试**

~~~python
def test_fill_rejects_same_source_and_destination(tmp_path):
    with pytest.raises(ValueError, match="不能覆盖源模板"):
        service.fill(analysis, dataset, mappings,
                     output_path=analysis.template_path,
                     compatibility_accepted=True)

def test_failure_removes_temp_and_keeps_final_absent(tmp_path, monkeypatch):
    target = tmp_path / "完成.xlsx"
    monkeypatch.setattr(service, "_write_workbook",
                        lambda *_: (_ for _ in ()).throw(RuntimeError("write failed")))
    with pytest.raises(RuntimeError):
        service.fill(analysis, dataset, mappings,
                     output_path=target, compatibility_accepted=True)
    assert not target.exists()
    assert not list(tmp_path.glob("*.partial.*"))

def test_atomic_output_without_source_supports_new_workbook(tmp_path):
    target = tmp_path / "新模板.xlsx"
    with AtomicFileOutput(None, target) as transaction:
        transaction.temporary_path.write_bytes(b"workbook")
        transaction.commit(lambda path: path.read_bytes() == b"workbook")
    assert target.read_bytes() == b"workbook"
~~~

另加未接受 compatibility_accepted 时拒绝写入、源码 sha256 不变和现有 merged/formula/行高/列宽/冻结窗格保存测试。

- [ ] **Step 2: 运行测试确认失败**

Run: python -m pytest tests/test_workbook_fill.py tests/test_v221_template_visual_sequence.py -q

Expected: FAIL，因为当前服务自动生成 exports 路径，没有原子输出或兼容同意参数。

- [ ] **Step 3: 实现原子兼容引擎**

~~~python
with AtomicFileOutput(analysis.template_path, output_path) as transaction:
    workbook = load_workbook(analysis.template_path, data_only=False)
    self._write_mapped_rows(workbook[analysis.sheet_name], dataset, mappings)
    workbook.save(transaction.temporary_path)
    transaction.commit(lambda path: load_workbook(path, data_only=False).close())
~~~

临时文件必须在目标文件的父目录且保持目标后缀。source_path 非空时拒绝其 resolve() 等于 output_path；source_path 为 None 时允许新模板生成。commit 仅在完整保存和 reopen 成功后 os.replace 到最终路径。异常分支 close workbook、删除临时文件并原样抛出；最终文件事前存在时只有成功时才替换。

- [ ] **Step 4: 验证并提交**

Run: python -m pytest tests/test_workbook_fill.py tests/test_v221_template_visual_sequence.py -q

Expected: PASS，兼容引擎的保真承诺仅限测试覆盖的属性，绝不声称任意高级对象完全无损。

- [ ] **Step 5: 完成阶段 D 全量验证**

Run: python -m pytest -q

Expected: 所有测试 PASS；原子事务同时覆盖有源模板填写与无源新模板生成，不影响阶段 A–C。

- [ ] **Step 6: 提交阶段 D**

~~~bash
git add app/services/atomic_workbook_output.py app/models/fill_models.py app/services/workbook_fill_service.py app/parsers/workbook_template_analyzer.py tests/test_workbook_fill.py tests/test_v221_template_visual_sequence.py
git commit -m "fix: 原子保存xlsx兼容填充结果"
~~~

### Task 6: COM 默认引擎与无 Excel 降级（阶段 E）

**Files:**
- Create: app/services/excel_com_service.py
- Create: app/services/workbook_fill_coordinator.py
- Modify: app/ui/workbook_fill_page.py
- Modify: app/models/fill_models.py
- Delete: app/services/legacy_excel_converter.py
- Test: tests/test_excel_com_service.py, tests/test_v22_excel_style_xls.py, tests/test_ui_smoke.py

**Interfaces:**
- Produces: ExcelComService.is_available()、list_sheets(path)、analyze(path, sheet_name, header_row)、fill(..., output_path)、validate_output(path)。
- Produces: WorkbookFillCoordinator.list_sheets(path)、analyze(path, sheet_name, header_row)、preview(...)、fill(...)；这些方法统一路由 COM 或兼容引擎。
- Produces: WorkbookFillCoordinator.select_engine(path, compatibility_accepted) -> "com" | "compatibility"。
- Raises: WorkbookFormatPreservationError for unprocessable .xls/.xlsm。
- Guarantees: COM 可用时三种模板格式均走 COM；无 COM 时 .xlsx 仅在明确同意后走兼容引擎。

- [ ] **Step 1: 写入失败的路由与 COM mock 测试**

~~~python
def test_com_available_routes_every_template_suffix(fake_excel, tmp_path):
    coordinator = WorkbookFillCoordinator(com_service=ExcelComService(fake_excel))
    for suffix in (".xls", ".xlsx", ".xlsm"):
        assert coordinator.select_engine(tmp_path / ("模板" + suffix), False) == "com"

def test_no_excel_rejects_legacy_and_macro(tmp_path):
    coordinator = WorkbookFillCoordinator(com_service=UnavailableComService())
    for suffix in (".xls", ".xlsm"):
        with pytest.raises(WorkbookFormatPreservationError, match="Microsoft Excel"):
            coordinator.select_engine(tmp_path / ("模板" + suffix), False)
~~~

另加同后缀临时副本、Save 而非 FileFormat=51 转换、异常清理、COM 重开校验、.xlsx 兼容模式明确同意，以及当前汇总有 unresolved conflicts 或身份歧义时默认禁止进入正式填充的测试。继续入口必须模拟用户 Yes，并断言确认标记被显式传入 coordinator。

- [ ] **Step 2: 运行测试确认失败**

Run: python -m pytest tests/test_excel_com_service.py tests/test_v22_excel_style_xls.py -q

Expected: FAIL，因为当前 LegacyExcelConverter 将 .xls 转换为临时 .xlsx。

- [ ] **Step 3: 实现 COM 原格式副本填写**

~~~python
shutil.copy2(source, transaction.temporary_path)
excel = client.DispatchEx("Excel.Application")
excel.Visible = False
excel.DisplayAlerts = False
workbook = excel.Workbooks.Open(str(transaction.temporary_path.resolve()))
worksheet = workbook.Worksheets(analysis.sheet_name)
# 仅写已映射单元格；按需要复制示例行
workbook.Save()
~~~

finally 中关闭 workbook 和 Excel。临时文件后缀必须等于源/最终后缀。COM 分析 Sheet/表头以支持 .xls/.xlsx/.xlsm；WorkbookFillCoordinator 对 .xls/.xlsm 必须只调用 COM 的 list_sheets/analyze/fill，不能调用 WorkbookTemplateAnalyzer 或依赖转换副本。禁止 SaveAs(FileFormat=51) 或任何后缀变化；win32com 仅在 is_available/fill 时导入。调用 transaction.commit 前，以 Excel COM 重新打开临时 .xls/.xlsm 输出、验证工作表和可读性、关闭 Excel，再执行最终原子替换。

- [ ] **Step 4: 接入 UI 同意与另存为**

选择模板的文件过滤器加入 Excel 模板 (*.xlsx *.xls *.xlsm)。选择模板后由 coordinator 的 list_sheets/analyze 说明实际引擎。无 Excel + .xlsx 时，显示本次操作 openpyxl 兼容模式无法保证任意高级 Office 对象的明确警示；仅 Yes 设置 compatibility_accepted。无 Excel + .xls/.xlsm 直接说明拒绝原因。当前资料汇总结果若有 unresolved conflicts 或身份歧义，默认阻止进入正式填写并提示先处理；只有额外 Yes 确认才将 allow_unresolved_merge=True 传给 coordinator，且最终提示必须说明该确认。最终路径来自 QFileDialog.getSaveFileName，默认 <stem>_已填写<suffix>；取消或源路径相同都不能写入。

- [ ] **Step 5: 验证并提交**

Run: python -m pytest tests/test_excel_com_service.py tests/test_v22_excel_style_xls.py tests/test_workbook_fill.py tests/test_ui_smoke.py -q

Expected: PASS；任何测试都不允许 .xls/.xlsm 被转换成 .xlsx。

- [ ] **Step 6: 完成阶段 E 全量验证**

Run: python -m pytest -q

Expected: 所有测试 PASS；COM mock 覆盖重开校验，兼容模式和合并歧义确认不会降低默认安全门槛。

- [ ] **Step 7: 提交阶段 E**

~~~bash
git add app/services/excel_com_service.py app/services/workbook_fill_coordinator.py app/ui/workbook_fill_page.py app/models/fill_models.py tests/test_excel_com_service.py tests/test_v22_excel_style_xls.py tests/test_ui_smoke.py
git rm app/services/legacy_excel_converter.py
git commit -m "feat: 使用COM高保真填写Excel模板"
~~~

### Task 7: 模板 Schema、照片和外部另存为（阶段 F）

**Files:**
- Modify: requirements.txt
- Modify: app/template_engine/schema.py
- Modify: app/template_engine/generator.py
- Modify: app/services/template_service.py
- Modify: app/template_engine/template_manager.py
- Modify: app/services/workbook_fill_service.py
- Modify: app/services/excel_com_service.py
- Test: tests/test_templates.py, tests/test_template_photo.py, tests/test_workbook_fill.py

**Interfaces:**
- Produces: FIELD_TYPES 包含 photo。
- Produces: TemplateGenerator.generate(schema, output_path, prefill_rows=[]) -> Path。
- Consumes: 最终 output_path 和标准字段键的 prefill_rows。
- Raises: PhotoInsertError(field_name, row_number, path) before final atomic commit.
- Guarantees: 输入区数据行数为 max(schema.default_rows, len(prefill_rows))，绝不因预填人数大于 default_rows 而截断。
- Guarantees: TemplateArtifact 继续表示 templates/ 内部管理副本（schema.json 加管理用 workbook）；用户选择的外部路径是另存副本，不替换 artifact.workbook_path。

- [ ] **Step 1: 写入失败测试**

~~~python
def test_photo_field_is_valid_and_allocates_input_area(tmp_path):
    path = TemplateGenerator().generate(schema_with_photo(), tmp_path / "照片模板.xlsx")
    sheet = load_workbook(path)["录入"]
    assert sheet.column_dimensions["A"].width >= 18
    assert sheet.row_dimensions[2].height >= 80

def test_missing_photo_does_not_leave_final_workbook(tmp_path):
    with pytest.raises(PhotoInsertError, match="第 2 行"):
        service.generate(schema_with_photo(), tmp_path / "结果.xlsx",
                         prefill_rows=[{"photo": "missing.png"}])
    assert not (tmp_path / "结果.xlsx").exists()

def test_prefill_rows_expand_beyond_default_rows(tmp_path):
    rows = [{"name": "学生" + str(index)} for index in range(5)]
    path = TemplateGenerator().generate(schema_with_default_rows(2), tmp_path / "名单.xlsx", rows)
    assert load_workbook(path)["录入"].max_row >= 6
~~~

另加 PNG/JPG 可重开、尺寸不超出区域、已有模板填充图片、普通预填文本公式安全，以及保存对话框取消不调用生成器测试。

- [ ] **Step 2: 运行测试确认失败**

Run: python -m pytest tests/test_templates.py tests/test_template_photo.py tests/test_workbook_fill.py -q

Expected: FAIL，因为 photo 当前不是合法类型，生成器没有预填和外部 output_path。

- [ ] **Step 3: 实现受限图片和 schema 保存分离**

在 requirements.txt 添加 Pillow；用 Pillow 读取尺寸，以 min(max_width/width, max_height/height, 1) 缩放，锚定目标单元格且不承诺居中。复用该受限图片帮助器到 TemplateGenerator 和兼容 WorkbookFillService。ExcelComService 使用 Excel 的 Shapes/AddPicture API，设置 LockAspectRatio，并将形状限制于目标单元格区域。TemplateGenerator 的输入区数据行数取 max(schema.default_rows, len(prefill_rows))。TemplateManager 继续在 templates/ 中持有 schema.json 加管理用 workbook，并维持 TemplateArtifact 的 list/copy/delete 契约；TemplateService 在该内部 artifact 正常生成后，通过 AtomicFileOutput 生成用户选择的外部另存副本，外部副本不成为 artifact 的存储路径。非图片用户值应用 safe_excel_value()，系统公式保持原样。

- [ ] **Step 4: 验证并提交**

Run: python -m pytest tests/test_templates.py tests/test_template_photo.py tests/test_workbook_fill.py -q

Expected: PASS，文件缺失不会留下半成品，生成的 PNG/JPG 模板可重开。

- [ ] **Step 5: 提交照片和输出契约**

~~~bash
git add requirements.txt app/template_engine/schema.py app/template_engine/generator.py app/services/template_service.py app/template_engine/template_manager.py app/services/workbook_fill_service.py app/services/excel_com_service.py tests/test_templates.py tests/test_template_photo.py tests/test_workbook_fill.py
git commit -m "feat: 支持模板照片字段与自选保存位置"
~~~

### Task 8: 模板页重构、身份预填与学生多选（阶段 F）

**Files:**
- Create: app/ui/dialogs/student_selection_dialog.py
- Modify: app/ui/template_page.py
- Modify: app/ui/workbook_fill_page.py
- Modify: app/services/template_service.py
- Modify: app/ui/main_window.py
- Test: tests/test_template_page_v2.py, tests/test_ui_smoke.py

**Interfaces:**
- Produces: StudentSelectionDialog.selected_students() -> list[Student]。
- Produces: TemplateService.prefill_rows(schema, mode, class_name=None, student_ids=[]) -> list[dict[str, object]]。
- Consumes: mode 为 blank、class 或 selected。
- Guarantees: 仅预填 schema 已声明字段；缺少用户要求的身份字段必须询问，不得静默添加。

- [ ] **Step 1: 写入失败 UI 测试**

~~~python
def test_template_page_has_scrollable_style_panel_and_collapsed_ai(page):
    assert page.scroll_area.widget() is not None
    assert page.style_preview.table.rowCount() == 2
    assert page.ai_toggle.isChecked() is False

def test_selected_students_prefill_only_declared_fields(page, student):
    page.set_generation_mode("selected")
    page.set_selected_students([student])
    rows = page.prefill_rows(schema_with("姓名", "学号"))
    assert rows == [{"name": student.name, "student_number": student.student_number}]
~~~

另加班级模式的姓名/学号/班级/专业/年级/电话/寝室，以及按姓名、学号、班级搜索和多选测试。

- [ ] **Step 2: 运行测试确认失败**

Run: python -m pytest tests/test_template_page_v2.py tests/test_ui_smoke.py -q

Expected: FAIL，因为当前 TemplatePage 使用 splitter、模态样式设置、永久 AI 输入区且无预填模式。

- [ ] **Step 3: 实现页面与多选**

编辑区改为 QScrollArea，顺序为基本信息、生成数据方式、字段、可见样式面板、可折叠 AI、生成操作。样式面板映射现有 WorkbookStyleSchema，提供 标准办公/简洁名单/数据录入/自定义、字号、行高、自动列宽、表头/正文对齐、边框、冻结、筛选以及 姓名|学号|班级|日期|备注 小预览。学生选择对话框只读取 MasterDataService；按 schema standard_field/显示名过滤 row 键；用户拒绝添加缺字段时继续生成但不写该字段。WorkbookFillPage 复用同一对话框作为“指定学生”来源，因此已有模板填写支持学生库、按班级、指定学生、当前汇总结果与单独上传 Excel/CSV，不引入第二套选择实现。

- [ ] **Step 4: 验证并提交**

Run: python -m pytest tests/test_templates.py tests/test_template_photo.py tests/test_template_page_v2.py tests/test_ui_smoke.py -q

Expected: PASS；班级与指定学生预填正确、AI 默认收起、取消保存不生成文件。

- [ ] **Step 5: 完成阶段 F 全量验证**

Run: python -m pytest -q

Expected: 所有测试 PASS；预填行不会截断，内部模板管理与外部另存副本均保持可用。

- [ ] **Step 6: 提交阶段 F 页面工作**

~~~bash
git add app/ui/dialogs/student_selection_dialog.py app/ui/template_page.py app/ui/workbook_fill_page.py app/services/template_service.py app/ui/main_window.py tests/test_template_page_v2.py tests/test_ui_smoke.py
git commit -m "feat: 重构模板页并支持学生预填"
~~~

### Task 9: 全量验证、文档和交付

**Files:**
- Modify: README.md
- Modify: tests/test_ui_smoke.py
- Create: tests/test_startup_smoke.py
- Test: all tests/

**Interfaces:**
- Documents: COM 优先、.xlsx 兼容模式的显式同意、无 Excel 时 .xls/.xlsm 拒绝、原子另存为与照片尺寸限制。
- Produces: 只包含代码、测试和文档的可验证提交；不包括 .env、数据库、真实 Excel 或照片。

- [ ] **Step 1: 添加最终启动覆盖**

~~~python
def test_main_window_builds_merge_fill_and_template_pages(application, services):
    window = MainWindow(*services)
    assert window.merge_page is not None
    assert window.workbook_fill_page is not None
    assert window.template_page is not None
    window.close()
~~~

增加有界入口测试：将 main.PROJECT_DIRECTORY 和 REQUIRED_DIRECTORIES 指向 tmp_path，设置 QT_QPA_PLATFORM=offscreen，并用 QApplication 子类的 exec() 安排 QTimer.singleShot(250, quit)。断言 main.main() 在计时器触发后返回 0；该测试必须关闭窗口并清理 QApplication，不读取真实 data/database.db。

- [ ] **Step 2: 只在行为验证后更新 README**

说明 COM 是 Windows 下三种模板格式的默认引擎；openpyxl 仅是经用户确认的 .xlsx 兼容模式；没有 Excel 时 .xls/.xlsm 被拒绝；用户模板不被修改；每次输出由用户选择；照片仅等比例限制于目标区域。不得声称任意 openpyxl 保存完全高保真，也不得承诺未测试的居中。

- [ ] **Step 3: 运行完整验证**

Run: python -m pytest -q

Expected: 所有基线和新增测试 PASS；单独记录任何环境警告。

Run: python -m pytest tests/test_startup_smoke.py -q

Expected: 在离屏环境创建真实入口的 QApplication、数据库组装和 MainWindow 后于 250ms 内自动退出，不会无限等待。若平台不支持离屏 Qt，记录受限环境并保留完整 UI 测试结果，不把它称为真实桌面启动验证。

- [ ] **Step 4: 检查交付并提交推送**

Run: git diff --check

Run: git status --short

Run: git diff --cached --name-only

Expected: 不暂存 .env、data/database.db、imports/、exports/、templates/、backups/、真实 Excel 或真实照片。

~~~bash
git add README.md tests/test_ui_smoke.py tests/test_startup_smoke.py
git commit -m "docs: 说明高保真填表与兼容模式限制"
git push origin codex/v2-merge-fill
~~~

Expected: 仅普通 fast-forward push，绝不合并 main。
