"""考勤统计的参数化 SQLite 查询。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.repositories.database import DatabaseManager


STANDARD_STATUSES = ("正常", "迟到", "缺勤", "请假")


class StatisticsRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def overview(self, query: Any) -> dict[str, int]:
        where, parameters = self._where(query, "ar")
        sql = f"""SELECT COUNT(*) AS record_count,
            COUNT(DISTINCT CASE WHEN ar.student_id IS NOT NULL THEN CAST(ar.student_id AS TEXT)
                WHEN ar.student_number <> '' THEN 'number:' || ar.student_number END) AS student_count,
            COUNT(DISTINCT ar.class_name) AS class_count,
            COALESCE(SUM(CASE WHEN ar.status = '迟到' THEN ar.count ELSE 0 END), 0) AS late_count,
            COALESCE(SUM(CASE WHEN ar.status = '缺勤' THEN ar.count ELSE 0 END), 0) AS absent_count,
            COALESCE(SUM(CASE WHEN ar.status = '请假' THEN ar.count ELSE 0 END), 0) AS leave_count,
            COALESCE(SUM(CASE WHEN ar.status NOT IN ('正常', '迟到', '缺勤', '请假') THEN ar.count ELSE 0 END), 0) AS other_count
            FROM attendance_records ar {where}"""
        with self.database.connection() as connection:
            row = connection.execute(sql, parameters).fetchone()
        result = dict(row)
        result["abnormal_count"] = result["late_count"] + result["absent_count"] + result["leave_count"] + result["other_count"]
        return {key: int(value or 0) for key, value in result.items()}

    def personal_summary(self, query: Any) -> list[dict[str, Any]]:
        where, parameters = self._where(query, "ar")
        sql = f"""SELECT ar.student_id, ar.student_name AS name, ar.student_number, ar.class_name,
            COALESCE(SUM(CASE WHEN ar.status = '迟到' THEN ar.count ELSE 0 END), 0) AS late_count,
            COALESCE(SUM(CASE WHEN ar.status = '缺勤' THEN ar.count ELSE 0 END), 0) AS absent_count,
            COALESCE(SUM(CASE WHEN ar.status = '请假' THEN ar.count ELSE 0 END), 0) AS leave_count,
            COALESCE(SUM(CASE WHEN ar.status = '正常' THEN ar.count ELSE 0 END), 0) AS normal_count,
            COALESCE(SUM(CASE WHEN ar.status NOT IN ('正常', '迟到', '缺勤', '请假') THEN ar.count ELSE 0 END), 0) AS other_count,
            COUNT(*) AS record_count
            FROM attendance_records ar {where}
            GROUP BY ar.student_id, ar.student_name, ar.student_number, ar.class_name
            ORDER BY (late_count + absent_count + leave_count + other_count) DESC,
                absent_count DESC, late_count DESC, name ASC, student_number ASC"""
        return self._rows(sql, parameters, add_abnormal=True)

    def class_summary(self, query: Any) -> list[dict[str, Any]]:
        where, parameters = self._where(query, "ar")
        sql = f"""SELECT ar.class_name,
            COALESCE(NULLIF(MAX(c.student_count), 0),
                (SELECT COUNT(*) FROM students fallback WHERE fallback.class_name = ar.class_name), 0) AS class_student_count,
            COUNT(DISTINCT CASE WHEN ar.student_id IS NOT NULL THEN CAST(ar.student_id AS TEXT)
                WHEN ar.student_number <> '' THEN 'number:' || ar.student_number END) AS record_student_count,
            COALESCE(SUM(CASE WHEN ar.status = '迟到' THEN ar.count ELSE 0 END), 0) AS late_count,
            COALESCE(SUM(CASE WHEN ar.status = '缺勤' THEN ar.count ELSE 0 END), 0) AS absent_count,
            COALESCE(SUM(CASE WHEN ar.status = '请假' THEN ar.count ELSE 0 END), 0) AS leave_count,
            COALESCE(SUM(CASE WHEN ar.status = '正常' THEN ar.count ELSE 0 END), 0) AS normal_count,
            COALESCE(SUM(CASE WHEN ar.status NOT IN ('正常', '迟到', '缺勤', '请假') THEN ar.count ELSE 0 END), 0) AS other_count,
            COUNT(*) AS record_count
            FROM attendance_records ar
            LEFT JOIN classes c ON c.standard_name = ar.class_name
            {where}
            GROUP BY ar.class_name
            ORDER BY (late_count + absent_count + leave_count + other_count) DESC,
                absent_count DESC, late_count DESC, ar.class_name ASC"""
        return self._rows(sql, parameters, add_abnormal=True)

    def student_detail(self, query: Any, student_id: int) -> list[dict[str, Any]]:
        where, parameters = self._where(query, "ar")
        if where:
            where += " AND ar.student_id = ?"
        else:
            where = " WHERE ar.student_id = ?"
        parameters.append(student_id)
        sql = f"""SELECT ar.date, ar.attendance_type, ar.course, ar.status, ar.count, tasks.name AS task_name,
            source_files.original_name AS source_file_name, source_files.sheet_name, ar.source_row_number, ar.remark
            FROM attendance_records ar
            JOIN tasks ON tasks.id = ar.task_id
            JOIN source_files ON source_files.id = ar.source_file_id
            {where}
            ORDER BY ar.date IS NULL, ar.date DESC, ar.id DESC"""
        return self._rows(sql, parameters)

    def attendance_types(self) -> list[str]:
        with self.database.connection() as connection:
            rows = connection.execute("SELECT DISTINCT attendance_type FROM attendance_records ORDER BY attendance_type").fetchall()
        return [str(row[0]) for row in rows if row[0]]

    def _rows(self, sql: str, parameters: list[object], add_abnormal: bool = False) -> list[dict[str, Any]]:
        with self.database.connection() as connection:
            rows = [dict(row) for row in connection.execute(sql, parameters).fetchall()]
        if add_abnormal:
            for row in rows:
                row["abnormal_count"] = sum(int(row[key] or 0) for key in ("late_count", "absent_count", "leave_count", "other_count"))
        return rows

    @staticmethod
    def _where(query: Any, alias: str) -> tuple[str, list[object]]:
        values = asdict(query)
        clauses: list[str] = []
        parameters: list[object] = []
        prefix = f"{alias}."
        for field, column in (("task_id", "task_id"), ("class_name", "class_name"), ("student_id", "student_id"), ("attendance_type", "attendance_type")):
            value = values[field]
            if value is not None and value != "":
                clauses.append(f"{prefix}{column} = ?")
                parameters.append(value)
        if values["start_date"]:
            clauses.append(f"{prefix}date >= ?")
            parameters.append(values["start_date"])
        if values["end_date"]:
            clauses.append(f"{prefix}date <= ?")
            parameters.append(values["end_date"])
        status = values["status"]
        if status == "其他":
            clauses.append(f"{prefix}status NOT IN ('正常', '迟到', '缺勤', '请假')")
        elif status:
            clauses.append(f"{prefix}status = ?")
            parameters.append(status)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), parameters
