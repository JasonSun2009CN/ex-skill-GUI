from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QComboBox, QLineEdit, QMessageBox,
)
from PySide6.QtCore import QThread, Signal, QObject, QSize
from PySide6.QtGui import QFont

from app.core.config import load_config
from app.core.llm.registry import get_provider
from app.core.imitation_chat import ImitationChatSession
from app.core.paths import SKILLS_DIR
from app.ui.widgets.chat_bubble import ChatBubble


class _ChatWorker(QObject):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, session: ImitationChatSession, user_text: str, cfg):
        super().__init__()
        self.session = session
        self.user_text = user_text
        self.cfg = cfg

    def run(self):
        try:
            reply = self.session.send(
                self.user_text,
                api_key=self.cfg.api_key,
                model=self.cfg.model or None,
                base_url=self.cfg.base_url or None,
            )
            self.done.emit(reply)
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class ChatTab(QWidget):
    def __init__(self):
        super().__init__()
        self._session: Optional[ImitationChatSession] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[_ChatWorker] = None
        self._build_ui()
        self._refresh_skills()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(12)

        title = QLabel("开始对话")
        title.setStyleSheet("font-size:18px; font-weight:600;")
        outer.addWidget(title)

        intro = QLabel("准备完成后会自动加载对应的关系风格，也可以手动选择已有 skill。")
        intro.setStyleSheet("color:#66817b;")
        outer.addWidget(intro)

        top = QHBoxLayout()
        top.addWidget(QLabel("对话风格:"))
        self.skill_combo = QComboBox()
        top.addWidget(self.skill_combo, 1)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._refresh_skills)
        top.addWidget(self.refresh_btn)
        self.load_btn = QPushButton("重新加载")
        self.load_btn.clicked.connect(self._on_load)
        top.addWidget(self.load_btn)
        outer.addLayout(top)

        self.chat_view = QListWidget()
        self.chat_view.setSelectionMode(QListWidget.NoSelection)
        self.chat_view.setSpacing(2)
        self.chat_view.setStyleSheet("""
            QListWidget { background: #f7fbfa; border-radius: 10px; padding: 8px; border: 1px solid #d9e7e3; }
            QListWidget::item { background: transparent; border: none; padding: 0; }
        """)
        outer.addWidget(self.chat_view, 1)

        bottom = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入消息... (Enter 发送)")
        self.input_edit.returnPressed.connect(self._on_send)
        f = QFont("PingFang SC", 12)
        self.input_edit.setFont(f)
        bottom.addWidget(self.input_edit, 1)
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("primaryButton")
        self.send_btn.clicked.connect(self._on_send)
        bottom.addWidget(self.send_btn)
        outer.addLayout(bottom)

        self.status = QLabel("未加载 skill")
        self.status.setStyleSheet("color:#6b7280;")
        outer.addWidget(self.status)

    # ------------------ skills list ------------------
    def _refresh_skills(self):
        current = self.skill_combo.currentData()
        self.skill_combo.clear()
        if SKILLS_DIR.exists():
            for d in sorted(SKILLS_DIR.iterdir()):
                if d.is_dir() and d.name.startswith("imitation-") and (d / "SKILL.md").exists():
                    self.skill_combo.addItem(d.name, str(d))
        if current:
            idx = self.skill_combo.findData(current)
            if idx >= 0:
                self.skill_combo.setCurrentIndex(idx)

    def notify_skill_generated(self, skill_dir: str):
        self._refresh_skills()
        idx = self.skill_combo.findData(skill_dir)
        if idx >= 0:
            self.skill_combo.setCurrentIndex(idx)
            self._on_load()

    def _current_skill_dir(self) -> Optional[str]:
        idx = self.skill_combo.currentIndex()
        if idx < 0:
            return None
        return self.skill_combo.itemData(idx)

    # ------------------ session ------------------
    def _on_load(self):
        sd = self._current_skill_dir()
        if not sd:
            QMessageBox.warning(self, "提示", "请先选择/生成一个 imitation skill")
            return
        try:
            cfg = load_config()
            if not cfg.api_key:
                raise RuntimeError("请先到「设置」Tab 填写 API Key")
            llm = get_provider(cfg.provider)
            self._session = ImitationChatSession(llm, sd)
            self.chat_view.clear()
            alias = re.sub(r"^imitation-", "", Path(sd).name)
            self.status.setText(f"✅ 已加载 skill for: {alias}，已清空历史")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    # ------------------ send ------------------
    def _add_bubble(self, text: str, is_user: bool):
        item = QListWidgetItem(self.chat_view)
        bubble = ChatBubble(text, is_user)
        item.setSizeHint(QSize(bubble.sizeHint().width(), bubble.sizeHint().height() + 8))
        self.chat_view.addItem(item)
        self.chat_view.setItemWidget(item, bubble)
        self.chat_view.scrollToBottom()

    def _on_send(self):
        if self._session is None:
            QMessageBox.warning(self, "提示", "请先点「加载/重置会话」")
            return
        text = self.input_edit.text().strip()
        if not text:
            return
        cfg = load_config()
        if not cfg.api_key:
            QMessageBox.warning(self, "提示", "请先到「设置」Tab 填写 API Key")
            return

        self._add_bubble(text, True)
        self.input_edit.clear()
        self.send_btn.setEnabled(False)
        self.input_edit.setEnabled(False)
        self.status.setText("生成中...")

        self._thread = QThread(self)
        self._worker = _ChatWorker(self._session, text, cfg)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_reply)
        self._worker.failed.connect(self._on_chat_fail)
        self._worker.done.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _cleanup_thread(self):
        if self._thread:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self.send_btn.setEnabled(True)
        self.input_edit.setEnabled(True)
        self.input_edit.setFocus()

    def _on_reply(self, reply: str):
        self._add_bubble(reply.strip(), False)
        self.status.setText(f"已回复 ({len(reply)} chars)")

    def _on_chat_fail(self, err: str):
        QMessageBox.critical(self, "调用失败", err)
        self.status.setText(f"❌ {err}")
