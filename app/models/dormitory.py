"""寝室基础信息领域模型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dormitory:
    building: str
    room_number: str
    standard_name: str
    remark: str | None = None
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.building, "楼栋"),
            (self.room_number, "寝室号"),
            (self.standard_name, "标准寝室名称"),
        ):
            if not value.strip():
                raise ValueError(f"{label}不能为空")
        object.__setattr__(self, "building", self.building.strip())
        object.__setattr__(self, "room_number", self.room_number.strip())
        object.__setattr__(self, "standard_name", self.standard_name.strip())
