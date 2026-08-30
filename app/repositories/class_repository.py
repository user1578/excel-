"""班级与班级别名的数据访问层。"""

from __future__ import annotations

from app.models.class_record import ClassAlias, ClassRecord
from app.repositories.database import DatabaseManager


class ClassRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def create(self, class_record: ClassRecord) -> ClassRecord:
        sql = """
        INSERT INTO classes (standard_name, major, grade, student_count, counselor, remark)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        with self.database.transaction() as connection:
            cursor = connection.execute(
                sql,
                (class_record.standard_name, class_record.major, class_record.grade,
                 class_record.student_count, class_record.counselor, class_record.remark),
            )
            class_id = cursor.lastrowid
        return self.get_by_id(class_id)  # type: ignore[arg-type]

    def get_by_id(self, class_id: int) -> ClassRecord | None:
        return self._fetch_one("SELECT * FROM classes WHERE id = ?", (class_id,))

    def get_by_standard_name(self, standard_name: str) -> ClassRecord | None:
        return self._fetch_one(
            "SELECT * FROM classes WHERE standard_name = ?", (standard_name.strip(),)
        )

    def list_all(self) -> list[ClassRecord]:
        return self._fetch_all("SELECT * FROM classes ORDER BY standard_name", ())

    def search(self, keyword: str) -> list[ClassRecord]:
        pattern = f"%{keyword.strip()}%"
        return self._fetch_all(
            """
            SELECT * FROM classes
            WHERE standard_name LIKE ? OR major LIKE ? OR grade LIKE ? OR counselor LIKE ?
            ORDER BY standard_name
            """,
            (pattern, pattern, pattern, pattern),
        )

    def count(self) -> int:
        with self.database.connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM classes").fetchone()[0])

    def update(self, class_id: int, class_record: ClassRecord) -> bool:
        sql = """
        UPDATE classes
        SET standard_name = ?, major = ?, grade = ?, student_count = ?, counselor = ?,
            remark = ?, updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
        """
        with self.database.transaction() as connection:
            cursor = connection.execute(
                sql,
                (class_record.standard_name, class_record.major, class_record.grade,
                 class_record.student_count, class_record.counselor, class_record.remark, class_id),
            )
            return cursor.rowcount == 1

    def delete(self, class_id: int) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute("DELETE FROM classes WHERE id = ?", (class_id,))
            return cursor.rowcount == 1

    def create_alias(self, class_id: int, alias_name: str) -> ClassAlias:
        alias = ClassAlias(class_id=class_id, alias_name=alias_name)
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO class_aliases (class_id, alias_name) VALUES (?, ?)",
                (alias.class_id, alias.alias_name),
            )
            alias_id = cursor.lastrowid
        return ClassAlias(id=alias_id, class_id=alias.class_id, alias_name=alias.alias_name)

    def list_aliases(self, class_id: int) -> list[ClassAlias]:
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM class_aliases WHERE class_id = ? ORDER BY alias_name", (class_id,)
            ).fetchall()
        return [ClassAlias(**dict(row)) for row in rows]

    def delete_alias(self, alias_id: int) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute("DELETE FROM class_aliases WHERE id = ?", (alias_id,))
            return cursor.rowcount == 1

    def resolve_standard_name(self, name_or_alias: str) -> str | None:
        sql = """
        SELECT classes.standard_name
        FROM classes
        LEFT JOIN class_aliases ON class_aliases.class_id = classes.id
        WHERE classes.standard_name = ? OR class_aliases.alias_name = ?
        LIMIT 1
        """
        normalized = name_or_alias.strip()
        with self.database.connection() as connection:
            row = connection.execute(sql, (normalized, normalized)).fetchone()
        return str(row["standard_name"]) if row else None

    def _fetch_one(self, sql: str, parameters: tuple[object, ...]) -> ClassRecord | None:
        with self.database.connection() as connection:
            row = connection.execute(sql, parameters).fetchone()
        return ClassRecord(**dict(row)) if row else None

    def _fetch_all(self, sql: str, parameters: tuple[object, ...]) -> list[ClassRecord]:
        with self.database.connection() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [ClassRecord(**dict(row)) for row in rows]
