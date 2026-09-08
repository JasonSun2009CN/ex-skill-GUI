from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import evidence, persona_store
from .llm.client import LLMClient
from .models import RoleMeta, make_role_id
from .persona_analyzer import analyze


class PipelineError(Exception):
    """新建角色流程的预期错误（记录找不到对象等），信息已面向用户。"""


@dataclass
class NewRoleDraft:
    display_name: str
    category: str
    subtype: str | None
    alias: str                    # 记录中「对方」名字
    me_alias: str = ""            # 留空则自动推测
    files: list[str] = field(default_factory=list)


def preview(draft: NewRoleDraft) -> dict:
    """解析预览：说话人统计、自动推测「我」、第三方丢弃情况。不调 LLM。"""
    if not draft.alias.strip():
        raise PipelineError("请填写「对方在记录里的名字」，用于在聊天记录中定位要模仿的人。")
    paths = [Path(f) for f in draft.files]
    if not paths:
        raise PipelineError("请先选择要导入的聊天记录文件。")
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise PipelineError("找不到文件：" + "、".join(missing))

    raw, turns = evidence.read_evidence_files(paths)
    speaker_counts = evidence.detect_speakers(turns)
    subject_count = speaker_counts.get(draft.alias, 0)
    # 记录中的实际写名（可能与 alias 存在大小写/符号差异），用于标注
    subject_writename = draft.alias
    for name in speaker_counts:
        if name != draft.alias and (draft.alias in name or name in draft.alias):
            subject_writename = name
            subject_count += speaker_counts[name]

    me = draft.me_alias.strip() or evidence.suggest_me_alias(speaker_counts, draft.alias)
    labeled, third_parties, dropped = evidence.label_turns(turns, draft.alias, me)

    return {
        "raw_chars": len(raw),
        "turn_count": len(turns),
        "subject_count": subject_count,
        "subject_writename": subject_writename,
        "speaker_counts": speaker_counts,
        "me_alias": me,
        "labeled_count": len(labeled),
        "third_parties": third_parties,
        "dropped_count": dropped,
    }


def build_role(llm: LLMClient, draft: NewRoleDraft, progress_cb: Callable[[str], None] | None = None) -> RoleMeta:
    """完整流程：解析 → 标注 → 生成画像 → 落盘 → 返回 RoleMeta。"""
    def log(s: str) -> None:
        if progress_cb:
            progress_cb(s)

    log("[1/3] 解析并整理聊天记录…")
    pv = preview(draft)
    if pv["subject_count"] <= 0:
        raise PipelineError(
            f"在记录中找不到「{draft.alias}」的发言（当前识别到说话人："
            + "、".join(pv["speaker_counts"]) + "）。请核对「对方在记录里的名字」。"
        )
    me = pv["me_alias"]
    if not me:
        raise PipelineError("无法自动识别「你自己」的发言，请在表单里指定你的昵称。")

    paths = [Path(f) for f in draft.files]
    raw, turns = evidence.read_evidence_files(paths)
    labeled, _third, _dropped = evidence.label_turns(turns, draft.alias, me)
    chat_text, truncated = evidence.format_turns(labeled)

    meta = RoleMeta(
        role_id=make_role_id(draft.display_name or draft.alias),
        display_name=draft.display_name or draft.alias,
        category=draft.category,
        subtype=draft.subtype,
        alias=draft.alias,
        me_alias=me,
        source_files=[p.name for p in paths],
        persona_status="pending",
    )

    persona = analyze(llm, meta, chat_text, truncated=truncated, progress_cb=log)
    log("[2/3] 落盘保存…")
    persona_store.create_role(meta, raw)
    persona_store.save_persona(meta.role_id, persona)
    log("[3/3] 完成。")
    return persona_store.get_role(meta.role_id) or meta
