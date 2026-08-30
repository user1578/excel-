"""学生、班级、寝室基础数据的业务服务。"""

from __future__ import annotations

import sqlite3
from dataclasses import replace

from app.models.class_record import ClassAlias, ClassRecord
from app.models.dormitory import Dormitory
from app.models.student import Student
from app.repositories.class_repository import ClassRepository
from app.repositories.database import DatabaseManager
from app.repositories.dormitory_repository import DormitoryRepository
from app.repositories.student_repository import StudentRepository


class DuplicateStudentNumberError(ValueError):
    """学号已存在时抛出，调用者可据此提示用户处理冲突。"""


class DuplicateClassNameError(ValueError):
    """班级标准名称已存在。"""


class DuplicateClassAliasError(ValueError):
    """班级别名已被占用。"""


class DuplicateDormitoryError(ValueError):
    """标准寝室名称或楼栋寝室号组合已存在。"""


class ClassInUseError(ValueError):
    """存在学生归属该班级，不能删除。"""

    def __init__(self, class_name: str, student_count: int) -> None:
        super().__init__(f"当前有{student_count}名学生属于该班级，请先调整学生班级后再删除。")
        self.class_name = class_name
        self.student_count = student_count


class DormitoryInUseError(ValueError):
    """存在学生使用该寝室，不能删除。"""

    def __init__(self, dormitory_name: str, student_count: int) -> None:
        super().__init__(f"当前有{student_count}名学生使用该寝室，请先处理学生寝室信息后再删除。")
        self.dormitory_name = dormitory_name
        self.student_count = student_count


class MasterDataService:
    """协调 Repository，并集中保存基础数据的业务规则。"""

    def __init__(self, database: DatabaseManager) -> None:
        self.students = StudentRepository(database)
        self.classes = ClassRepository(database)
        self.dormitories = DormitoryRepository(database)

    def create_student(self, student: Student) -> Student:
        try:
            return self.students.create(self._normalize_student_class(student))
        except sqlite3.IntegrityError as error:
            if "students.student_number" in str(error):
                raise DuplicateStudentNumberError(f"学号已存在：{student.student_number}") from error
            raise

    def update_student(self, student_id: int, student: Student) -> bool:
        try:
            return self.students.update(student_id, self._normalize_student_class(student))
        except sqlite3.IntegrityError as error:
            if "students.student_number" in str(error):
                raise DuplicateStudentNumberError(f"学号已存在：{student.student_number}") from error
            raise

    def delete_student(self, student_id: int) -> bool:
        return self.students.delete(student_id)

    def get_student_by_number(self, student_number: str) -> Student | None:
        return self.students.get_by_student_number(student_number)

    def find_students_by_name_and_class(self, name: str, class_name: str) -> list[Student]:
        normalized_class = self.resolve_class_name(class_name) or class_name.strip()
        return self.students.find_by_name_and_class(name, normalized_class)

    def find_students_by_name(self, name: str) -> list[Student]:
        """可返回多个同名学生；本方法绝不自行选择其中一人。"""
        return self.students.find_by_name(name)

    def list_students(self) -> list[Student]:
        return self.students.list_all()

    def search_students(self, keyword: str) -> list[Student]:
        return self.students.search(keyword) if keyword.strip() else self.list_students()

    def count_students(self) -> int:
        return self.students.count()

    def count_students_by_class(self, class_name: str) -> int:
        standard_name = self.resolve_class_name(class_name) or class_name.strip()
        return self.students.count_by_class(standard_name)

    def count_students_by_dormitory(self, dormitory_name: str) -> int:
        return self.students.count_by_dormitory(dormitory_name.strip())

    def create_class(self, class_record: ClassRecord) -> ClassRecord:
        try:
            return self.classes.create(class_record)
        except sqlite3.IntegrityError as error:
            if "classes.standard_name" in str(error):
                raise DuplicateClassNameError(f"班级已存在：{class_record.standard_name}") from error
            raise

    def update_class(self, class_id: int, class_record: ClassRecord) -> bool:
        try:
            return self.classes.update(class_id, class_record)
        except sqlite3.IntegrityError as error:
            if "classes.standard_name" in str(error):
                raise DuplicateClassNameError(f"班级已存在：{class_record.standard_name}") from error
            raise

    def delete_class(self, class_id: int) -> bool:
        class_record = self.classes.get_by_id(class_id)
        if class_record is None:
            return False
        student_count = self.count_students_by_class(class_record.standard_name)
        if student_count:
            raise ClassInUseError(class_record.standard_name, student_count)
        return self.classes.delete(class_id)

    def add_class_alias(self, class_id: int, alias_name: str) -> ClassAlias:
        try:
            return self.classes.create_alias(class_id, alias_name)
        except sqlite3.IntegrityError as error:
            if "class_aliases.alias_name" in str(error):
                raise DuplicateClassAliasError(f"班级别名已被占用：{alias_name.strip()}") from error
            raise

    def list_class_aliases(self, class_id: int) -> list[ClassAlias]:
        return self.classes.list_aliases(class_id)

    def delete_class_alias(self, alias_id: int) -> bool:
        return self.classes.delete_alias(alias_id)

    def resolve_class_name(self, name_or_alias: str) -> str | None:
        return self.classes.resolve_standard_name(name_or_alias)

    def list_classes(self) -> list[ClassRecord]:
        return self.classes.list_all()

    def search_classes(self, keyword: str) -> list[ClassRecord]:
        return self.classes.search(keyword) if keyword.strip() else self.list_classes()

    def count_classes(self) -> int:
        return self.classes.count()

    def create_dormitory(self, dormitory: Dormitory) -> Dormitory:
        try:
            return self.dormitories.create(dormitory)
        except sqlite3.IntegrityError as error:
            if "dormitories.standard_name" in str(error) or "dormitories.building, dormitories.room_number" in str(error):
                raise DuplicateDormitoryError("标准寝室名称或楼栋、寝室号已存在") from error
            raise

    def update_dormitory(self, dormitory_id: int, dormitory: Dormitory) -> bool:
        try:
            return self.dormitories.update(dormitory_id, dormitory)
        except sqlite3.IntegrityError as error:
            if "dormitories.standard_name" in str(error) or "dormitories.building, dormitories.room_number" in str(error):
                raise DuplicateDormitoryError("标准寝室名称或楼栋、寝室号已存在") from error
            raise

    def delete_dormitory(self, dormitory_id: int) -> bool:
        dormitory = self.dormitories.get_by_id(dormitory_id)
        if dormitory is None:
            return False
        student_count = self.count_students_by_dormitory(dormitory.standard_name)
        if student_count:
            raise DormitoryInUseError(dormitory.standard_name, student_count)
        return self.dormitories.delete(dormitory_id)

    def list_dormitories(self) -> list[Dormitory]:
        return self.dormitories.list_all()

    def search_dormitories(self, keyword: str) -> list[Dormitory]:
        return self.dormitories.search(keyword) if keyword.strip() else self.list_dormitories()

    def count_dormitories(self) -> int:
        return self.dormitories.count()

    def _normalize_student_class(self, student: Student) -> Student:
        standard_name = self.resolve_class_name(student.class_name)
        return replace(student, class_name=standard_name) if standard_name else student
