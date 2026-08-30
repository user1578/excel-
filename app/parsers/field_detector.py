"""字段别名与内容特征识别。"""
from __future__ import annotations
import re
import pandas as pd
from app.models.field_mapping import DetectedField, StandardField

ALIASES = {
 StandardField.NAME:{"姓名","学生姓名","名字","学生名字","学生"}, StandardField.STUDENT_NUMBER:{"学号","学生学号","学生编号","学籍号","编号"},
 StandardField.CLASS_NAME:{"班级","行政班","所在班级","专业班级","学生班级"}, StandardField.LATE:{"迟到","晚到","迟到人员","迟到名单","迟到学生"},
 StandardField.ABSENT:{"缺勤","缺席","未到","未到人员","缺课","缺勤人员"}, StandardField.LEAVE:{"请假","请假人员","请假学生"},
 StandardField.EXPECTED:{"应到","应到人数","应到数","总人数"}, StandardField.ACTUAL:{"实到","实到人数","到课人数","实际到课"}, StandardField.PHONE:{"联系电话","手机","手机号","电话"},
 StandardField.DATE:{"日期","时间","检查日期","考勤日期"}, StandardField.COURSE:{"课程","课程名称","科目"},
 StandardField.DORMITORY:{"寝室","宿舍","寝室号","宿舍号"}, StandardField.REMARK:{"备注","说明","情况说明"}, StandardField.SEQUENCE:{"序号"}, StandardField.STATUS:{"状态"}, StandardField.MAJOR:{"专业"}, StandardField.GRADE:{"年级"}, StandardField.SCORE:{"分数"}, StandardField.BUILDING:{"楼栋"}, StandardField.ROOM_NUMBER:{"房间号"}
}
def detect_field(index:int, name:str, values:pd.Series, history:StandardField|None=None) -> DetectedField:
    clean=name.strip()
    if history: return DetectedField(index,clean,history,"历史映射",100)
    for field, aliases in ALIASES.items():
        if clean in aliases: return DetectedField(index,clean,field,"标准名称" if clean==next(iter({x for x in aliases if x==clean}),None) and clean in {"姓名","学号","班级","日期","课程","备注","状态","专业","年级","序号"} else "别名识别",95)
    values=[str(v).strip() for v in values.dropna().head(30) if str(v).strip()]
    if values and sum(bool(re.fullmatch(r"\d{6,20}",v)) for v in values)/len(values)>.7: return DetectedField(index,clean,StandardField.STUDENT_NUMBER,"内容特征",55)
    if values and sum(bool(re.search(r"\d{4}[-/.年]\d{1,2}",v)) for v in values)/len(values)>.5: return DetectedField(index,clean,StandardField.DATE,"内容特征",50)
    return DetectedField(index,clean,StandardField.OTHER,"未知",0)
