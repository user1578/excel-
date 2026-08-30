"""学生基础信息领域模型。"""

from __future__ import annotations

from dataclasses import dataclass


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name}不能为空")
    return normalized


@dataclass(frozen=True)
class Student:
    """姓名、学号、班级是学生相关数据的核心字段。"""

    name: str
    student_number: str
    class_name: str
    major: str | None = None
    grade: str | None = None
    phone: str | None = None
    dormitory: str | None = None
    remark: str | None = None
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required(self.name, "姓名"))
        object.__setattr__(self, "student_number", _required(self.student_number, "学号"))
        object.__setattr__(self, "class_name", _required(self.class_name, "班级"))
