from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from . import paths
from .models import RoleMeta


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# roles.json 索引
# ---------------------------------------------------------------------------


def list_roles() -> list[RoleMeta]:
    data = _read_json(paths.roles_json_path())
    roles = []
    if isinstance(data, dict):
        for item in data.get("roles", []):
            try:
                roles.append(RoleMeta.from_dict(item))
            except Exception:
                continue
    roles.sort(key=lambda r: r.updated_at, reverse=True)
    return roles


def get_role(role_id: str) -> RoleMeta | None:
    for r in list_roles():
        if r.role_id == role_id:
            return r
    return None


def _save_all(roles: list[RoleMeta]) -> None:
    _write_json(
        paths.roles_json_path(),
        {"version": 1, "roles": [r.to_dict() for r in roles]},
    )


def upsert_role(meta: RoleMeta) -> None:
    roles = [r for r in list_roles() if r.role_id != meta.role_id]
    roles.append(meta)
    _save_all(roles)


def delete_role(role_id: str) -> None:
    roles = [r for r in list_roles() if r.role_id != role_id]
    _save_all(roles)
    d = paths.role_dir(role_id)
    if d.exists():
        import shutil

        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# 角色目录内容
# ---------------------------------------------------------------------------


def create_role(meta: RoleMeta, evidence_raw: str, persona: dict | None = None) -> None:
    """新建角色目录并落盘全部文件。"""
    d = paths.role_dir(meta.role_id)
    d.mkdir(parents=True, exist_ok=True)
    if evidence_raw:
        (d / "evidence.txt").write_text(evidence_raw, encoding="utf-8")
    if persona:
        _write_json(d / "persona.json", persona)
    (d / "history.jsonl").touch(exist_ok=True)
    if not meta.created_at:
        meta.created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    meta.updated_at = meta.created_at
    upsert_role(meta)


def save_persona(role_id: str, persona: dict) -> None:
    _write_json(paths.role_dir(role_id) / "persona.json", persona)
    meta = get_role(role_id)
    if meta:
        meta.persona_status = "ready"
        meta.confidence = persona.get("confidence")
        meta.updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        upsert_role(meta)


def load_persona(role_id: str) -> dict | None:
    data = _read_json(paths.role_dir(role_id) / "persona.json")
    return data if isinstance(data, dict) else None


def evidence_path(role_id: str) -> Path:
    return paths.role_dir(role_id) / "evidence.txt"


# ---------------------------------------------------------------------------
# 聊天历史（JSONL）
# ---------------------------------------------------------------------------


def append_history(role_id: str, role: str, content: str) -> None:
    p = paths.role_dir(role_id) / "history.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "role": role,
        "content": content,
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    meta = get_role(role_id)
    if meta:
        meta.updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
        upsert_role(meta)


def read_history(role_id: str, limit: int | None = None) -> list[dict]:
    p = paths.role_dir(role_id) / "history.jsonl"
    records: list[dict] = []
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    if limit is not None and limit > 0:
        return records[-limit:]
    return records
