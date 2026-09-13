from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    name: str
    is_dark: bool

    # 背景
    window_bg: str
    sidebar_bg: str
    sidebar_bg_selected: str
    sidebar_bg_hover: str
    chat_bg: str
    card_bg: str
    input_bg: str

    # 文字
    text_primary: str
    text_secondary: str
    text_muted: str
    text_on_accent: str
    text_on_bubble_user: str
    text_on_bubble_assistant: str

    # 边框/分隔
    border: str
    divider: str

    # 强调色
    accent: str
    accent_hover: str

    # 气泡
    bubble_user: str
    bubble_user_border: str
    bubble_assistant: str
    bubble_assistant_border: str

    # 状态
    error: str
    success: str
    warning: str
    info: str

    # 滚动条
    scrollbar_track: str
    scrollbar_thumb: str
    scrollbar_thumb_hover: str


LIGHT = Theme(
    name="light",
    is_dark=False,
    window_bg="#ffffff",
    sidebar_bg="#f5f5f7",
    sidebar_bg_selected="#e8e8ed",
    sidebar_bg_hover="#ededf2",
    chat_bg="#f6f7f9",
    card_bg="#ffffff",
    input_bg="#ffffff",
    text_primary="#1d1d1f",
    text_secondary="#3a3a3c",
    text_muted="#8e8e93",
    text_on_accent="#ffffff",
    text_on_bubble_user="#000000",
    text_on_bubble_assistant="#1d1d1f",
    border="#d1d1d6",
    divider="#e5e5ea",
    accent="#0d9488",
    accent_hover="#0f766e",
    bubble_user="#95ec69",
    bubble_user_border="#7ed957",
    bubble_assistant="#ffffff",
    bubble_assistant_border="#e5e5ea",
    error="#ff3b30",
    success="#34c759",
    warning="#ff9500",
    info="#007aff",
    scrollbar_track="transparent",
    scrollbar_thumb="#c7c7cc",
    scrollbar_thumb_hover="#a1a1aa",
)

DARK = Theme(
    name="dark",
    is_dark=True,
    window_bg="#1c1c1e",
    sidebar_bg="#2c2c2e",
    sidebar_bg_selected="#3a3a3c",
    sidebar_bg_hover="#323234",
    chat_bg="#1c1c1e",
    card_bg="#2c2c2e",
    input_bg="#2c2c2e",
    text_primary="#ffffff",
    text_secondary="#ebebf5",
    text_muted="#8e8e93",
    text_on_accent="#000000",
    text_on_bubble_user="#000000",
    text_on_bubble_assistant="#ffffff",
    border="#38383a",
    divider="#38383a",
    accent="#5eead4",
    accent_hover="#2dd4bf",
    bubble_user="#2c9f67",
    bubble_user_border="#248f5b",
    bubble_assistant="#3a3a3c",
    bubble_assistant_border="#48484a",
    error="#ff453a",
    success="#30d158",
    warning="#ff9f0a",
    info="#0a84ff",
    scrollbar_track="transparent",
    scrollbar_thumb="#48484a",
    scrollbar_thumb_hover="#636366",
)


# ---------------------------------------------------------------------------
# 头像颜色池（与亮/暗模式无关，只由角色名决定）
# ---------------------------------------------------------------------------

AVATAR_COLORS = [
    "#ff9500",  # 橙
    "#ff2d55",  # 粉红
    "#5856d6",  # 紫
    "#007aff",  # 蓝
    "#5ac8fa",  # 天蓝
    "#34c759",  # 绿
    "#af52de",  # 紫红
    "#ff3b30",  # 红
    "#00c7be",  # 青
    "#ffcc00",  # 黄
]


def avatar_color(seed: str) -> str:
    """由任意字符串生成确定性的头像背景色。"""
    idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(AVATAR_COLORS)
    return AVATAR_COLORS[idx]


def avatar_initial(name: str) -> str:
    """取名字的首字符作为头像文字；英文取大写首字母。"""
    name = name.strip()
    if not name:
        return "?"
    first = name[0]
    if "\u4e00" <= first <= "\u9fff":
        return first
    return name[0].upper()


# ---------------------------------------------------------------------------
# 系统深色模式检测
# ---------------------------------------------------------------------------

def system_is_dark() -> bool:
    """检测 macOS 当前是否处于深色模式。"""
    try:
        r = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return r.returncode == 0 and "Dark" in r.stdout
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 主题应用
# ---------------------------------------------------------------------------

