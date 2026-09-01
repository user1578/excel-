"""手动模式与 AI 模式共用的模板 Schema、序列化和本地校验。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.field_mapping import FIELD_LABELS, StandardField
from app.template_engine.styles import WorkbookStyleSchema, standard_office_style


FIELD_TYPES = ("text", "integer", "decimal", "date", "percentage", "select", "name", "student_number", "class_name", "dormitory", "formula")
FIELD_TYPE_LABELS = {
    "text": "文本", "integer": "整数", "decimal": "小数", "date": "日期", "percentage": "百分比", "select": "下拉选项",
    "name": "姓名", "student_number": "学号", "class_name": "班级", "dormitory": "寝室", "formula": "计算字段",
}
CORE_STANDARD_FIELDS = (StandardField.NAME.value, StandardField.STUDENT_NUMBER.value, StandardField.CLASS_NAME.value)
INVALID_SHEET_CHARACTERS = re.compile(r"[\\/*?:\[\]]")
FIELD_REFERENCE = re.compile(r"\{([^{}]+)\}")


class SchemaValidationError(ValueError):
    """Schema 不可生成模板时的中文错误。"""


@dataclass(frozen=True)
class FieldSchema:
    name: str
    field_type: str = "text"
    required: bool = False
    default_value: str | None = None
    options: list[str] = field(default_factory=list)
    data_source: str | None = None
    formula: str | None = None
    description: str | None = None
    standard_field: str | None = None
    allow_blank: bool = True
    column_width: float | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FieldSchema":
        return cls(
            name=str(value.get("name", "")).strip(), field_type=str(value.get("field_type", "text")), required=bool(value.get("required", False)),
            default_value=None if value.get("default_value") is None else str(value.get("default_value")),
            options=[str(item) for item in (value.get("options") or []) if str(item).strip()], data_source=value.get("data_source"),
            formula=value.get("formula"), description=value.get("description"), standard_field=value.get("standard_field"),
            allow_blank=bool(value.get("allow_blank", True)),
            column_width=float(value["column_width"]) if value.get("column_width") not in (None, "") else None,
        )


@dataclass(frozen=True)
class SheetSchema:
    name: str
    fields: list[FieldSchema] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SheetSchema":
        return cls(str(value.get("name", "")).strip(), [FieldSchema.from_dict(item) for item in (value.get("fields") or [])])


@dataclass(frozen=True)
class TemplateSchema:
    template_name: str
    student_related: bool = False
    description: str | None = None
    default_rows: int = 100
    sheets: list[SheetSchema] = field(default_factory=list)
    style: WorkbookStyleSchema = field(default_factory=standard_office_style)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TemplateSchema":
        return cls(
            template_name=str(value.get("template_name", "")).strip(), student_related=bool(value.get("student_related", False)),
            description=value.get("description"), default_rows=int(value.get("default_rows") or 100),
            sheets=[SheetSchema.from_dict(item) for item in (value.get("sheets") or [])],
            style=WorkbookStyleSchema.from_dict(value.get("style")),
        )

    @classmethod
    def from_json(cls, raw_json: str) -> "TemplateSchema":
        try:
            value = json.loads(raw_json)
        except json.JSONDecodeError as error:
            raise SchemaValidationError("模板配置不是合法 JSON。") from error
        if not isinstance(value, dict):
            raise SchemaValidationError("模板配置必须是 JSON 对象。")
        schema = cls.from_dict(value)
        schema.validate()
        return schema

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def validate(self) -> None:
        if not self.template_name:
            raise SchemaValidationError("模板名称不能为空。")
        if self.default_rows < 1 or self.default_rows > 10000:
            raise SchemaValidationError("预生成空白行数必须在 1 到 10000 之间。")
        if not self.sheets:
            raise SchemaValidationError("模板至少需要一个工作表。")
        try:
            self.style.validate()
        except ValueError as error:
            raise SchemaValidationError(str(error)) from error
        sheet_names: set[str] = set()
        for sheet in self.sheets:
            if not sheet.name or len(sheet.name) > 31 or INVALID_SHEET_CHARACTERS.search(sheet.name):
                raise SchemaValidationError(f"工作表名称不合法：{sheet.name or '空名称'}。")
            if sheet.name in sheet_names:
                raise SchemaValidationError(f"工作表名称重复：{sheet.name}。")
            sheet_names.add(sheet.name)
            if not sheet.fields:
                raise SchemaValidationError(f"工作表“{sheet.name}”至少需要一个字段。")
            self._validate_fields(sheet)

    @staticmethod
    def _validate_fields(sheet: SheetSchema) -> None:
        names = [field_schema.name for field_schema in sheet.fields]
        if any(not name for name in names):
            raise SchemaValidationError(f"工作表“{sheet.name}”存在空字段名。")
        if len(names) != len(set(names)):
            duplicate = next(name for name in names if names.count(name) > 1)
            raise SchemaValidationError(f"工作表“{sheet.name}”字段名重复：{duplicate}。")
        all_names = set(names)
        core_fields: set[str] = set()
        for field_schema in sheet.fields:
            if field_schema.name.startswith("="):
                raise SchemaValidationError(f"字段“{field_schema.name}”不能以 = 开头。")
            if field_schema.default_value and field_schema.default_value.lstrip().startswith("="):
                raise SchemaValidationError(f"字段“{field_schema.name}”默认值不能包含 Excel 公式。")
            if any(option.lstrip().startswith("=") for option in field_schema.options):
                raise SchemaValidationError(f"字段“{field_schema.name}”下拉选项不能包含 Excel 公式。")
            if field_schema.field_type not in FIELD_TYPES:
                raise SchemaValidationError(f"字段“{field_schema.name}”类型不支持。")
            if field_schema.column_width is not None and not 5 <= field_schema.column_width <= 80:
                raise SchemaValidationError(f"字段“{field_schema.name}”列宽必须在 5 到 80 之间。")
            if field_schema.standard_field:
                try:
                    StandardField(field_schema.standard_field)
                except ValueError as error:
                    raise SchemaValidationError(f"字段“{field_schema.name}”的标准字段不合法。") from error
                if field_schema.standard_field in CORE_STANDARD_FIELDS:
                    if field_schema.standard_field in core_fields:
                        raise SchemaValidationError(f"工作表“{sheet.name}”核心字段重复。")
                    core_fields.add(field_schema.standard_field)
            if field_schema.field_type == "select" and not field_schema.options and field_schema.data_source not in {"classes", "dormitories"}:
                raise SchemaValidationError(f"下拉字段“{field_schema.name}”必须配置选项或数据源。")
            if field_schema.field_type == "formula":
                TemplateSchema._validate_formula(field_schema, all_names)

    @staticmethod
    def _validate_formula(field_schema: FieldSchema, available_names: set[str]) -> None:
        expression = (field_schema.formula or "").strip()
        if not expression:
            raise SchemaValidationError(f"计算字段“{field_schema.name}”必须配置公式。")
        references = FIELD_REFERENCE.findall(expression)
        if not references:
            raise SchemaValidationError(f"计算字段“{field_schema.name}”必须使用 {{字段名称}} 引用字段。")
        for reference in references:
            if reference not in available_names:
                raise SchemaValidationError(f"公式引用的字段不存在：{reference}。")
        residual = FIELD_REFERENCE.sub("0", expression)
        if not re.fullmatch(r"[\d\s()+\-*/.]+", residual):
            raise SchemaValidationError(f"计算字段“{field_schema.name}”公式仅支持 +、-、*、/、() 和字段引用。")

    def ensure_student_core_fields(self) -> "TemplateSchema":
        if not self.student_related:
            return self
        primary = self.sheets[0]
        existing = {field.standard_field: field for field in primary.fields if field.standard_field in CORE_STANDARD_FIELDS}
        core_fields = [existing.get(standard, core_field_schema(standard)) for standard in CORE_STANDARD_FIELDS]
        remaining = [field for field in primary.fields if field.standard_field not in CORE_STANDARD_FIELDS]
        updated = SheetSchema(primary.name, core_fields + remaining)
        return TemplateSchema(self.template_name, self.student_related, self.description, self.default_rows, [updated, *self.sheets[1:]], self.style)


def core_field_schema(standard_field: str) -> FieldSchema:
    field = StandardField(standard_field)
    mapping = {StandardField.NAME: "name", StandardField.STUDENT_NUMBER: "student_number", StandardField.CLASS_NAME: "class_name"}
    return FieldSchema(FIELD_LABELS[field], mapping[field], required=True, allow_blank=False, data_source="classes" if field is StandardField.CLASS_NAME else None, standard_field=field.value, description="学生核心身份字段")
