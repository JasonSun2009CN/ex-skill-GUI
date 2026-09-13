from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QLabel, QWidget

from .theme import avatar_color, avatar_initial


class Avatar(QLabel):
    """圆形头像组件。优先显示自定义图片，否则显示首字母彩色背景。"""

    def __init__(self, name: str, seed: str, size: int = 40, parent: QWidget | None = None):
        super().__init__(parent)
        self._name = name
        self._seed = seed
        self._size = size
        self._image_path: str | None = None
        self._image_cache: QImage | None = None
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self._render()

    def set_name(self, name: str) -> None:
        if name == self._name:
            return
        self._name = name
        self._render()

    def set_seed(self, seed: str) -> None:
        if seed == self._seed:
            return
        self._seed = seed
        self._render()

    def set_identity(self, name: str, seed: str) -> None:
        """同时更新显示名与取色种子，只重绘一次。

        对话框里逐字输入时这是高频路径，分开调用会触发两次完整的 pixmap 重建。
        """
        if name == self._name and seed == self._seed:
            return
        self._name = name
        self._seed = seed
        self._render()

    def set_image_path(self, path: str | Path | None) -> None:
        new_path = str(path) if path else None
        if new_path == self._image_path:
            return
        self._image_path = new_path
        self._image_cache = None  # 路径变了才需要重新解码
        self._render()

    def _scaled_image(self) -> QImage | None:
        """取按显示尺寸缩放好的头像图，结果缓存，避免重复读盘/解码。"""
        if self._image_cache is not None:
            return self._image_cache
        if not self._image_path or not Path(self._image_path).exists():
            return None
        img = QImage(str(self._image_path))
        if img.isNull():
            return None
        self._image_cache = img.scaled(
            self._size, self._size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        return self._image_cache

    def _render(self) -> None:
        size = self._size
        dpr = self.devicePixelRatio() if hasattr(self, "devicePixelRatio") else 1.0
        pixmap = QPixmap(int(size * dpr), int(size * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addEllipse(QRectF(0, 0, size, size))
        painter.setClipPath(path)

        scaled = self._scaled_image()
        if scaled is not None:
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            painter.drawImage(QRect(0, 0, size, size), scaled, QRect(x, y, size, size))
            painter.end()
            self.setPixmap(pixmap)
            return

        # 纯色背景 + 首字母
        bg = QColor(avatar_color(self._seed))
        painter.fillRect(0, 0, size, size, bg)

        pen = QPen(QColor("white"))
        painter.setPen(pen)
        font = QFont("PingFang SC", max(10, size // 2), QFont.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text = avatar_initial(self._name)
        text_rect = fm.boundingRect(text)
        x = (size - text_rect.width()) // 2
        y = (size + fm.ascent() - fm.descent()) // 2
        painter.drawText(x, y, text)

        painter.end()
        self.setPixmap(pixmap)
