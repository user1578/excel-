"""后续阶段功能的统一占位页面。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)

        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        message = QLabel("该功能将在后续阶段实现")
        message.setObjectName("placeholderMessage")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(heading)
        layout.addStretch()
        layout.addWidget(message)
        layout.addStretch()
