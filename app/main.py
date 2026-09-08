from __future__ import annotations

import os
import sys

from app.ui.qtgate import qt_probe_ok, print_remediation, sanitize_qt_env


def main() -> int:
    # 在子进程里先确认 Qt 平台插件可用；失败时 Qt 的 abort 无法在 Python 里捕获，
    # 因此用预检 + 友好中文提示代替 cryptic 报错。
    if not os.environ.get("EX_SKILL_PROBE") and not qt_probe_ok():
        print_remediation()
        return 1

    sanitize_qt_env()

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("ex-skill 角色聊天")
    try:
        app.setFont(QFont("PingFang SC", 11))
    except Exception:
        pass

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
