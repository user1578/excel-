"""本地 AI 配置页；仅在用户点击保存时写入 .env。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.ai.deepseek_client import DeepSeekClient, DeepSeekClientError, DeepSeekConfig


class SettingsPage(QWidget):
    def __init__(self, env_path: str | Path | None = None, parent=None, client: DeepSeekClient | None = None):
        super().__init__(parent)
        self.env_path = Path(env_path or Path(__file__).resolve().parents[2] / ".env")
        self.client = client or DeepSeekClient(self.env_path)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.addWidget(QLabel("设置", objectName="pageTitle"))
        layout.addWidget(QLabel("AI 配置保存在本机 .env；请勿提交真实 API Key。"))
        form = QFormLayout()
        self.enabled = QCheckBox("启用 DeepSeek")
        self.api_key = QLineEdit(); self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.model = QLineEdit()
        self.base_url = QLineEdit()
        form.addRow("", self.enabled); form.addRow("API Key", self.api_key); form.addRow("模型名称", self.model); form.addRow("API 地址", self.base_url)
        layout.addLayout(form)
        save = QPushButton("保存本地配置")
        save.clicked.connect(self.save)
        test = QPushButton("测试连接")
        test.clicked.connect(self.test_connection)
        layout.addWidget(save); layout.addWidget(test); layout.addStretch()
        self.refresh()

    def refresh(self):
        config = DeepSeekConfig.load(self.env_path)
        self.enabled.setChecked(config.enabled); self.api_key.setText(config.api_key); self.model.setText(config.model); self.base_url.setText(config.base_url)

    def save(self):
        DeepSeekConfig(self.enabled.isChecked(), self.api_key.text().strip(), self.model.text().strip() or "deepseek-chat", self.base_url.text().strip()).save(self.env_path)
        QMessageBox.information(self, "保存完成", "AI 配置已保存到本机 .env。")

    def test_connection(self):
        try:
            self.client.test_connection()
        except DeepSeekClientError as error:
            QMessageBox.warning(self, "连接失败", str(error))
            return
        QMessageBox.information(self, "连接成功", "DeepSeek连接成功")
