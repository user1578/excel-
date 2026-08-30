"""首页及基础数据概览。"""

from collections.abc import Callable

from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.services.master_data_service import MasterDataService


class HomePage(QWidget):
    def __init__(self, service: MasterDataService, navigate: Callable[[str], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.navigate = navigate
        self._stat_values: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(18)

        title = QLabel("Excel资料整理助手")
        title.setObjectName("pageTitle")
        subtitle = QLabel("先维护好学生、班级和寝室基础资料，再逐步完成 Excel 整理流程。")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        quick_layout = QHBoxLayout()
        for label, page_key in (("学生库", "students"), ("班级库", "classes"), ("寝室库", "dormitories")):
            button = QPushButton(f"进入{label}")
            button.setObjectName("quickButton")
            button.clicked.connect(lambda _checked=False, key=page_key: self.navigate(key))
            quick_layout.addWidget(button)
        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        stats_title = QLabel("基础数据统计")
        stats_title.setObjectName("sectionTitle")
        layout.addWidget(stats_title)
        stats_layout = QGridLayout()
        stats_layout.setHorizontalSpacing(16)
        for index, (key, label) in enumerate((
            ("students", "学生总数"),
            ("classes", "班级总数"),
            ("dormitories", "寝室总数"),
        )):
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            name = QLabel(label)
            name.setObjectName("statLabel")
            value = QLabel("0")
            value.setObjectName("statValue")
            card_layout.addWidget(name)
            card_layout.addWidget(value)
            self._stat_values[key] = value
            stats_layout.addWidget(card, 0, index)
        layout.addLayout(stats_layout)

        recent = QFrame()
        recent.setObjectName("noticeCard")
        recent_layout = QVBoxLayout(recent)
        recent_title = QLabel("最近功能")
        recent_title.setObjectName("sectionTitle")
        recent_text = QLabel("Excel整理、汇总统计、模板生成将在后续阶段加入。")
        recent_text.setWordWrap(True)
        recent_layout.addWidget(recent_title)
        recent_layout.addWidget(recent_text)
        layout.addWidget(recent)
        layout.addStretch()

    def refresh(self) -> None:
        self._stat_values["students"].setText(str(self.service.count_students()))
        self._stat_values["classes"].setText(str(self.service.count_classes()))
        self._stat_values["dormitories"].setText(str(self.service.count_dormitories()))
