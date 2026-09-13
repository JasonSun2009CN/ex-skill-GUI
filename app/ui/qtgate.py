from __future__ import annotations

import os
import stat
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


def clear_hidden_plugin_flags() -> bool:
    """清除 PySide6 插件目录内文件的 macOS UF_HIDDEN 标志。

    Qt 的 QFactoryLoader 用 QDir 默认过滤扫描 plugins 目录，而 QDir 默认
    排除隐藏文件。若插件 .dylib 被标记为 hidden，Qt 将认定「找不到平台插件」
    并直接 abort（报 qt.qpa.plugin: Could not find the Qt platform plugin）。

    返回是否执行了清理。
    """
    if sys.platform != "darwin":
        return False
    try:
        from PySide6.QtCore import QLibraryInfo

        plugins = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
    except Exception:
        return False
    if not plugins or not os.path.isdir(plugins):
        return False

    hidden = []
    for dirpath, _dirnames, filenames in os.walk(plugins):
        for name in filenames:
            p = os.path.join(dirpath, name)
            try:
                if os.stat(p).st_flags & stat.UF_HIDDEN:
                    hidden.append(p)
            except OSError:
                continue
    if not hidden:
        return False

    try:
        subprocess.run(
            ["chflags", "-R", "nohidden", plugins],
            check=False,
            capture_output=True,
        )
        return True
    except Exception:
        return False


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

最常见的原因是 macOS 把 PySide6 的插件文件标记成了「隐藏」（UF_HIDDEN）：
Qt 用 QDir 默认过滤扫描插件目录，会直接跳过隐藏文件，于是认为找不到平台插件。
即使重装 PySide6，文件可能在解压后又被重新打上该标志，所以重装往往治不好。

按顺序尝试以下解决办法：
1. 清除 PySide6 插件目录的隐藏标志（最可能的修复）：
       chflags -R nohidden .venv/lib/python3.11/site-packages/PySide6
   然后重新启动：
       source .venv/bin/activate
       python launch.py
   （应用启动时也会自动尝试清理一次；若仍失败，手动执行上面这条命令。）
2. 若报错只在 IDE 里出现、系统终端里正常，说明是 IDE 的 macOS 沙箱导致，
   请改用系统终端（Terminal.app）运行，或在 IDE 设置里指定项目自带的 .venv 解释器。
3. 若以上都无效，再考虑在项目 venv 里重装 PySide6：
       .venv/bin/pip uninstall -y PySide6 PySide6-Essentials PySide6-Addons shiboken6
       .venv/bin/pip install "PySide6==6.8.2"
"""


def print_remediation() -> None:
    print(REMEDIATION)
