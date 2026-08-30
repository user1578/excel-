"""考勤查询与个人、班级统计的业务层。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.repositories.statistics_repository import StatisticsRepository


@dataclass(frozen=True)
class AttendanceQuery:
    task_id: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    class_name: str | None = None
    student_id: int | None = None
    attendance_type: str | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期。")


@dataclass(frozen=True)
class StatisticsResult:
    overview: dict[str, int]
    personal_rows: list[dict[str, Any]]
    class_rows: list[dict[str, Any]]


class StatisticsService:
    def __init__(self, database) -> None:
        self.repository = StatisticsRepository(database)

    def summarize(self, query: AttendanceQuery) -> StatisticsResult:
        return StatisticsResult(self.repository.overview(query), self.repository.personal_summary(query), self.repository.class_summary(query))

    def student_detail(self, query: AttendanceQuery, student_id: int) -> list[dict[str, Any]]:
        return self.repository.student_detail(query, student_id)

    def attendance_types(self) -> list[str]:
        return self.repository.attendance_types()

    @staticmethod
    def dates_for_period(period: str, today: date | None = None) -> tuple[str | None, str | None]:
        today = today or date.today()
        if period == "全部":
            return None, None
        if period == "本周":
            return (today - timedelta(days=today.weekday())).isoformat(), (today + timedelta(days=6 - today.weekday())).isoformat()
        if period == "本月":
            month_end = (date(today.year + (today.month == 12), 1 if today.month == 12 else today.month + 1, 1) - timedelta(days=1))
            return today.replace(day=1).isoformat(), month_end.isoformat()
        raise ValueError("仅“全部”“本周”“本月”可自动计算日期范围。")
