"""Start the ex-skill desktop GUI from the project root.

启动前先确认自己跑在项目自带的 `.venv` 里，必要时用 `.venv/bin/python` 重新执行。
这样能避开几个会掩盖真实原因的常见坑：

- 终端里残留着**旧路径**的 venv 激活（项目迁移后 `python` 直接 command not found，
  或者提示符还挂着 `(.venv)` 但 PATH 已经失效）；
- 用了系统 python / IDE 选错解释器 —— PySide6 根本没装，却报成
  「找不到 Qt 平台插件」，让人误以为是 UF_HIDDEN 的问题。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

# 匹配任意 `<某处>/.venv/bin`，用来从 PATH 里剔除失效的旧 venv。
_STALE_VENV_BIN = re.compile(r"[/\\]\.venv[/\\]bin[/\\]?$")

# 重新执行后置位，避免 exec 失败时在解释器之间来回自举。
_GUARD = "EX_SKILL_BOOTSTRAPPED"


def _running_in_project_venv() -> bool:
    """用 sys.prefix 判断，而不是 sys.executable。

    venv 里的 `bin/python` 是指向框架 Python 的符号链接，resolve() 之后会跑到
    venv 外面去，用它判断会恒为 False。
    """
    try:
        return Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()
    except OSError:
        return False


def _clean_path(path: str, keep: str) -> str:
    """把 `keep`（本项目 venv 的 bin）提到 PATH 最前，并丢掉其它 venv 的 bin 条目。

    项目迁移后，旧位置 `<旧目录>/.venv/bin` 常常还留在 PATH 里。它是失效的，
    但会让 `python` / `pip` 解析到不存在或版本不对的解释器。
    """
    rest = [
        p
        for p in path.split(os.pathsep)
        if p and p != keep and not _STALE_VENV_BIN.search(p)
    ]
    return os.pathsep.join([keep, *rest])


def _bootstrap_into_venv() -> None:
    if _running_in_project_venv() or os.environ.get(_GUARD):
        return
    if not VENV_PYTHON.exists():
        sys.exit(
            f"找不到项目虚拟环境：{VENV_PYTHON}\n"
            "请先创建并安装依赖：\n"
            f"    cd {ROOT}\n"
            "    python3.11 -m venv .venv\n"
            "    .venv/bin/pip install -r requirements.txt\n"
        )
    # 必须显式 flush：execve 会替换整个进程，不会替我们清空 Python 的缓冲区，
    # 而 stdout 重定向到文件/管道时是块缓冲，不 flush 这条提示就丢了。
    print(f"[ex-skill] 解释器 {sys.executable} 不是项目 .venv，改用 {VENV_PYTHON}", flush=True)
    env = dict(os.environ)
    env[_GUARD] = "1"
    # 环境里可能残留着旧位置（项目迁移前）的 VIRTUAL_ENV / PATH —— 正是它们让提示符
    # 显示着错误的 (.venv)、并让 python 指向已经不存在的目录。按实际使用的解释器覆写。
    env["VIRTUAL_ENV"] = str(ROOT / ".venv")
    env["PATH"] = _clean_path(env.get("PATH", ""), str(VENV_PYTHON.parent))
    os.execve(
        str(VENV_PYTHON),
        [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
        env,
    )


def main() -> int:
    _bootstrap_into_venv()

    # 必须在自举之后导入：app 包会链式 import PySide6。
    from app.main import main as app_main

    return app_main()


if __name__ == "__main__":
    sys.exit(main())
