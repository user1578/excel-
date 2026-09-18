# V2 资料汇总与表格填充设计

## 目标

在已稳定的 V2.2.2 代码之上，以最小增量完成第二版 Excel 整理能力：修复导入数据风险，完善多文件资料汇总，并以格式保真为最高优先级把任意合格数据源填写到用户提供的 Excel 模板；模板生成支持样式、身份预填、照片字段和用户选择保存位置。

## 已核验基线

- 开发分支：`codex/v2-merge-fill`，从 `f14b91f125007c00bf84f1e92af9c65b515cd57d` fast-forward 对齐。
- 初始测试：`python -m pytest -q` 为 149 passed；仅有 pytest 缓存目录权限警告。
- 现有模块已经提供 `DatasetMergeService`、`MergePage`、`WorkbookFillService`、`WorkbookFillPage`、`TemplatePage`、`TemplateSchema`、`TemplateGenerator`、日期与 Excel 文本安全工具。实施只补齐缺口，不重写这些边界。

## 范围和非目标

本轮包含日期、pending 去重、状态拆分和公式注入安全；资料汇总的两个模式和导出；模板副本填充；模板页重构；学生预填；照片字段；另存为。

不包含 OCR、PDF、Word、云同步、照片管理系统、资料源 `.xls` 解析，或让 DeepSeek 直接读写本地文件。任何真实用户 Excel、照片、数据库或 `.env` 均不进入测试和 Git。

## 架构

### 1. 统一规范化与安全写值

`app.utils.value_normalizer.normalize_date()` 是日期唯一入口。它将 `datetime`、`date`、Pandas Timestamp 和明确的 ISO、斜杠、点号或中文年月日格式转换为 `YYYY-MM-DD`；未能可靠识别的输入返回可显示的原值和失败状态，而不是猜测日期。Excel 数字日期序列只有在解析器已知工作簿日期系统，并且原单元格具有日期语义（例如日期 number format 或读取器明确标注）时才转换；普通数字不得按范围猜成日期。导入服务据此将记录放入待确认或记录明确的异常，禁止非法日期进入 `attendance_records`。

`app.utils.excel_safety.safe_excel_value()` 是所有用户来源文本进入 Excel 的唯一安全出口。以 `= + - @`、Tab 或回车开始的文本前置单引号；真实系统公式仍由模板生成器和序号功能直接写入。统计导出、班级导出、资料汇总、模板生成预填、xlsx 填充和 COM 填充必须经过同一工具。

### 2. 导入修复

`ImportService.resolve_and_import()` 在人工选择学生且补齐身份字段后，重新构造标准考勤值并运行现有重复判断。该方法返回结构化 `PendingResolutionResult`，包含 `outcome`、可选的 `attendance_record_id` 和面向界面的说明；调用方不得假定任意已解决 pending 都有记录 ID：

- `imported`：新建正式记录，返回其 `attendance_record_id`。
- `exact_duplicate_skipped`：将 pending 标记已解决，resolution 写入“人工确认后发现正式记录已存在，完全重复未再次导入”，不插入记录，`attendance_record_id` 为 `None`。
- `possible_duplicate_requires_confirmation`：保持 pending 待处理，返回要求明确二次确认的结果，`attendance_record_id` 为 `None`，且不能新建第二个 pending；确认后才可返回 `imported`。

`AttendanceTransformer` 以实际换行和 `、 , ， ; ； /` 为分隔符拆分状态；字符串中的字面字符 `\\n` 不作为真实换行误拆。每个非空状态生成一条记录。

### 3. 临时资料汇总工作区

现有 `TableDataset`、`TableRow`、`Provenance`、`MergeResult` 和 `DataWorkspaceService` 继续作为内存工作区，不写入 `attendance_records`。

- 直接合并：按标准字段和自定义字段的并集纵向追加，缺列为空，并保留文件、Sheet、行号来源。
- 人员关联：严格按相同非空学号、姓名加规范化班级、唯一且无矛盾身份线索的姓名依次匹配；重名或不同非空学号绝不自动关联。
- 合并规则：相同非空值合并；空值与非空值取非空；两个不同非空值产生 `MergeConflict`，默认显示 A 值但未解决。界面可选 A、B、保留已有或手工输入，并刷新工作区快照。

`MergeExportService` 接受明确的输出路径；若未解决冲突，只有 UI 取得用户明确许可时才导出。导出使用“汇总结果”“汇总说明”和必要时“字段冲突”工作表，写入合并方式、来源文件、Sheet、匹配规则、生成时间和追溯信息。

### 4. 高保真表格填充

模板永远只读，格式保真优先于“必须填写成功”。Service 层拒绝源模板路径与输出路径相同的调用。实际写入遵循“临时输出 → 完整写入与可重开校验 → 成功后原子替换到最终路径”：写入或校验失败时删除临时副本，最终路径不留下半成品。

