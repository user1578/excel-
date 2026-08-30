"""将一行标准化导入数据拆分为一至多条考勤事实。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.parsed_record import ParsedRecord


@dataclass(frozen=True)
class AttendanceEntry:
    """可写入 attendance_records 的单条考勤信息。"""

    status: str
    count: int = 1
    attendance_type: str = "课堂考勤"


class AttendanceTransformer:
    """识别“迟到、缺勤、请假、状态”列，并使每种状态独立成记录。"""

    STATUS_FIELDS = {"late": "迟到", "absent": "缺勤", "leave": "请假"}
    NEGATIVE_VALUES = {"", "0", "否", "无", "正常", "false", "no", "n", "nan", "none", "null"}

    def transform(self, record: ParsedRecord, complete_attendance: bool = False) -> list[AttendanceEntry]:
        data = record.normalized_data
        entries: list[AttendanceEntry] = []
        for field, status in self.STATUS_FIELDS.items():
            value = self._clean(data.get(field))
            if value.lower() not in self.NEGATIVE_VALUES:
                entries.append(AttendanceEntry(status, self._count(value)))

        status_value = self._clean(data.get("status"))
        if status_value:
            for status in re.split(r"[、,，;；/\\n]+", status_value):
                clean = status.strip()
                if clean and clean.lower() not in self.NEGATIVE_VALUES:
                    entries.append(AttendanceEntry(clean, 1))

        return entries or ([AttendanceEntry("正常")] if complete_attendance else [])

    @staticmethod
    def _clean(value: object) -> str:
        return "" if value is None else str(value).strip()

    @staticmethod
    def _count(value: str) -> int:
        try:
            return max(1, int(float(value)))
        except ValueError:
            return 1
