"""将 DeepSeek 的受限 JSON 输出转换为本地 TemplateSchema。"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

from app.ai.deepseek_client import DeepSeekClient
from app.models.field_mapping import StandardField
from app.template_engine.schema import FieldSchema, SchemaValidationError, SheetSchema, TemplateSchema


class DeepSeekParser:
    def __init__(self, client: DeepSeekClient) -> None:
        self.client = client

    def generate_schema(self, requirement: str) -> TemplateSchema:
        if not requirement.strip():
            raise ValueError("请输入模板需求。")
        raw = self.client.request_template_json(self._prompt(requirement.strip()))
        try:
            raw = self._extract_json(raw)
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise SchemaValidationError("AI 未返回 JSON 对象。")
            schema = TemplateSchema.from_dict(self._normalize(value))
            schema.validate()
        except (json.JSONDecodeError, SchemaValidationError, ValueError) as error:
            raise SchemaValidationError(f"AI 返回的模板方案无效：{error}") from error
        return self._standardize(schema).ensure_student_core_fields()

    @staticmethod
    def _prompt(requirement: str) -> str:
        domain_rules = ""
        if "早读" in requirement and ("迟到" in requirement or "缺勤" in requirement):
            domain_rules = "早读异常登记必须包含：姓名、学号、班级、日期、迟到、缺勤、请假、备注；不要生成统计 Sheet。\n"
        return """你必须返回 TemplateSchema JSON，不是表格数据 JSON。禁止返回 {"姓名":""}、字段值、示例行或任意其他结构。
唯一允许的结构骨架如下：
{"template_name":"模板名","student_related":true,"description":"说明","default_rows":100,"sheets":[{"name":"数据录入","fields":[{"name":"姓名","field_type":"name","required":true,"default_value":null,"options":[],"data_source":null,"formula":null,"description":"","standard_field":"name","allow_blank":false}]}]}
只能使用字段类型：text, integer, decimal, date, percentage, select, name, student_number, class_name, dormitory, formula。学生相关模板要设 student_related=true。计算字段公式必须只使用 {字段名}、数字、+、-、*、/、()；例如到课率只能写 {实到人数}/{应到人数}。公式禁止开头 =、IFERROR、任何函数、逗号、Excel 单元格坐标、外部链接和宏；本地生成器会安全处理除零。options 使用 []，不要使用 null。只返回一个 JSON 对象，禁止 Markdown 和解释文字。
补充领域规则：""" + domain_rules + "需求：" + requirement

    @staticmethod
    def _extract_json(value: str) -> str:
        text = value.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise SchemaValidationError("AI 未返回 JSON 对象。")
        return text[start:end + 1]

    @staticmethod
    def _normalize(value: dict[str, Any]) -> dict[str, Any]:
        """只处理明确列出的轻微别名，未知值仍交给 Schema 拒绝。"""
        field_types = {"文本": "text", "整数": "integer", "小数": "decimal", "数值": "decimal", "日期": "date", "百分比": "percentage", "下拉选项": "select", "姓名": "name", "学号": "student_number", "班级": "class_name", "寝室": "dormitory", "计算字段": "formula", "number": "decimal"}
        standard_fields = {"姓名": "name", "学号": "student_number", "班级": "class_name", "日期": "date", "课程": "course", "迟到": "late", "缺勤": "absent", "请假": "leave", "应到": "expected", "实到": "actual", "寝室": "dormitory", "楼栋": "building", "寝室号": "room_number", "分数": "score", "状态": "status", "备注": "remark", "联系电话": "phone"}
        for sheet in value.get("sheets", []):
            for field in sheet.get("fields", []):
                if field.get("field_type") in field_types:
                    field["field_type"] = field_types[field["field_type"]]
                if field.get("standard_field") in standard_fields:
                    field["standard_field"] = standard_fields[field["standard_field"]]
                if field.get("name") in {"存在问题", "问题", "物品名称", "数量", "负责人"} and field.get("standard_field") not in set(standard_fields.values()):
                    field["standard_field"] = None
                if isinstance(field.get("formula"), str) and field["formula"].lstrip().startswith("="):
                    field["formula"] = field["formula"].lstrip()[1:].strip()
        return value

    @staticmethod
    def _standardize(schema: TemplateSchema) -> TemplateSchema:
        aliases = {
            "姓名": StandardField.NAME, "学号": StandardField.STUDENT_NUMBER, "班级": StandardField.CLASS_NAME,
            "日期": StandardField.DATE, "检查日期": StandardField.DATE, "课程": StandardField.COURSE,
            "应到": StandardField.EXPECTED, "应到人数": StandardField.EXPECTED, "实到": StandardField.ACTUAL, "实到人数": StandardField.ACTUAL,
            "迟到": StandardField.LATE, "迟到人数": StandardField.LATE, "缺勤": StandardField.ABSENT, "缺勤人数": StandardField.ABSENT,
            "请假": StandardField.LEAVE, "请假人数": StandardField.LEAVE, "寝室": StandardField.DORMITORY,
            "卫生评分": StandardField.SCORE, "分数": StandardField.SCORE, "状态": StandardField.STATUS,
            "备注": StandardField.REMARK, "联系电话": StandardField.PHONE, "手机号": StandardField.PHONE,
        }
        type_defaults = {
            StandardField.NAME: "name", StandardField.STUDENT_NUMBER: "student_number", StandardField.CLASS_NAME: "class_name",
            StandardField.DATE: "date", StandardField.EXPECTED: "integer", StandardField.ACTUAL: "integer", StandardField.LATE: "integer",
            StandardField.ABSENT: "integer", StandardField.LEAVE: "integer", StandardField.DORMITORY: "dormitory", StandardField.SCORE: "decimal",
        }
        sheets = []
        for sheet in schema.sheets:
            fields = []
            for field in sheet.fields:
                standard = StandardField(field.standard_field) if field.standard_field else aliases.get(field.name)
                if not schema.student_related and standard in {StandardField.NAME, StandardField.STUDENT_NUMBER, StandardField.CLASS_NAME} and field.name not in {"姓名", "学号", "班级"}:
                    standard = None
                    field = replace(field, field_type="text", standard_field=None, data_source=None)
                if standard:
                    field = replace(field, standard_field=standard.value, field_type=type_defaults.get(standard, field.field_type))
                    if standard in {StandardField.NAME, StandardField.STUDENT_NUMBER, StandardField.CLASS_NAME}:
                        field = replace(field, required=True, allow_blank=False)
                    if standard is StandardField.CLASS_NAME:
                        field = replace(field, data_source="classes")
                    elif standard is StandardField.DORMITORY:
                        field = replace(field, data_source="dormitories")
                fields.append(field)
            sheets.append(SheetSchema(sheet.name, fields))
        normalized = TemplateSchema(schema.template_name, schema.student_related, schema.description, schema.default_rows, sheets)
        normalized.validate()
        return normalized
