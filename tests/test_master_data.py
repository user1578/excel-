"""基础数据库与基础资料 CRUD 测试。"""

from __future__ import annotations

import sqlite3
import time

import pytest

from app.models.class_record import ClassRecord
from app.models.dormitory import Dormitory
from app.models.student import Student
from app.repositories.database import DatabaseManager
from app.services.master_data_service import (
    ClassInUseError,
    DormitoryInUseError,
    DuplicateStudentNumberError,
    MasterDataService,
)


@pytest.fixture
def service(tmp_path):
    database = DatabaseManager(tmp_path / "data" / "database.db")
    database.initialize()
    return MasterDataService(database)


def test_database_initialization_creates_file_and_tables(service, tmp_path):
    assert (tmp_path / "data" / "database.db").exists()
    with service.students.database.connection() as connection:
        tables = {row["name"] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
    assert {"students", "classes", "class_aliases", "dormitories"}.issubset(tables)


def test_create_student_and_find_by_student_number(service):
    created = service.create_student(Student("张三", "20260001", "物联网2401", major="物联网工程"))

    found = service.get_student_by_number("20260001")

    assert created.id is not None
    assert found is not None
    assert found.name == "张三"
    assert found.class_name == "物联网2401"


def test_duplicate_student_number_is_rejected(service):
    service.create_student(Student("张三", "20260001", "物联网2401"))

    with pytest.raises(DuplicateStudentNumberError):
        service.create_student(Student("李四", "20260001", "软件2401"))


def test_student_number_is_also_unique_at_database_layer(service):
    service.students.create(Student("张三", "20260001", "物联网2401"))

    with pytest.raises(sqlite3.IntegrityError):
        service.students.create(Student("李四", "20260001", "软件2401"))


def test_find_students_by_name_and_class(service):
    service.create_student(Student("张三", "20260001", "物联网2401"))
    service.create_student(Student("张三", "20260002", "软件2401"))

    found = service.find_students_by_name_and_class("张三", "软件2401")

    assert [student.student_number for student in found] == ["20260002"]


def test_find_by_name_returns_all_duplicate_names(service):
    service.create_student(Student("王晨", "20260001", "物联网2401"))
    service.create_student(Student("王晨", "20260002", "软件2401"))

    found = service.find_students_by_name("王晨")

    assert len(found) == 2
    assert {student.class_name for student in found} == {"物联网2401", "软件2401"}


def test_create_class_and_resolve_alias(service):
    created = service.create_class(ClassRecord("物联网2401", major="物联网工程", grade="2024"))
    service.add_class_alias(created.id, "物联2401")
    service.add_class_alias(created.id, "物联网工程2401")

    assert service.resolve_class_name("物联2401") == "物联网2401"
    assert service.resolve_class_name("物联网工程2401") == "物联网2401"
    assert service.resolve_class_name("物联网2401") == "物联网2401"


def test_deleting_class_cascades_to_class_aliases(service):
    created = service.create_class(ClassRecord("物联网2401"))
    service.add_class_alias(created.id, "物联2401")

    assert service.delete_class(created.id)
    with service.students.database.connection() as connection:
        alias_count = connection.execute(
            "SELECT COUNT(*) FROM class_aliases WHERE class_id = ?", (created.id,)
        ).fetchone()[0]
    assert alias_count == 0


def test_foreign_keys_enabled_on_every_connection_and_connections_close(service):
    database = service.students.database
    with database.connection() as first_connection:
        assert first_connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with database.connection() as second_connection:
        assert second_connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    with pytest.raises(sqlite3.ProgrammingError):
        first_connection.execute("SELECT 1")


def test_student_class_alias_is_normalized_and_can_be_queried(service):
    created_class = service.create_class(ClassRecord("物联网2401"))
    service.add_class_alias(created_class.id, "物联2401")
    created_student = service.create_student(Student("张三", "20260001", "物联2401"))

    found = service.find_students_by_name_and_class("张三", "物联2401")

    assert created_student.class_name == "物联网2401"
    assert [student.student_number for student in found] == ["20260001"]


def test_create_update_and_delete_basic_data(service):
    student = service.create_student(Student("张三", "20260001", "物联网2401"))
    assert service.update_student(student.id, Student("张三", "20260001", "物联网2401", remark="已核对"))
    assert service.get_student_by_number("20260001").remark == "已核对"
    assert service.delete_student(student.id)
    assert service.get_student_by_number("20260001") is None

    class_record = service.create_class(ClassRecord("软件2401", student_count=30))
    assert service.update_class(class_record.id, ClassRecord("软件2401", student_count=31))
    assert service.delete_class(class_record.id)

    dormitory = service.create_dormitory(Dormitory("南3", "402", "南3-402"))
    assert service.update_dormitory(dormitory.id, Dormitory("南3", "402", "南3-402", "已检查"))
    assert service.delete_dormitory(dormitory.id)


def test_updated_at_changes_for_every_mutable_basic_record(service):
    student = service.create_student(Student("张三", "20260001", "物联网2401"))
    class_record = service.create_class(ClassRecord("物联网2401"))
    dormitory = service.create_dormitory(Dormitory("南3", "402", "南3-402"))

    time.sleep(0.02)
    assert service.update_student(student.id, Student("张三", "20260001", "物联网2401", remark="已更新"))
    assert service.update_class(class_record.id, ClassRecord("物联网2401", remark="已更新"))
    assert service.update_dormitory(dormitory.id, Dormitory("南3", "402", "南3-402", "已更新"))

    assert service.get_student_by_number("20260001").updated_at != student.updated_at
    assert service.classes.get_by_id(class_record.id).updated_at != class_record.updated_at
    assert service.dormitories.get_by_id(dormitory.id).updated_at != dormitory.updated_at


def test_chinese_phone_and_dormitory_values_round_trip(service):
    created = service.create_student(
        Student(
            "李小雨",
            "20260008",
            "物联网2401",
            phone="13800138000",
            dormitory="南3-402",
            remark="中文备注：已确认",
        )
    )

    found = service.get_student_by_number("20260008")

    assert found is not None
    assert (found.name, found.phone, found.dormitory, found.remark) == (
        created.name,
        "13800138000",
        "南3-402",
        "中文备注：已确认",
    )


def test_list_search_and_count_methods(service):
    service.create_student(Student("张三", "20260001", "物联网2401"))
    service.create_student(Student("李四", "20260002", "软件2401"))
    service.create_class(ClassRecord("物联网2401", major="物联网工程"))
    service.create_class(ClassRecord("软件2401", major="软件工程"))
    service.create_dormitory(Dormitory("南3", "402", "南3-402"))

    assert service.count_students() == 2
    assert [student.student_number for student in service.search_students("张")] == ["20260001"]
    assert [student.student_number for student in service.search_students("软件2401")] == ["20260002"]
    assert service.count_classes() == 2
    assert [item.standard_name for item in service.search_classes("软件")] == ["软件2401"]
    assert service.count_dormitories() == 1
    assert [item.standard_name for item in service.search_dormitories("402")] == ["南3-402"]


def test_cannot_delete_class_or_dormitory_when_students_use_them(service):
    class_record = service.create_class(ClassRecord("物联网2401"))
    dormitory = service.create_dormitory(Dormitory("南3", "402", "南3-402"))
    service.create_student(Student("张三", "20260001", "物联网2401", dormitory="南3-402"))

    with pytest.raises(ClassInUseError):
        service.delete_class(class_record.id)
    with pytest.raises(DormitoryInUseError):
        service.delete_dormitory(dormitory.id)
