"""Excel资料整理助手的应用入口，只负责启动与组装。"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.repositories.database import DatabaseManager, initialize_database
from app.services.master_data_service import MasterDataService
from app.ui.main_window import MainWindow


PROJECT_DIRECTORY = Path(__file__).resolve().parent
REQUIRED_DIRECTORIES = (
    PROJECT_DIRECTORY / "data",
    PROJECT_DIRECTORY / "data" / "attachments",
    PROJECT_DIRECTORY / "imports",
    PROJECT_DIRECTORY / "exports",
    PROJECT_DIRECTORY / "templates",
    PROJECT_DIRECTORY / "backups",
)


def initialize_required_directories() -> None:
    """保证本地运行所需目录存在，不处理业务数据。"""
    for directory in REQUIRED_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def initialize_application_database() -> DatabaseManager:
    """保证 data/database.db 与基础表已经就绪。"""
    initialize_required_directories()
    return initialize_database()


def main() -> int:
    """初始化本地环境后创建 QApplication 与主窗口。"""
    try:
        database = initialize_application_database()
    except (OSError, sqlite3.Error) as error:
        application = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "启动失败", f"无法初始化本地数据库。\n\n{error}")
        return 1

    application = QApplication(sys.argv)
    application.setApplicationName("Excel资料整理助手")
    application.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow(MasterDataService(database))
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
