from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    """数据根目录：默认 ~/.ex-skill，可用环境变量 EX_SKILL_DATA_DIR 覆盖（测试/便携模式）。

    所有聊天证据、画像与聊天历史都保存在仓库之外，避免误提交。
    """
    env = os.environ.get("EX_SKILL_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".ex-skill"


def ensure_layout() -> None:
    """创建数据目录结构。只在启动与写入路径时调用，不在 import 时产生副作用。"""
    for d in (data_root(), data_root() / "roles"):
        d.mkdir(parents=True, exist_ok=True)


def config_path() -> Path:
    return data_root() / "config.json"


def roles_json_path() -> Path:
    return data_root() / "roles.json"


def role_dir(role_id: str) -> Path:
    return data_root() / "roles" / role_id
