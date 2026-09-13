from __future__ import annotations

import os
import sys

from app.ui.qtgate import (
    clear_hidden_plugin_flags,
    print_remediation,
    qt_probe_ok,
    sanitize_qt_env,
)


def main() -> int:
    # macOS 上 PySide6 插件可能被标记 UF_HIDDEN，导致 Qt 的 QDir 扫描不到插件。
    # 这是一个已知的环境问题，每次启动先自动清理，避免触发下面的预检失败。
    clear_hidden_plugin_flags()

    # 在子进程里先确认 Qt 平台插件可用；失败时 Qt 的 abort 无法在 Python 里捕获，
    # 因此用预检 + 友好中文提示代替 cryptic 报错。
    if not os.environ.get("EX_SKILL_PROBE") and not qt_probe_ok():
        print_remediation()
        return 1

    sanitize_qt_env()

    from PySide6.QtWidgets import QApplication

    from app.core import config as config_mod
    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_theme, get_theme, set_app_font

    app = QApplication(sys.argv)
    app.setApplicationName("ex-skill 角色聊天")
    set_app_font(app)

    cfg = config_mod.load_config()
    theme = get_theme(cfg.theme_mode)
    apply_theme(app, theme)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
