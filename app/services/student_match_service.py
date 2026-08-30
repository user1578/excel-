"""严格的学生匹配与补全规则。"""
from app.models.field_mapping import StandardField
from app.models.parsed_record import ParsedRecord
from app.services.master_data_service import MasterDataService

class StudentMatchService:
 def __init__(self, master:MasterDataService): self.master=master
 def match(self, record:ParsedRecord)->ParsedRecord:
  d=record.normalized_data; name=d.get(StandardField.NAME.value); number=d.get(StandardField.STUDENT_NUMBER.value); class_name=d.get(StandardField.CLASS_NAME.value)
  if class_name:
   standard=self.master.resolve_class_name(str(class_name))
   if standard: d[StandardField.CLASS_NAME.value]=standard; record.field_sources[StandardField.CLASS_NAME.value]="班级别名标准化"
   else: record.issues.append("UNKNOWN_CLASS")
  student=None
  if number:
   student=self.master.get_student_by_number(str(number))
   if not student: record.issues.append("STUDENT_NOT_FOUND")
   else:
    if name and name!=student.name: record.issues.append("STUDENT_NUMBER_NAME_CONFLICT")
    if class_name and d.get(StandardField.CLASS_NAME.value)!=student.class_name: record.issues.append("CLASS_CONFLICT")
  elif name and d.get(StandardField.CLASS_NAME.value):
   found=self.master.find_students_by_name_and_class(str(name),str(d[StandardField.CLASS_NAME.value])); student=found[0] if len(found)==1 else None
   if not found: record.issues.append("STUDENT_NOT_FOUND")
   if len(found)>1: record.issues.append("DUPLICATE_NAME")
  elif name:
   found=self.master.find_students_by_name(str(name)); student=found[0] if len(found)==1 else None
   if len(found)>1: record.issues.append("DUPLICATE_NAME")
   elif not found: record.issues.append("STUDENT_NOT_FOUND")
  else: record.issues.append("MISSING_NAME")
  if student:
   record.student_id=student.id
   for field,value in ((StandardField.NAME,student.name),(StandardField.STUDENT_NUMBER,student.student_number),(StandardField.CLASS_NAME,student.class_name)):
    if not d.get(field.value): d[field.value]=value; record.field_sources[field.value]="学生库补全"
  if any(x in record.issues for x in ("STUDENT_NUMBER_NAME_CONFLICT","CLASS_CONFLICT")): record.match_status="冲突"
  elif student and not record.issues: record.match_status="正常"
  else: record.match_status="待确认" if any(x in record.issues for x in ("DUPLICATE_NAME","STUDENT_NOT_FOUND","MISSING_NAME")) else "未匹配"
  return record
