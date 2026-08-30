"""导入业务表的数据访问层；调用方可传入同一事务连接。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.repositories.database import DatabaseManager


class ImportRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def find_source_duplicate(self, task_id: int, file_hash: str, sheet_name: str | None) -> sqlite3.Row | None:
        with self.database.connection() as connection:
            return connection.execute(
                "SELECT * FROM source_files WHERE task_id = ? AND file_hash = ? AND sheet_name IS ?",
                (task_id, file_hash, sheet_name),
            ).fetchone()

    def create_source_file(self, connection: sqlite3.Connection, values: dict[str, Any]) -> int:
        cursor = connection.execute(
            """INSERT INTO source_files
            (task_id, original_name, original_path, stored_path, file_type, file_size, file_hash, sheet_name, record_count, status)
            VALUES (:task_id, :original_name, :original_path, :stored_path, :file_type, :file_size, :file_hash, :sheet_name, :record_count, :status)""",
            values,
        )
        return int(cursor.lastrowid)

    def create_attendance(self, connection: sqlite3.Connection, values: dict[str, Any]) -> int:
        cursor = connection.execute(
            """INSERT INTO attendance_records
            (task_id, source_file_id, source_row_number, date, attendance_type, student_id, student_name, student_number,
             class_name, status, count, course, remark, raw_data)
            VALUES (:task_id, :source_file_id, :source_row_number, :date, :attendance_type, :student_id, :student_name,
             :student_number, :class_name, :status, :count, :course, :remark, :raw_data)""",
            values,
        )
        return int(cursor.lastrowid)

    def find_record_duplicate(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str | None:
        exact = connection.execute(
            """SELECT id FROM attendance_records WHERE task_id = :task_id AND student_id = :student_id
            AND date IS :date AND course IS :course AND attendance_type = :attendance_type AND status = :status LIMIT 1""",
            values,
        ).fetchone()
        if exact and values["student_id"] is not None and (values["date"] or values["course"]):
            return "EXACT_DUPLICATE"

        possible = connection.execute(
            """SELECT id FROM attendance_records WHERE task_id = :task_id AND date IS :date AND course IS :course
            AND attendance_type = :attendance_type AND status = :status
            AND ((student_number <> '' AND student_number = :student_number)
              OR (student_name <> '' AND student_name = :student_name AND class_name IS :class_name)) LIMIT 1""",
            values,
        ).fetchone()
        return "POSSIBLE_DUPLICATE" if possible else None

    def create_pending(self, connection: sqlite3.Connection, values: dict[str, Any]) -> int:
        cursor = connection.execute(
            """INSERT INTO pending_records
            (task_id, source_file_id, source_row_number, issue_type, raw_data, normalized_data, suggestion)
            VALUES (:task_id, :source_file_id, :source_row_number, :issue_type, :raw_data, :normalized_data, :suggestion)""",
            values,
        )
        return int(cursor.lastrowid)

    def create_log(self, connection: sqlite3.Connection, values: dict[str, Any]) -> int:
        cursor = connection.execute(
            """INSERT INTO import_logs
            (task_id, source_file_id, total_rows, success_count, pending_count, duplicate_count, conflict_count, message)
            VALUES (:task_id, :source_file_id, :total_rows, :success_count, :pending_count, :duplicate_count, :conflict_count, :message)""",
            values,
        )
        return int(cursor.lastrowid)

    def list_pending(self, task_id: int | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM pending_records"
        params: tuple[object, ...] = ()
        if task_id is not None:
            sql += " WHERE task_id = ?"
            params = (task_id,)
        sql += " ORDER BY CASE status WHEN '待处理' THEN 0 ELSE 1 END, id DESC"
        with self.database.connection() as connection:
            return connection.execute(sql, params).fetchall()

    def get_pending(self, pending_id: int, connection: sqlite3.Connection | None = None) -> sqlite3.Row | None:
        if connection is not None:
            return connection.execute("SELECT * FROM pending_records WHERE id = ?", (pending_id,)).fetchone()
        with self.database.connection() as own_connection:
            return own_connection.execute("SELECT * FROM pending_records WHERE id = ?", (pending_id,)).fetchone()

    def resolve_pending(self, connection: sqlite3.Connection, pending_id: int, resolution: dict[str, Any]) -> None:
        connection.execute(
            """UPDATE pending_records SET status = '已解决', resolution = ?,
            resolved_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?""",
            (json.dumps(resolution, ensure_ascii=False), pending_id),
        )

    def list_logs(self, task_id: int | None = None) -> list[sqlite3.Row]:
        sql = """SELECT import_logs.*, source_files.original_name, source_files.sheet_name, tasks.name AS task_name
        FROM import_logs JOIN source_files ON source_files.id = import_logs.source_file_id
        JOIN tasks ON tasks.id = import_logs.task_id"""
        params: tuple[object, ...] = ()
        if task_id is not None:
            sql += " WHERE import_logs.task_id = ?"
            params = (task_id,)
        sql += " ORDER BY import_logs.id DESC"
        with self.database.connection() as connection:
            return connection.execute(sql, params).fetchall()
