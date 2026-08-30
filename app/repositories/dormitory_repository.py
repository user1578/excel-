"""寝室表的数据访问层。"""

from __future__ import annotations

from app.models.dormitory import Dormitory
from app.repositories.database import DatabaseManager


class DormitoryRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def create(self, dormitory: Dormitory) -> Dormitory:
        sql = """
        INSERT INTO dormitories (building, room_number, standard_name, remark)
        VALUES (?, ?, ?, ?)
        """
        with self.database.transaction() as connection:
            cursor = connection.execute(
                sql,
                (dormitory.building, dormitory.room_number, dormitory.standard_name, dormitory.remark),
            )
            dormitory_id = cursor.lastrowid
        return self.get_by_id(dormitory_id)  # type: ignore[arg-type]

    def get_by_id(self, dormitory_id: int) -> Dormitory | None:
        return self._fetch_one("SELECT * FROM dormitories WHERE id = ?", (dormitory_id,))

    def get_by_standard_name(self, standard_name: str) -> Dormitory | None:
        return self._fetch_one(
            "SELECT * FROM dormitories WHERE standard_name = ?", (standard_name.strip(),)
        )

    def list_all(self) -> list[Dormitory]:
        return self._fetch_all("SELECT * FROM dormitories ORDER BY standard_name", ())

    def search(self, keyword: str) -> list[Dormitory]:
        pattern = f"%{keyword.strip()}%"
        return self._fetch_all(
            """
            SELECT * FROM dormitories
            WHERE standard_name LIKE ? OR building LIKE ? OR room_number LIKE ?
            ORDER BY standard_name
            """,
            (pattern, pattern, pattern),
        )

    def count(self) -> int:
        with self.database.connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM dormitories").fetchone()[0])

    def update(self, dormitory_id: int, dormitory: Dormitory) -> bool:
        sql = """
        UPDATE dormitories
        SET building = ?, room_number = ?, standard_name = ?, remark = ?,
            updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
        """
        with self.database.transaction() as connection:
            cursor = connection.execute(
                sql,
                (dormitory.building, dormitory.room_number, dormitory.standard_name,
                 dormitory.remark, dormitory_id),
            )
            return cursor.rowcount == 1

    def delete(self, dormitory_id: int) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute("DELETE FROM dormitories WHERE id = ?", (dormitory_id,))
            return cursor.rowcount == 1

    def _fetch_one(self, sql: str, parameters: tuple[object, ...]) -> Dormitory | None:
        with self.database.connection() as connection:
            row = connection.execute(sql, parameters).fetchone()
        return Dormitory(**dict(row)) if row else None

    def _fetch_all(self, sql: str, parameters: tuple[object, ...]) -> list[Dormitory]:
        with self.database.connection() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [Dormitory(**dict(row)) for row in rows]
