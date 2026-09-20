"""应用真实入口的隔离启动冒烟测试。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import main as application_main
from app.repositories.database import initialize_database
from app.ui.main_window import MainWindow


def test_main_entry_builds_window_and_exits_with_temporary_runtime(monkeypatch, tmp_path):
    project_directory = tmp_path / "runtime"
    required_directories = (
        project_directory / "data",
        project_directory / "data" / "attachments",
        project_directory / "imports",
        project_directory / "exports",
        project_directory / "templates",
        project_directory / "backups",
    )
    created_windows = []

    class RecordingMainWindow(MainWindow):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created_windows.append(self)

    monkeypatch.setattr(application_main, "PROJECT_DIRECTORY", project_directory)
    monkeypatch.setattr(application_main, "REQUIRED_DIRECTORIES", required_directories)
    monkeypatch.setattr(
        application_main,
        "initialize_database",
        lambda: initialize_database(project_directory / "data" / "database.db"),
    )
    monkeypatch.setattr(application_main, "MainWindow", RecordingMainWindow)
    application = QApplication.instance() or QApplication([])

    def quit_application():
        for window in created_windows:
            window.close()
        application.quit()

    QTimer.singleShot(250, quit_application)

    assert application_main.main() == 0
    assert all(directory.is_dir() for directory in required_directories)
    assert (project_directory / "data" / "database.db").is_file()
    assert len(created_windows) == 1
    assert created_windows[0].merge_page is not None
    assert created_windows[0].workbook_fill_page is not None
    assert created_windows[0].template_page is not None
