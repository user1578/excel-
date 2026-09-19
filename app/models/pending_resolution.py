"""待确认记录人工处理的结构化结果。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PendingResolutionOutcome(str, Enum):
    IMPORTED = "imported"
    EXACT_DUPLICATE_SKIPPED = "exact_duplicate_skipped"
    POSSIBLE_DUPLICATE_REQUIRES_CONFIRMATION = "possible_duplicate_requires_confirmation"


@dataclass(frozen=True)
class PendingResolutionResult:
    outcome: PendingResolutionOutcome
    attendance_record_id: int | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if self.outcome is PendingResolutionOutcome.IMPORTED and self.attendance_record_id is None:
            raise ValueError("导入成功必须包含正式考勤记录 ID。")
        if self.outcome is not PendingResolutionOutcome.IMPORTED and self.attendance_record_id is not None:
            raise ValueError("未导入的处理结果不能包含正式考勤记录 ID。")
