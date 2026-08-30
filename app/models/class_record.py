"""班级及班级别名领域模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassRecord:
    standard_name: str
    major: str | None = None
    grade: str | None = None
    student_count: int = 0
    counselor: str | None = None
    remark: str | None = None
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if not self.standard_name.strip():
            raise ValueError("班级标准名称不能为空")
        if self.student_count < 0:
            raise ValueError("班级人数不能小于零")
        object.__setattr__(self, "standard_name", self.standard_name.strip())


@dataclass(frozen=True)
class ClassAlias:
    class_id: int
    alias_name: str
    id: int | None = None
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.class_id <= 0:
            raise ValueError("班级 ID 必须为正整数")
        if not self.alias_name.strip():
            raise ValueError("班级别名不能为空")
        object.__setattr__(self, "alias_name", self.alias_name.strip())