- Windows 检测到可用 Microsoft Excel 时：`.xls`、`.xlsx` 与 `.xlsm` 一律默认选择 `ExcelComWorkbookFillService`。COM 先复制源文件，再后台只写指定区域，并以原扩展名保存；由 Excel 本身保留字体、边框、图片、图表、隐藏对象、宏和其它 Office 特性。非左上角 merged cell 映射在预览和写入前都明确拒绝。
- 无 Microsoft Excel 时：普通 `.xlsx` 只可作为**兼容模式**由 `WorkbookFillService` 使用 openpyxl 处理。UI 必须清楚说明兼容模式无法保证保存任意高级对象，并要求用户逐次明确接受后才允许写入；兼容模式仍保留已有 Sheet、公式、合并单元格、行高、列宽、冻结窗格与打印属性的回归测试。
- 无 Microsoft Excel 时：`.xls` 与 `.xlsm` 明确拒绝，不降级、不转换、不删除宏，也不产生输出文件。`.xlsm` 仅可在 COM 可用时原扩展名保存。
- 填充数据源保持为学生库、按班级、指定学生、当前汇总结果和单独上传 `.xlsx/.csv`；现有文本/TXT 来源保持兼容。默认起始行是表头下一行，用户可修改；“示例行”沿用已有冲突策略决定是否覆盖。

输出默认建议 `exports/` 与 `原文件名_已填写.原扩展名`，但每次都由 `QFileDialog.getSaveFileName` 选择最终目录和文件名。取消不创建目标、临时输出或残留文件；目标路径等于源路径时必须在 Service 层拒绝。

### 5. 模板生成、身份预填与照片

`TemplatePage` 改为带滚动区域的顺序布局：基本信息、生成数据方式、可扩展字段表、可见样式设置面板、可折叠 AI 区、生成操作。样式面板提供标准办公、简洁名单、数据录入、自定义，及字号、行高、自动列宽、对齐、边框、冻结首行、自动筛选和小型预览。

模板数据模式为：空白、按班级预填、指定学生预填。班级从现有 `classes` 与 `students` 查询；指定学生通过可搜索、多选的对话框按姓名、学号、班级筛选。只对模板已经声明的姓名、学号、班级、专业、年级、电话、寝室字段预填；缺字段时 UI 提示是否添加，用户未同意则不改 schema。

`FieldSchema` 扩展 `photo` 类型，`TemplateGenerator` 为照片列应用较大列宽和行高。数据值是本地 `.jpg/.jpeg/.png` 路径时，xlsx 生成和填充使用 Pillow 与 openpyxl 等比例缩放并限制于目标单元格区域；只有真正实现居中定位后才在界面和文档承诺居中。文件缺失时给出字段、行号和路径的可见错误，不写入半成品。`.xls/.xlsm` 图片由 COM 插入。CSV 不支持照片。

模板生成 Excel 同样经过另存为，默认名称为 `模板名称.xlsx`；schema 仍保存至内部 `templates/` 供后续编辑。用户取消时仅取消本次 Excel 输出，不创建残留文件。

## 依赖和平台边界

- 保持 Python 3.11、PySide6、pandas、openpyxl、pytest。
- 添加 `Pillow` 用于 xlsx 图片尺寸探测和嵌入。
- `pywin32` 保持 Windows 条件依赖（`sys_platform == "win32"`），必须按需导入；无 pywin32 或无 Excel 不得妨碍应用其它功能启动。

## 阶段与验收

1. 阶段 A：先为四项安全修复写失败测试，包含数字日期没有工作簿日期语义时进入待确认，以及三种结构化 pending 结果；实施后完整测试。
2. 阶段 B：补齐汇总服务、匹配、冲突和安全导出测试，完整测试。
3. 阶段 C：资料汇总页面的文件、Sheet、状态、筛选、冲突和另存为行为测试，完整测试。
4. 阶段 D：xlsx 模板副本、映射、合并单元格、保存取消、输出路径不等于源路径、原子落盘和图片填充测试；兼容模式必须验证明确接受门槛，完整测试。
5. 阶段 E：COM 层以 mock 验证 `.xls/.xlsx/.xlsm` 的默认选择、原扩展名、临时文件清理和无 Excel 时的拒绝降级，完整测试。
6. 阶段 F：模板页布局、样式预览、班级预填、指定学生多选、保存对话框和照片生成测试，完整测试。

所有新增文件使用 `tests/data` 或 pytest `tmp_path`。每阶段均执行 `python -m pytest -q`；最终还要执行离屏 UI 启动冒烟、检查 diff 与敏感文件，并在 `codex/v2-merge-fill` 提交、推送。不得合并 main、强推、重置远端或删除、弱化既有测试。
