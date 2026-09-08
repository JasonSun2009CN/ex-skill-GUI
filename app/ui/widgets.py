from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QFont


class ChatBubble(QFrame):
    """单条消息气泡：user 右侧深青、assistant/对方 左侧浅绿。"""

    def __init__(self, text: str, is_user: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.is_user = is_user
        self.setFrameShape(QFrame.NoFrame)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(0)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setMaximumWidth(560)
        label.setMinimumWidth(40)
        label.setFont(QFont("PingFang SC", 11))
        label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {"#0d9488" if is_user else "#e5f2ef"};
                color: {"#ffffff" if is_user else "#19332f"};
                padding: 10px 14px;
                border-radius: 12px;
                max-width: 560px;
            }}
            """
        )

        if is_user:
            outer.addStretch(1)
            outer.addWidget(label, 0, Qt.AlignRight)
        else:
            outer.addWidget(label, 0, Qt.AlignLeft)
            outer.addStretch(1)
        self.adjustSize()


class ChatView(QScrollArea):
    """聊天消息滚动区。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)
        self.setWidget(self._container)
        self.setStyleSheet("QScrollArea { background: #f6f8f7; }")
        self._typing_bubble: ChatBubble | None = None

    def _scroll_to_bottom(self) -> None:
        sb = self.verticalScrollBar()
        QTimer.singleShot(0, lambda: sb.setValue(sb.maximum()))

    def add_message(self, role: str, text: str) -> None:
        self._layout.insertWidget(self._layout.count() - 1, ChatBubble(text, role == "user"))
        self._scroll_to_bottom()

    def show_typing(self) -> None:
        if self._typing_bubble is None:
            self._typing_bubble = ChatBubble("对方正在输入…", is_user=False)
            self._typing_bubble.setStyleSheet("color:#8aa;")
            self._layout.insertWidget(self._layout.count() - 1, self._typing_bubble)
            self._scroll_to_bottom()

    def hide_typing(self) -> None:
        if self._typing_bubble is not None:
            self._layout.removeWidget(self._typing_bubble)
            self._typing_bubble.deleteLater()
            self._typing_bubble = None

    def clear(self) -> None:
        self.hide_typing()
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
