"""用户确认的字段映射历史。"""
from app.models.field_mapping import FieldMapping, StandardField
from app.repositories.database import DatabaseManager

class FieldMappingRepository:
    def __init__(self, database: DatabaseManager) -> None: self.database = database
    def get(self, source_name: str) -> FieldMapping | None:
        with self.database.connection() as c: row=c.execute("SELECT * FROM field_mappings WHERE source_field_name=?",(source_name.strip(),)).fetchone()
        return self._row(row) if row else None
    def save(self, source_name: str, field: StandardField) -> FieldMapping:
        with self.database.transaction() as c:
            c.execute("""INSERT INTO field_mappings(source_field_name,standard_field,confirmed,usage_count)
            VALUES(?,?,1,1) ON CONFLICT(source_field_name) DO UPDATE SET standard_field=excluded.standard_field,
            confirmed=1, usage_count=field_mappings.usage_count+1, updated_at=STRFTIME('%Y-%m-%dT%H:%M:%fZ','now')""",(source_name.strip(),field.value))
        return self.get(source_name)  # type: ignore[return-value]
    def _row(self,row) -> FieldMapping:
        d=dict(row); d["standard_field"]=StandardField(d["standard_field"]); d["confirmed"]=bool(d["confirmed"]); return FieldMapping(**d)
