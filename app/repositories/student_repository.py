"""学生表的数据访问层。"""

from __future__ import annotations

from app.models.student import Student
from app.repositories.database import DatabaseManager


class StudentRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def create(self, student: Student) -> Student:
        sql = """
        INSERT INTO students (name, student_number, class_name, major, grade, phone, dormitory, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.database.transaction() as connection:
            cursor = connection.execute(
                sql,
                (student.name, student.student_number, student.class_name, student.major,
                 student.grade, student.phone, student.dormitory, student.remark),
            )
            student_id = cursor.lastrowid
        return self.get_by_id(student_id)  # type: ignore[arg-type]

    def get_by_id(self, student_id: int) -> Student | None:
        return self._fetch_one("SELECT * FROM students WHERE id = ?", (student_id,))

    def get_by_student_number(self, student_number: str) -> Student | None:
        return self._fetch_one(
            "SELECT * FROM students WHERE student_number = ?", (student_number.strip(),)
        )

    def find_by_name_and_class(self, name: str, class_name: str) -> list[Student]:
        return self._fetch_all(
            "SELECT * FROM students WHERE name = ? AND class_name = ? ORDER BY id",
            (name.strip(), class_name.strip()),
        )

    def find_by_name(self, name: str) -> list[Student]:
        return self._fetch_all("SELECT * FROM students WHERE name = ? ORDER BY id", (name.strip(),))

    def list_all(self) -> list[Student]:
        return self._fetch_all("SELECT * FROM students ORDER BY class_name, student_number", ())

    def search(self, keyword: str) -> list[Student]:
        pattern = f"%{keyword.strip()}%"
        return self._fetch_all(
            """
            SELECT * FROM students
            WHERE name LIKE ? OR student_number LIKE ? OR class_name LIKE ?
            ORDER BY class_name, student_number
            """,
            (pattern, pattern, pattern),
        )

    def count(self) -> int:
        return self._count("SELECT COUNT(*) FROM students", ())

    def count_by_class(self, class_name: str) -> int:
        return self._count("SELECT COUNT(*) FROM students WHERE class_name = ?", (class_name,))

    def count_by_dormitory(self, dormitory: str) -> int:
        return self._count("SELECT COUNT(*) FROM students WHERE dormitory = ?", (dormitory,))

    def update(self, student_id: int, student: Student) -> bool:
        sql = """
        UPDATE students
        SET name = ?, student_number = ?, class_name = ?, major = ?, grade = ?, phone = ?,
            dormitory = ?, remark = ?,
            updated_at = STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
        """
        with self.database.transaction() as connection:
            cursor = connection.execute(
                sql,
                (student.name, student.student_number, student.class_name, student.major,
                 student.grade, student.phone, student.dormitory, student.remark, student_id),
            )
            return cursor.rowcount == 1

    def delete(self, student_id: int) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute("DELETE FROM students WHERE id = ?", (student_id,))
            return cursor.rowcount == 1

    def _fetch_one(self, sql: str, parameters: tuple[object, ...]) -> Student | None:
        with self.database.connection() as connection:
            row = connection.execute(sql, parameters).fetchone()
        return Student(**dict(row)) if row else None

    def _fetch_all(self, sql: str, parameters: tuple[object, ...]) -> list[Student]:
        with self.database.connection() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [Student(**dict(row)) for row in rows]

    def _count(self, sql: str, parameters: tuple[object, ...]) -> int:
        with self.database.connection() as connection:
            return int(connection.execute(sql, parameters).fetchone()[0])
