"""生成 Excel 识别测试资料；可重复执行。"""
from pathlib import Path
from openpyxl import Workbook

ROOT = Path(__file__).parent / "data"

def book(name, rows, sheets=None):
    wb = Workbook(); ws = wb.active; ws.title = "Sheet1"
    for row in rows: ws.append(row)
    for title, data in sheets or []:
        sh = wb.create_sheet(title)
        for row in data: sh.append(row)
    wb.save(ROOT / name)

def main():
    ROOT.mkdir(exist_ok=True)
    book("normal.xlsx", [["姓名","学号","班级","迟到"],["张三","20260001","物联网2401","是"]])
    book("alias_headers.xlsx", [["学生姓名","学生编号","行政班","晚到","未到"],["张三","20260001","物联2401","是","否"]])
    book("title_before_header.xlsx", [["2026年9月份课堂检查情况汇总"],[],["姓名","学号","班级","迟到","缺勤"],["张三","20260001","物联网2401","否","否"]])
    book("missing_student_number.xlsx", [["姓名","班级","迟到"],["张三","物联网2401","是"]])
    book("duplicate_name.xlsx", [["姓名","迟到"],["王晨","是"]])
    book("conflict.xlsx", [["姓名","学号","班级"],["李四","20260001","物联网2401"]])
    book("class_alias.xlsx", [["姓名","学号","班级"],["张三","20260001","物联2401"]])
    book("multi_sheet.xlsx", [["说明"],["第一张不处理"]], [("考勤", [["姓名","学号","班级","迟到"],["张三","20260001","物联网2401","是"]])])
    book("empty.xlsx", [])
    (ROOT / "sample.csv").write_text("姓名,学号,班级,迟到\n张三,20260001,物联网2401,是\n", encoding="utf-8-sig")

if __name__ == "__main__": main()
