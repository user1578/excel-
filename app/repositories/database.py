"""SQLite 连接、事务和数据库结构初始化。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "database.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    student_number TEXT NOT NULL UNIQUE,
    class_name TEXT NOT NULL,
    major TEXT,
    grade TEXT,
    phone TEXT,
    dormitory TEXT,
    remark TEXT,
    created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_students_name_class
ON students(name, class_name);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_name TEXT NOT NULL UNIQUE,
    major TEXT,
    grade TEXT,
    student_count INTEGER NOT NULL DEFAULT 0 CHECK(student_count >= 0),
    counselor TEXT,
    remark TEXT,
    created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS class_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    alias_name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_class_aliases_class_id
ON class_aliases(class_id);

CREATE TABLE IF NOT EXISTS dormitories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    building TEXT NOT NULL,
    room_number TEXT NOT NULL,
    standard_name TEXT NOT NULL UNIQUE,
    remark TEXT,
    created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(building, room_number)
);

CREATE TABLE IF NOT EXISTS field_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_field_name TEXT NOT NULL UNIQUE,
    standard_field TEXT NOT NULL,
    confirmed INTEGER NOT NULL DEFAULT 1,
    usage_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, task_type TEXT NOT NULL,
 start_date TEXT, end_date TEXT, remark TEXT, status TEXT NOT NULL DEFAULT '进行中',
 created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ','now')),
 updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS source_files (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, original_name TEXT NOT NULL, original_path TEXT NOT NULL,
 stored_path TEXT NOT NULL, file_type TEXT NOT NULL, file_size INTEGER NOT NULL, file_hash TEXT NOT NULL, sheet_name TEXT,
 imported_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ','now')), record_count INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_source_files_hash_task_sheet ON source_files(file_hash, task_id, sheet_name);
CREATE TABLE IF NOT EXISTS attendance_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, source_file_id INTEGER NOT NULL, source_row_number INTEGER NOT NULL,
 date TEXT, attendance_type TEXT NOT NULL, student_id INTEGER, student_name TEXT, student_number TEXT, class_name TEXT,
 status TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, course TEXT, remark TEXT, raw_data TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ','now')), updated_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE RESTRICT, FOREIGN KEY(source_file_id) REFERENCES source_files(id) ON DELETE RESTRICT,
 FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS pending_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, source_file_id INTEGER NOT NULL, source_row_number INTEGER NOT NULL,
 issue_type TEXT NOT NULL, raw_data TEXT NOT NULL, normalized_data TEXT NOT NULL, suggestion TEXT, status TEXT NOT NULL DEFAULT '待处理',
 resolution TEXT, created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ','now')), resolved_at TEXT,
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE RESTRICT, FOREIGN KEY(source_file_id) REFERENCES source_files(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS import_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, source_file_id INTEGER NOT NULL, total_rows INTEGER NOT NULL,
 success_count INTEGER NOT NULL, pending_count INTEGER NOT NULL, duplicate_count INTEGER NOT NULL, conflict_count INTEGER NOT NULL,
 message TEXT, created_at TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ','now')),
 FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE RESTRICT, FOREIGN KEY(source_file_id) REFERENCES source_files(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_attendance_duplicate_lookup
ON attendance_records(task_id, student_id, date, course, attendance_type, status);
CREATE INDEX IF NOT EXISTS idx_pending_records_status ON pending_records(task_id, status);
CREATE INDEX IF NOT EXISTS idx_import_logs_task ON import_logs(task_id, id);
"""


class DatabaseManager:
    """为每个操作提供独立 SQLite 连接，避免跨层共享游标。"""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or DEFAULT_DATABASE_PATH)

    def initialize(self) -> None:
        """创建数据目录及尚不存在的数据库表。"""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA_SQL)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """提供只读或由调用方自行控制的数据库连接。"""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """执行原子写操作；发生异常时自动回滚。"""
        with self.connection() as connection:
            try:
                connection.execute("BEGIN")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise


def initialize_database(database_path: str | Path | None = None) -> DatabaseManager:
    """初始化数据库并返回可交给 Repository 的连接管理器。"""
    database = DatabaseManager(database_path)
    database.initialize()
    return database
