from __future__ import annotations

import os
import subprocess
import sys

# 可能与 Qt 平台插件冲突/污染的变量
_POLLUTED_VARS = (
    "QT_QPA_PLATFORM",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QT_PLUGIN_PATH",
    "DYLD_FRAMEWORK_PATH",
    "DYLD_LIBRARY_PATH",
)

# 探针：仅构造一次 QApplication 就退出（不弹窗）。Qt 平台插件加载失败时进程会 abort → 返回码非 0。
_PROBE_CODE = r"""
import os, sys
for k in (%s):
    os.environ.pop(k, None)
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
app = QApplication(sys.argv)
QTimer.singleShot(0, app.quit)
app.exec()
print("QT_OK")
""" % " ".join(repr(v) for v in _POLLUTED_VARS)


def sanitize_qt_env() -> None:
    """清除可能让 Qt 找不到平台插件的污染变量（在构造 QApplication 前调用）。"""
    for k in _POLLUTED_VARS:
        os.environ.pop(k, None)


def qt_probe_ok(timeout: float = 20.0) -> bool:
    """用子进程验证 Qt 是否能初始化平台插件。"""
    env = dict(os.environ)
    for k in _POLLUTED_VARS:
        env.pop(k, None)
    env["EX_SKILL_PROBE"] = "1"
    try:
        r = subprocess.run(
            [sys.executable, "-c", _PROBE_CODE],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode == 0 and "QT_OK" in r.stdout
    except Exception:
        return False


REMEDIATION = """\
ex-skill 无法启动图形界面。

检测到 Qt 平台插件加载失败，通常报错类似：
    qt.qpa.plugin: Could not find the Qt platform plugin "cocoa" in ""
    This application failed to start ...

按顺序尝试以下解决办法：
1. 用「系统终端」（Terminal.app，不是 IDE 内置终端）运行：
       cd 项目目录
       source .venv/bin/activate
       python launch.py
2. 在项目 venv 里干净重装 PySide6：
       .venv/bin/pip uninstall -y PySide6 PySide6-Essentials PySide6-Addons shiboken6
       .venv/bin/pip install "PySide6==6.11.2"
3. 若报错只在 IDE 里出现、系统终端里正常，说明是 IDE 的 macOS 沙箱导致，
   请直接用系统终端运行，或在 IDE 设置里指定项目自带的 .venv 解释器后改用「集成终端」启动。
"""


def print_remediation() -> None:
    print(REMEDIATION)
