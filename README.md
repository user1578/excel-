# Excel资料整理助手

## 项目简介

Excel资料整理助手是一个 Windows 本地桌面工具，用于维护学生基础资料、导入 Excel/CSV 资料、标准化考勤记录，并完成查询、汇总与 Excel 导出。

学生相关数据以**姓名、学号、班级**为核心字段，用于匹配、追溯和统计。

## 主要功能

- 学生、班级、班级别名和寝室基础库维护
- `.xlsx`、`.csv` 文件导入，支持 Sheet 选择、表头识别和字段映射
- 姓名、学号、班级匹配与班级别名标准化
- 异常数据待确认、文件重复检测和记录重复检测
- 考勤记录正式导入、导入历史和来源追溯
- 个人汇总、班级汇总、学生明细和 Excel 统计结果导出
- 手动创建和管理 Excel 模板
- 使用 DeepSeek 根据自然语言生成本地校验后的模板 Schema

## 技术栈

- Python 3.11（建议）
- PySide6
- SQLite
- pandas
- openpyxl
- DeepSeek API（可选）

## 环境与安装

建议使用 Python 3.11。在项目根目录执行：

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 基础使用流程

1. 在“学生库”“班级库”“寝室库”维护基础资料。
2. 创建整理任务后，在“资料导入”选择 Excel 或 CSV 文件、Sheet、表头和字段映射。
3. 检查学生匹配与“待确认”记录，再执行正式导入。
4. 在“汇总统计”按任务、日期、班级、学生、考勤类型和状态查询；可查看学生明细并导出 `.xlsx`。
5. 在“模板生成”手动建立模板，或填写自然语言需求后由 DeepSeek 生成 Schema，确认预览后再生成 Excel 模板。

## DeepSeek 配置

在程序“设置”页面配置是否启用、API Key、模型名称和 API 地址，并可使用“测试连接”验证配置。

真实 API Key 仅保存在本机 `.env`，不会上传 GitHub；请勿在代码、日志或文档中填写真实 Key。

## 支持格式

- `.xlsx`
- `.csv`

## 项目目录

```text
app/          应用代码（界面、服务、仓储、解析和模板引擎）
config/       配置模块
data/         本地数据库及附件运行目录
imports/      导入文件副本运行目录
exports/      统计导出运行目录
templates/    用户生成模板运行目录
backups/      备份运行目录
tests/        自动化测试与虚构测试 fixture
```

## 测试

```bash
python -m pytest -q
```

## 当前限制

- 暂不支持旧版 `.xls` 文件。
- 暂不支持 OCR、PDF/Word 自动解析和查寝照片管理。
- AI 模板生成依赖网络连接和可用的 DeepSeek API 配置。
- 当前逐人考勤记录不用于直接计算应到、实到或到课率；准确计算这些指标需要后续的班级场次模型。

## 数据安全

用户原始文件不会被程序修改。正式数据库以及 `imports/`、`exports/`、`templates/`、`backups/` 和附件等运行数据默认不上传 GitHub；仓库仅保留必要的 `.gitkeep` 和测试 fixture。
