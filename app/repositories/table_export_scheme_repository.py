"""班级名单导出方案的数据访问层。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.repositories.database import DatabaseManager


@dataclass(frozen=True)
class TableExportScheme:
    name: str
    title: str
    configuration: list[dict[str, str]]
    id: int | None = None


class TableExportSchemeRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def list_all(self) -> list[TableExportScheme]:
        with self.database.connection() as connection:
            rows = connection.execute("SELECT * FROM table_export_schemes ORDER BY name").fetchall()
        return [self._from_row(row) for row in rows]

    def get_by_name(self, name: str) -> TableExportScheme | None:
        with self.database.connection() as connection:
            row = connection.execute("SELECT * FROM table_export_schemes WHERE name = ?", (name.strip(),)).fetchone()
        return self._from_row(row) if row else None

    def create(self, scheme: TableExportScheme) -> TableExportScheme:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO table_export_schemes (name, title, configuration_json) VALUES (?, ?, ?)",
                (scheme.name.strip(), scheme.title, json.dumps(scheme.configuration, ensure_ascii=False)),
            )
        return TableExportScheme(scheme.name.strip(), scheme.title, scheme.configuration, cursor.lastrowid)

    def delete(self, scheme_id: int) -> bool:
        with self.database.transaction() as connection:
            return connection.execute("DELETE FROM table_export_schemes WHERE id = ?", (scheme_id,)).rowcount == 1

    @staticmethod
    def _from_row(row) -> TableExportScheme:
        return TableExportScheme(str(row["name"]), str(row["title"] or ""), json.loads(str(row["configuration_json"])), int(row["id"]))
