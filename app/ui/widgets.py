from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.models import RoleMeta
from .avatar import Avatar
from .theme import Theme


def format_timestamp(ts: str | None) -> str:
    """把 ISO 时间字符串格式化为完整日期时间。"""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)


class ChatBubble(QWidget):
    """单条聊天消息：头像 + 昵称/时间 + 气泡。"""

    def __init__(
        self,
        text: str,
        is_user: bool,
        meta: RoleMeta | None,
        user_name: str = "我",
        timestamp: str | None = None,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.is_user = is_user
        self.theme = theme

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 6, 12, 6)
        root.setSpacing(10)

        # 头像
        if is_user:
            avatar = Avatar(user_name, user_name, size=36)
            avatar.setObjectName("userAvatar")
        else:
            display = meta.display_name if meta else "对方"
            seed = meta.role_id if meta else display
            avatar = Avatar(display, seed, size=36)
            avatar.set_image_path(meta.avatar_path if meta else None)

        # 内容列：昵称/时间 + 气泡
        content = QVBoxLayout()
        content.setSpacing(4)
        content.setAlignment(Qt.AlignRight if is_user else Qt.AlignLeft)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        name_label = QLabel(user_name if is_user else (meta.display_name if meta else "对方"))
        name_label.setStyleSheet(f"color: {theme.text_muted if theme else '#8e8e93'}; font-size: 11px;")
        time_label = QLabel(format_timestamp(timestamp))
        time_label.setStyleSheet(f"color: {theme.text_muted if theme else '#8e8e93'}; font-size: 11px;")
        if is_user:
            meta_row.addStretch(1)
            meta_row.addWidget(time_label)
            meta_row.addWidget(name_label)
        else:
            meta_row.addWidget(name_label)
            meta_row.addWidget(time_label)
            meta_row.addStretch(1)
        content.addLayout(meta_row)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        if theme:
            bg = theme.bubble_user if is_user else theme.bubble_assistant
            fg = theme.text_on_bubble_user if is_user else theme.text_on_bubble_assistant
            border = theme.bubble_user_border if is_user else theme.bubble_assistant_border
            bubble.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {bg};
                    color: {fg};
                    padding: 10px 14px;
                    border-radius: 14px;
                    border: 1px solid {border};
                }}
                """
            )
        bubble.setFont(QFont("PingFang SC", 13))

        bubble_row = QHBoxLayout()
        bubble_row.setSpacing(0)
        if is_user:
            bubble_row.addStretch(1)
            bubble_row.addWidget(bubble, 0, Qt.AlignRight)
        else:
            bubble_row.addWidget(bubble, 0, Qt.AlignLeft)
            bubble_row.addStretch(1)
        content.addLayout(bubble_row)

        if is_user:
            root.addLayout(content, 1)
            root.addWidget(avatar, 0, Qt.AlignTop)
        else:
            root.addWidget(avatar, 0, Qt.AlignTop)
            root.addLayout(content, 1)


class ChatView(QScrollArea):
    """聊天消息滚动区。"""

    def __init__(self, meta: RoleMeta | None = None, theme: Theme | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.meta = meta
        self.theme = theme
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 8, 0, 8)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)
        self.setWidget(self._container)
        if theme:
            self.setStyleSheet(f"QScrollArea {{ background: {theme.chat_bg}; }}")

        self._typing_widget: QWidget | None = None

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.setStyleSheet(f"QScrollArea {{ background: {theme.chat_bg}; }}")

    def set_meta(self, meta: RoleMeta) -> None:
        self.meta = meta

    def _scroll_to_bottom(self) -> None:
        sb = self.verticalScrollBar()
        QTimer.singleShot(0, lambda: sb.setValue(sb.maximum()))

    def add_message(self, role: str, text: str, timestamp: str | None = None) -> None:
        is_user = role == "user"
        bubble = ChatBubble(
            text,
            is_user,
            self.meta,
            timestamp=timestamp,
            theme=self.theme,
        )
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def show_typing(self) -> None:
        if self._typing_widget is not None:
            return
        self._typing_widget = ChatBubble(
            "对方正在输入…",
            is_user=False,
            meta=self.meta,
            timestamp=None,
            theme=self.theme,
        )
        # 弱化样式
        for label in self._typing_widget.findChildren(QLabel):
            if "对方正在输入" in label.text():
                label.setStyleSheet(
                    f"background-color: {self.theme.bubble_assistant if self.theme else '#ffffff'};"
                    f"color: {self.theme.text_muted if self.theme else '#8e8e93'};"
                    "padding: 10px 14px; border-radius: 14px;"
                )
        self._layout.insertWidget(self._layout.count() - 1, self._typing_widget)
        self._scroll_to_bottom()

    def hide_typing(self) -> None:
        if self._typing_widget is not None:
            self._layout.removeWidget(self._typing_widget)
            self._typing_widget.deleteLater()
            self._typing_widget = None

    def clear(self) -> None:
        self.hide_typing()
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()


class ChatInput(QTextEdit):
    """多行聊天输入框：Enter 发送，Shift+Enter 换行，最多显示 5 行。"""

    send_clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setPlaceholderText("说点什么…")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setAcceptRichText(False)
        self._max_lines = 5
        self._base_height = 0
        self.textChanged.connect(self._adjust_height)
        QTimer.singleShot(0, self._adjust_height)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() == Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_clicked.emit()
            return
        super().keyPressEvent(event)

    def _adjust_height(self) -> None:
        doc = self.document()
        fm = QFontMetrics(doc.defaultFont())
        line_height = fm.lineSpacing()
        margins = self.contentsMargins()
        frame_width = self.frameWidth()
        # 内容高度 + 边距
        doc_height = doc.size().height()
        max_height = line_height * self._max_lines + margins.top() + margins.bottom() + frame_width * 2 + 8
        preferred = min(max(int(doc_height) + 16, line_height + 24), max_height)
        if self.maximumHeight() != max_height:
            self.setMaximumHeight(max_height)
        if self.height() != preferred:
            self.setFixedHeight(preferred)

    def text_value(self) -> str:
        return self.toPlainText().strip()

    def clear_input(self) -> None:
        self.clear()
        self._adjust_height()
