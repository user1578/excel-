"""应用主窗口与导航。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.master_data_service import MasterDataService
from app.ui.class_page import ClassPage
from app.ui.dormitory_page import DormitoryPage
from app.ui.home_page import HomePage
from app.ui.placeholder_page import PlaceholderPage
from app.ui.student_page import StudentPage
from app.ui.import_page import ImportPage
from app.ui.pending_page import PendingPage
from app.services.import_service import ImportService
from app.services.task_service import TaskService
from app.ui.task_page import TaskPage
from app.ui.history_page import HistoryPage
from app.services.statistics_service import StatisticsService
from app.services.excel_export_service import ExcelExportService
from app.ui.statistics_page import StatisticsPage
from app.services.template_service import TemplateService
from app.ai.deepseek_client import DeepSeekClient
from app.ai.deepseek_parser import DeepSeekParser
from app.ui.template_page import TemplatePage
from app.ui.settings_page import SettingsPage


APP_STYLE = """
QMainWindow { background: #f6f7f9; }
QFrame#sidebar { background: #ffffff; border-right: 1px solid #e4e7ec; }
QLabel#appTitle { color: #1f2937; font-size: 18px; font-weight: 700; }
QLabel#appSubtitle, QLabel#subtitle { color: #667085; }
QLabel#pageTitle { color: #1f2937; font-size: 24px; font-weight: 700; }
QLabel#sectionTitle { color: #344054; font-size: 15px; font-weight: 600; }
QLabel#placeholderMessage { color: #667085; font-size: 16px; }
QPushButton { background: #ffffff; border: 1px solid #d0d5dd; border-radius: 5px; padding: 6px 12px; color: #344054; }
QPushButton:hover { background: #f9fafb; }
QPushButton#navButton { border: 0; border-radius: 4px; text-align: left; padding: 9px 12px; }
QPushButton#navButton:checked { background: #eaf2ff; color: #175cd3; font-weight: 600; }
QPushButton#quickButton { background: #ffffff; border-color: #b9d3ff; color: #175cd3; padding: 9px 16px; }
QFrame#statCard, QFrame#noticeCard { background: #ffffff; border: 1px solid #e4e7ec; border-radius: 6px; }
QLabel#statLabel { color: #667085; }
QLabel#statValue { color: #1f2937; font-size: 27px; font-weight: 700; }
QTableWidget { background: #ffffff; border: 1px solid #e4e7ec; gridline-color: #eef0f3; selection-background-color: #eaf2ff; }
QHeaderView::section { background: #f9fafb; border: 0; border-bottom: 1px solid #e4e7ec; padding: 8px; color: #475467; font-weight: 600; }
QLineEdit, QComboBox, QTextEdit, QSpinBox { background: #ffffff; border: 1px solid #d0d5dd; border-radius: 4px; padding: 5px; }
"""


class MainWindow(QMainWindow):
    def __init__(self, service: MasterDataService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._nav_buttons: dict[str, QPushButton] = {}
        self._page_indexes: dict[str, int] = {}
        self.setWindowTitle("Excel资料整理助手")
        self.resize(1280, 780)
        self.setMinimumSize(1000, 650)
        self.setStyleSheet(APP_STYLE)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_sidebar())

        self.content_stack = QStackedWidget()
        root_layout.addWidget(self.content_stack, 1)
        self.setCentralWidget(root)
        self._build_pages()
        self.navigate("home")

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 22, 14, 18)
        layout.setSpacing(5)
        title = QLabel("Excel资料整理助手")
        title.setObjectName("appTitle")
        title.setWordWrap(True)
        subtitle = QLabel("本地资料维护工具")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(18)
        for key, label in (
            ("home", "首页"),
            ("tasks", "整理任务"),
            ("imports", "资料导入"),
            ("pending", "待确认"),
            ("students", "学生库"),
            ("classes", "班级库"),
            ("dormitories", "寝室库"),
            ("statistics", "汇总统计"),
            ("templates", "模板生成"),
            ("history", "历史记录"),
            ("settings", "设置"),
        ):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, page_key=key: self.navigate(page_key))
            self._nav_buttons[key] = button
            layout.addWidget(button)
        layout.addStretch()
        return sidebar

    def _build_pages(self) -> None:
        self.home_page = HomePage(self.service, self.navigate)
        self.student_page = StudentPage(self.service)
        self.class_page = ClassPage(self.service)
        self.dormitory_page = DormitoryPage(self.service)
        self.task_service = TaskService(self.service.students.database)
        self.import_service = ImportService(self.service.students.database, self.service)
        self.task_page = TaskPage(self.task_service)
        self.import_page = ImportPage(self.import_service, self.task_service)
        self.pending_page = PendingPage(self.import_service, self.service)
        self.history_page = HistoryPage(self.import_service)
        self.statistics_service = StatisticsService(self.service.students.database)
        self.statistics_page = StatisticsPage(self.statistics_service, ExcelExportService(self.statistics_service), self.service, self.task_service)
        self.template_service = TemplateService(self.service)
        self.template_page = TemplatePage(self.template_service, DeepSeekParser(DeepSeekClient()))
        self.settings_page = SettingsPage()
        self._add_page("home", self.home_page)
        self._add_page("tasks", self.task_page)
        self._add_page("students", self.student_page)
        self._add_page("classes", self.class_page)
        self._add_page("dormitories", self.dormitory_page)
        self._add_page("imports", self.import_page)
        self._add_page("pending", self.pending_page)
        self._add_page("history", self.history_page)
        self._add_page("statistics", self.statistics_page)
        self._add_page("templates", self.template_page)
        self._add_page("settings", self.settings_page)
        for key, title in (
        ):
            self._add_page(key, PlaceholderPage(title))
        for page in (self.student_page, self.class_page, self.dormitory_page):
            page.data_changed.connect(self.home_page.refresh)
        self.import_page.session_changed.connect(self.pending_page.set_session)
        self.import_page.imported.connect(self.pending_page.refresh)
        self.import_page.imported.connect(self.history_page.refresh)
        self.task_page.data_changed.connect(self.import_page.refresh_tasks)

    def _add_page(self, key: str, page: QWidget) -> None:
        self._page_indexes[key] = self.content_stack.addWidget(page)

    def navigate(self, key: str) -> None:
        self.content_stack.setCurrentIndex(self._page_indexes[key])
        for page_key, button in self._nav_buttons.items():
            button.setChecked(page_key == key)
        current_page = self.content_stack.currentWidget()
        refresh = getattr(current_page, "refresh", None)
        if callable(refresh):
            refresh()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Repository 每次操作均关闭连接，主窗口可安全正常退出。"""
        event.accept()
