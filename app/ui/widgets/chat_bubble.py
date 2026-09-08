from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QPalette, QPainter, QBrush, QPen


class ChatBubble(QFrame):
    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.is_user = is_user
        self.text = text

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(0)

        bubble_wrap = QWidget()
        bubble_layout = QHBoxLayout(bubble_wrap)
        bubble_layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setFont(QFont("PingFang SC", 11))
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {"#0d9488" if is_user else "#e5f2ef"};
                color: {"#ffffff" if is_user else "#19332f"};
                padding: 10px 14px;
                border-radius: 12px;
                max-width: 560px;
            }}
        """)

        if is_user:
            bubble_layout.addStretch(1)
            bubble_layout.addWidget(label, 0, Qt.AlignRight)
            outer.addStretch(1)
            outer.addWidget(bubble_wrap)
        else:
            bubble_layout.addWidget(label, 0, Qt.AlignLeft)
            bubble_layout.addStretch(1)
            outer.addWidget(bubble_wrap)
            outer.addStretch(1)

        self.setMaximumWidth(680)
        self.adjustSize()