def get_theme(theme_mode: str) -> Theme:
    """根据主题模式返回当前应使用的主题。"""
    if theme_mode == "dark":
        return DARK
    if theme_mode == "light":
        return LIGHT
    return DARK if system_is_dark() else LIGHT


def set_app_font(app: QApplication) -> None:
    """设置应用默认字体，优先使用苹方/SF Pro。"""
    preferred = ["PingFang SC", "SF Pro Text", "Helvetica Neue", "Arial"]
    font = QFont()
    for name in preferred:
        font = QFont(name, 13)
        if font.exactMatch():
            break
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)


def apply_theme(app: QApplication, theme: Theme) -> None:
    """把主题应用到 QApplication：调色板 + 全局 QSS。"""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(theme.window_bg))
    palette.setColor(QPalette.WindowText, QColor(theme.text_primary))
    palette.setColor(QPalette.Base, QColor(theme.input_bg))
    palette.setColor(QPalette.AlternateBase, QColor(theme.sidebar_bg))
    palette.setColor(QPalette.Text, QColor(theme.text_primary))
    palette.setColor(QPalette.PlaceholderText, QColor(theme.text_muted))
    palette.setColor(QPalette.Button, QColor(theme.card_bg))
    palette.setColor(QPalette.ButtonText, QColor(theme.text_primary))
    palette.setColor(QPalette.Highlight, QColor(theme.accent))
    palette.setColor(QPalette.HighlightedText, QColor(theme.text_on_accent))
    if theme.is_dark:
        palette.setColor(QPalette.ToolTipBase, QColor(theme.card_bg))
        palette.setColor(QPalette.ToolTipText, QColor(theme.text_primary))
    app.setPalette(palette)

    app.setStyleSheet(_global_stylesheet(theme))


def _global_stylesheet(theme: Theme) -> str:
    t = theme
    return f"""
    /* 基础控件 */
    QWidget {{
        font-size: 13px;
        outline: none;
    }}

    QMainWindow {{
        background: {t.window_bg};
        border: none;
    }}

    QPushButton {{
        background: {t.accent};
        color: {t.text_on_accent};
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background: {t.accent_hover};
    }}
    QPushButton:pressed {{
        background: {t.accent};
    }}
    QPushButton:disabled {{
        background: {t.divider};
        color: {t.text_muted};
    }}
    QPushButton#toolButton {{
        background: transparent;
        color: {t.text_secondary};
        border-radius: 4px;
        padding: 4px 8px;
    }}
    QPushButton#toolButton:hover {{
        background: {t.divider};
    }}

    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
        background: {t.input_bg};
        color: {t.text_primary};
        border: 1px solid {t.border};
        border-radius: 6px;
        padding: 6px 8px;
        selection-background-color: {t.accent};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border: 1px solid {t.accent};
    }}
    QLineEdit::placeholder, QTextEdit::placeholder, QPlainTextEdit::placeholder {{
        color: {t.text_muted};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {t.text_muted};
        width: 0;
        height: 0;
    }}

    QListWidget {{
        background: transparent;
        border: none;
        outline: none;
    }}
    QListWidget::item {{
        border: none;
        border-radius: 8px;
        margin: 2px 6px;
        padding: 8px;
    }}
    QListWidget::item:selected {{
        background: {t.sidebar_bg_selected};
    }}
    QListWidget::item:hover {{
        background: {t.sidebar_bg_hover};
    }}
    QListWidget::item:selected:hover {{
        background: {t.sidebar_bg_selected};
    }}

    QMenu {{
        background: {t.card_bg};
        border: 1px solid {t.border};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 6px 18px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background: {t.accent};
        color: {t.text_on_accent};
    }}
    QMenu::separator {{
        height: 1px;
        background: {t.divider};
        margin: 6px 12px;
    }}

    QScrollBar:vertical {{
        background: {t.scrollbar_track};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.scrollbar_thumb};
        min-height: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.scrollbar_thumb_hover};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {t.scrollbar_track};
        height: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t.scrollbar_thumb};
        min-width: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {t.scrollbar_thumb_hover};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    QSplitter::handle {{
        background: transparent;
    }}
    QSplitter::handle:horizontal {{
        width: 1px;
        margin: 1px;
    }}
    QSplitter::handle:horizontal:hover {{
        background: {t.accent};
    }}

    QDialog {{
        background: {t.window_bg};
    }}
    QDialog QPushButton#secondaryButton {{
        background: {t.card_bg};
        color: {t.text_primary};
        border: 1px solid {t.border};
    }}
    QDialog QPushButton#secondaryButton:hover {{
        background: {t.divider};
    }}
    """
