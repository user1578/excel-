"""跨模块业务编排服务。"""

from app.services.master_data_service import (
    ClassInUseError,
    DormitoryInUseError,
    DuplicateClassAliasError,
    DuplicateClassNameError,
    DuplicateDormitoryError,
    DuplicateStudentNumberError,
    MasterDataService,
)
from app.services.import_service import ImportService

__all__ = [
    "ClassInUseError",
    "DormitoryInUseError",
    "DuplicateClassAliasError",
    "DuplicateClassNameError",
    "DuplicateDormitoryError",
    "DuplicateStudentNumberError",
    "MasterDataService",
    "ImportService",
]
