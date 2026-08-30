from dataclasses import dataclass
@dataclass(frozen=True)
class Task:
 name:str; task_type:str="考勤"; start_date:str|None=None; end_date:str|None=None; remark:str|None=None; status:str="进行中"; id:int|None=None
