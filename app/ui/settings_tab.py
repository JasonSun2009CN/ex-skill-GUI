from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QMessageBox

from app.core.config import load_config, save_config, AppConfig
from app.core.llm.registry import list_providers, get_provider
from app.core.llm.types import ChatMessage, ChatParams


_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
    "gemini": "gemini-1.5-flash-latest",
}


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("连接设置")
        title.setStyleSheet("font-size:18px; font-weight:600;")
        layout.addWidget(title)

        form = QVBoxLayout()
        form.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("服务商:"), 0)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(list_providers())
        self.provider_combo.currentIndexChanged.connect(self._on_provider_change)
        row1.addWidget(self.provider_combo, 1)
        form.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("API Key:"), 0)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("sk-...")
        row2.addWidget(self.key_edit, 1)
        form.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Base URL:"), 0)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("留空使用官方地址，例如 https://api.openai.com/v1")
        row3.addWidget(self.base_url_edit, 1)
        form.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("模型:"), 0)
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("例如 gpt-4o-mini")
        row4.addWidget(self.model_edit, 1)
        form.addLayout(row4)

        layout.addLayout(form)

        layout.addSpacing(12)
        btn_row = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._on_test)
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self._on_save)
        btn_row.addStretch(1)
        btn_row.addWidget(self.test_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#6b7280;")
        layout.addWidget(self.status)

        layout.addStretch(1)

    def _on_provider_change(self, _idx: int):
        provider = self.provider_combo.currentText()
        default = _DEFAULT_MODELS.get(provider, "")
        if default and not self.model_edit.text().strip():
            self.model_edit.setText(default)

    def _collect(self) -> AppConfig:
        return AppConfig(
            provider=self.provider_combo.currentText(),
            api_key=self.key_edit.text().strip(),
            base_url=self.base_url_edit.text().strip(),
            model=self.model_edit.text().strip() or _DEFAULT_MODELS.get(self.provider_combo.currentText(), ""),
        )

    def _load(self):
        cfg = load_config()
        idx = self.provider_combo.findText(cfg.provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.key_edit.setText(cfg.api_key)
        self.base_url_edit.setText(cfg.base_url)
        self.model_edit.setText(cfg.model or _DEFAULT_MODELS.get(cfg.provider, ""))

    def _on_save(self):
        cfg = self._collect()
        save_config(cfg)
        self.status.setText(f"已保存到 ~/.ex-skill/config.json ({cfg.provider})")

    def _on_test(self):
        cfg = self._collect()
        if not cfg.api_key:
            QMessageBox.warning(self, "提示", "请先填写 API Key")
            return
        self.status.setText("测试中...")
        self.test_btn.setEnabled(False)
        try:
            provider = get_provider(cfg.provider)
            base_url = cfg.base_url or None
            model = cfg.model or _DEFAULT_MODELS.get(cfg.provider) or None
            reply = provider.chat(ChatParams(
                api_key=cfg.api_key,
                base_url=base_url,
                model=model,
                messages=[
                    ChatMessage("system", "You are a ping bot."),
                    ChatMessage("user", "Reply with only the word PONG in uppercase."),
                ],
                temperature=0.0,
                max_tokens=8,
            ))
            if "PONG" in reply.upper():
                self.status.setText(f"✅ 连接成功 ({cfg.provider}/{model or 'default'}) 回复: {reply.strip()[:30]}")
            else:
                self.status.setText(f"⚠️ 已返回但非预期: {reply.strip()[:60]}")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))
            self.status.setText(f"❌ 失败: {e}")
        finally:
            self.test_btn.setEnabled(True)
