from app.repositories.task_repository import TaskRepository
class TaskInUseError(ValueError): pass
class TaskService:
 def __init__(self,database):self.repo=TaskRepository(database)
 def create(self,task):return self.repo.create(task)
 def list(self):return self.repo.list()
 def delete(self,i):
  if self.repo.related_count(i):raise TaskInUseError("该任务已关联来源文件、正式记录、待确认记录或导入日志，不能删除。")
  return self.repo.delete(i)
