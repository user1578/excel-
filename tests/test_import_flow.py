from pathlib import Path
import pytest
from app.models.class_record import ClassRecord
from app.models.field_mapping import StandardField
from app.models.student import Student
from app.repositories.database import DatabaseManager
from app.services.import_service import ImportService
from app.services.master_data_service import MasterDataService

DATA = Path(__file__).parent / "data"

@pytest.fixture
def service(tmp_path):
    db = DatabaseManager(tmp_path / "test.db"); db.initialize(); master = MasterDataService(db)
    c = master.create_class(ClassRecord("物联网2401")); master.create_class(ClassRecord("软件2401")); master.add_class_alias(c.id, "物联2401")
    master.create_student(Student("张三","20260001","物联网2401")); master.create_student(Student("李四","20260002","软件2401")); master.create_student(Student("王晨","20260003","物联网2401")); master.create_student(Student("王晨","20260004","软件2401"))
    return ImportService(db, master)

def parse(service, name, sheet=None):
    session = service.analyze(DATA / name, sheet)
    return service.apply_mappings(session, service.default_mapping(session))

def test_xlsx_csv_sheets_and_header(service):
    assert service.sheets(DATA / "multi_sheet.xlsx") == ["Sheet1", "考勤"]
    assert parse(service,"normal.xlsx").records[0].match_status == "正常"
    assert parse(service,"sample.csv").records[0].normalized_data["name"] == "张三"
    assert service.analyze(DATA / "title_before_header.xlsx").header_row == 2

def test_alias_history_and_standardization(service):
    session = parse(service,"alias_headers.xlsx")
    assert session.records[0].normalized_data["class_name"] == "物联网2401"
    assert [x.detected_field for x in session.fields][:3] == [StandardField.NAME,StandardField.STUDENT_NUMBER,StandardField.CLASS_NAME]
    service.mappings.save("检查结果",StandardField.STATUS)
    assert service.analyze(DATA / "normal.xlsx").fields[0].detected_field == StandardField.NAME

def test_matching_conflict_duplicate_and_completion(service):
    assert parse(service,"missing_student_number.xlsx").records[0].normalized_data["student_number"] == "20260001"
    assert "DUPLICATE_NAME" in parse(service,"duplicate_name.xlsx").records[0].issues
    assert "STUDENT_NUMBER_NAME_CONFLICT" in parse(service,"conflict.xlsx").records[0].issues

def test_mapping_validation_and_empty(service):
    session = service.analyze(DATA / "normal.xlsx")
    with pytest.raises(ValueError): service.apply_mappings(session,{0:StandardField.NAME,1:StandardField.NAME})
    with pytest.raises(ValueError): service.analyze(DATA / "empty.xlsx")
