from app.models.task import Task
from app.repositories.database import DatabaseManager
class TaskRepository:
 def __init__(self,database):self.database=database
 def create(self,task):
  with self.database.transaction() as c: i=c.execute("INSERT INTO tasks(name,task_type,start_date,end_date,remark,status) VALUES(?,?,?,?,?,?)",(task.name,task.task_type,task.start_date,task.end_date,task.remark,task.status)).lastrowid
  return self.get(i)
 def get(self,i):
  with self.database.connection() as c:r=c.execute("SELECT * FROM tasks WHERE id=?",(i,)).fetchone()
  return Task(**{k:dict(r)[k] for k in Task.__dataclass_fields__ if k in dict(r)}) if r else None
 def list(self):
  with self.database.connection() as c:rows=c.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
  return [Task(**{k:dict(r)[k] for k in Task.__dataclass_fields__ if k in dict(r)}) for r in rows]
 def related_count(self,i):
  with self.database.connection() as c:return sum(int(c.execute(f"SELECT COUNT(*) FROM {t} WHERE task_id=?",(i,)).fetchone()[0]) for t in ("source_files","attendance_records","pending_records","import_logs"))
 def delete(self,i):
  with self.database.transaction() as c:return c.execute("DELETE FROM tasks WHERE id=?",(i,)).rowcount==1
