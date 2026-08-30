"""统一字段定义与字段映射模型。"""
from dataclasses import dataclass
from enum import Enum


class StandardField(str, Enum):
    IGNORE = "ignore"; OTHER = "other"; SEQUENCE = "sequence"; NAME = "name"
    STUDENT_NUMBER = "student_number"; CLASS_NAME = "class_name"; MAJOR = "major"
    GRADE = "grade"; DATE = "date"; COURSE = "course"; LATE = "late"; ABSENT = "absent"
    LEAVE = "leave"; EXPECTED = "expected"; ACTUAL = "actual"; PHONE = "phone"; DORMITORY = "dormitory"
    BUILDING = "building"; ROOM_NUMBER = "room_number"; SCORE = "score"; STATUS = "status"; REMARK = "remark"


FIELD_LABELS = {field: label for field, label in [
    (StandardField.IGNORE,"忽略"),(StandardField.OTHER,"其他"),(StandardField.SEQUENCE,"序号"),
    (StandardField.NAME,"姓名"),(StandardField.STUDENT_NUMBER,"学号"),(StandardField.CLASS_NAME,"班级"),
    (StandardField.MAJOR,"专业"),(StandardField.GRADE,"年级"),(StandardField.DATE,"日期"),
    (StandardField.COURSE,"课程"),(StandardField.LATE,"迟到"),(StandardField.ABSENT,"缺勤"),
    (StandardField.LEAVE,"请假"),(StandardField.EXPECTED,"应到"),(StandardField.ACTUAL,"实到"),(StandardField.PHONE,"联系电话"),
    (StandardField.DORMITORY,"寝室"),(StandardField.BUILDING,"楼栋"),(StandardField.ROOM_NUMBER,"寝室号"),
    (StandardField.SCORE,"分数"),(StandardField.STATUS,"状态"),(StandardField.REMARK,"备注")
]}

@dataclass(frozen=True)
class FieldMapping:
    source_field_name: str
    standard_field: StandardField
    confirmed: bool = True
    usage_count: int = 1
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

@dataclass(frozen=True)
class DetectedField:
    column_index: int
    source_name: str
    detected_field: StandardField
    source: str
    confidence: int
