from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..core import config as config_mod
from ..core.config import PROVIDER_PRESETS, Config
from ..core.llm.client import LLMClient
from .theme import Theme
from .workers import run_in_thread

API_MODE_LABELS = {"openai": "OpenAI 兼容（/chat/completions）", "anthropic": "Anthropic（/v1/messages）"}
API_MODE_VALUES = {"OpenAI 兼容（/chat/completions）": "openai", "Anthropic（/v1/messages）": "anthropic"}

THEME_LABELS = {"system": "跟随系统", "light": "浅色", "dark": "暗色"}
THEME_VALUES = {"跟随系统": "system", "浅色": "light", "暗色": "dark"}


class SettingsDialog(QDialog):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setWindowTitle("设置")
        self.setModal(True)
        self.resize(520, 380)
        self.result_config: Config | None = None
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("模型与界面设置")
        title.setFont(QFont("PingFang SC", 16, QFont.Bold))
        title.setStyleSheet(f"color: {theme.text_primary};")
        root.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(12)

        # 主题
        self.theme_combo = QComboBox()
        for label in THEME_VALUES:
            self.theme_combo.addItem(label)

        # 服务预设
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("（自定义）", "")
        for name in PROVIDER_PRESETS:
            self.preset_combo.addItem(name, name)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)

        # API Key + 显示/隐藏
        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("sk-…")
        self.toggle_key_btn = QPushButton("显示")
        self.toggle_key_btn.setObjectName("toolButton")
        self.toggle_key_btn.setFixedSize(48, 28)
        self.toggle_key_btn.setCheckable(True)
        self.toggle_key_btn.toggled.connect(self._on_toggle_key)
        key_row.addWidget(self.api_key_edit, 1)
        key_row.addWidget(self.toggle_key_btn)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(list(API_MODE_VALUES.keys()))

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("留空使用该服务默认地址")

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("如 deepseek-chat / claude-sonnet-5 / gpt-4o-mini")

        form.addRow("主题", self.theme_combo)
        form.addRow("服务预设", self.preset_combo)
        form.addRow("API Key", key_row)
        form.addRow("接口形态", self.mode_combo)
        form.addRow("Base URL", self.base_url_edit)
        form.addRow("模型", self.model_edit)
        root.addLayout(form)

        hint = QLabel("支持两类接口：OpenAI 兼容（DeepSeek/Qwen/GLM/OpenAI/OpenRouter 等）与 Anthropic。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {theme.text_muted}; font-size: 11px;")
        root.addWidget(hint)

        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._on_test)
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(f"color: {theme.text_muted};")

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self.test_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)

        root.addWidget(self._status_label)
        root.addLayout(btn_row)

        self._load(config_mod.load_config())

    # ------------------------------------------------------------------
    def _load(self, cfg: Config) -> None:
        self.api_key_edit.setText(cfg.api_key)
        self.mode_combo.setCurrentIndex(0 if cfg.api_mode == "openai" else 1)
        self.base_url_edit.setText(cfg.base_url)
        self.model_edit.setText(cfg.model)

        theme_index = list(THEME_VALUES.values()).index(cfg.theme_mode) if cfg.theme_mode in THEME_VALUES.values() else 0
        self.theme_combo.setCurrentIndex(theme_index)

    def _current_config(self) -> Config:
        return Config(
            api_mode=API_MODE_VALUES[self.mode_combo.currentText()],
            api_key=self.api_key_edit.text().strip(),
            base_url=self.base_url_edit.text().strip(),
            model=self.model_edit.text().strip(),
            theme_mode=THEME_VALUES[self.theme_combo.currentText()],
            sidebar_width=config_mod.load_config().sidebar_width,
        )

    def _on_preset_changed(self, _idx: int) -> None:
        name = self.preset_combo.currentData()
        if not name:
            return
        mode, base_url, model = PROVIDER_PRESETS[name]
        self.mode_combo.setCurrentIndex(0 if mode == "openai" else 1)
        self.base_url_edit.setText(base_url)
        self.model_edit.setText(model)

    def _on_toggle_key(self, checked: bool) -> None:
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            self.toggle_key_btn.setText("隐藏")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            self.toggle_key_btn.setText("显示")

    def _on_save(self) -> None:
        cfg = self._current_config()
        if not cfg.api_key:
            QMessageBox.warning(self, "提示", "请填写 API Key。")
            return
        if not cfg.model:
            QMessageBox.warning(self, "提示", "请填写模型名。")
            return
        config_mod.save_config(cfg)
        self.result_config = cfg
        self.accept()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.test_btn.setEnabled(not busy)
        self._status_label.setText("正在测试连接…" if busy else "")

    def _on_test(self) -> None:
        if self._busy:
            return
        cfg = self._current_config()
        if not cfg.api_key or not cfg.model:
            self._status_label.setText("请先填写 API Key 与模型名再测试。")
            return
        self._set_busy(True)

        def task(progress):
            return LLMClient(cfg).probe()

        def on_done(result):
            self._set_busy(False)
            ok, msg = result
            if ok:
                QMessageBox.information(self, "测试连接", f"连接成功：{msg}")
                self._status_label.setText("")
            else:
                QMessageBox.warning(self, "测试连接", f"连接失败：\n{msg}")

        def on_fail(err: str) -> None:
            self._set_busy(False)
            QMessageBox.warning(self, "测试连接", f"连接失败：\n{err}")

        run_in_thread(task, on_done, on_fail, parent=self.window())

    def reject(self) -> None:
        if self._busy:
            return
        super().reject()
