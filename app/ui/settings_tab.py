from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QMessageBox

from app.core.config import load_config, save_config, AppConfig
from app.core.llm.registry import list_providers, get_provider
from app.core.llm.types import ChatMessage, ChatParams


PROVIDER_OPTIONS = {
    "orcarouter": ("OrcaRouter", "", ""),
    "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    "openai": ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
    "anthropic": ("Anthropic", "https://api.anthropic.com", "claude-3-5-haiku-latest"),
    "gemini": ("Google Gemini", "https://generativelanguage.googleapis.com", "gemini-2.5-flash"),
    "deepseek": ("DeepSeek", "https://api.deepseek.com", "deepseek-chat"),
    "qwen": ("阿里云百炼 / Qwen", "", "qwen-plus"),
    "moonshot": ("Moonshot / Kimi", "https://api.moonshot.cn/v1", "kimi-k2"),
    "zhipu": ("智谱 GLM", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
    "groq": ("Groq", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "mistral": ("Mistral AI", "https://api.mistral.ai/v1", "mistral-small-latest"),
    "together": ("Together AI", "https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    "siliconflow": ("硅基流动", "https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V3"),
    "custom-openai": ("其他 OpenAI 兼容服务", "", ""),
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
        for provider_id in PROVIDER_OPTIONS:
            label = PROVIDER_OPTIONS.get(provider_id, (provider_id, "", ""))[0]
            self.provider_combo.addItem(label, provider_id)
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
        provider_id = self.provider_combo.currentData()
        _, base_url, model = PROVIDER_OPTIONS.get(provider_id, (provider_id, "", ""))
        if not self.base_url_edit.text().strip() or self.base_url_edit.property("autoBaseUrl"):
            self.base_url_edit.setText(base_url)
            self.base_url_edit.setProperty("autoBaseUrl", bool(base_url))
        if not self.model_edit.text().strip() or self.model_edit.property("autoModel"):
            self.model_edit.setText(model)
            self.model_edit.setProperty("autoModel", bool(model))

    def _collect(self) -> AppConfig:
        return AppConfig(
            provider=self.provider_combo.currentData() or "openai",
            api_key=self.key_edit.text().strip(),
            base_url=self.base_url_edit.text().strip(),
            model=self.model_edit.text().strip(),
        )

    def _load(self):
        cfg = load_config()
        idx = self.provider_combo.findData(cfg.provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.key_edit.setText(cfg.api_key)
        self.base_url_edit.setText(cfg.base_url)
        default_base = PROVIDER_OPTIONS.get(cfg.provider, (cfg.provider, "", ""))[1]
        default_model = PROVIDER_OPTIONS.get(cfg.provider, (cfg.provider, "", ""))[2]
        self.base_url_edit.setText(cfg.base_url or default_base)
        self.model_edit.setText(cfg.model or default_model)
        self.base_url_edit.setProperty("autoBaseUrl", not bool(cfg.base_url))
        self.model_edit.setProperty("autoModel", not bool(cfg.model))

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
            model = cfg.model or PROVIDER_OPTIONS.get(cfg.provider, ("", "", ""))[2] or None
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
