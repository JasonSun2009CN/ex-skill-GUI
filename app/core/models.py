from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# 关系类别 / 子类
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, str] = {
    "lover": "恋人",
    "family": "家人",
    "friend": "朋友",
    "colleague": "同事",
    "other": "其他",
}

# lover 的子类表示对方的性别 / 称呼
LOVER_SUBTYPES: dict[str, str] = {"male": "男", "female": "女"}

# family 的子类表示具体成员
FAMILY_SUBTYPES: dict[str, str] = {
    "father": "父亲",
    "mother": "母亲",
    "elder_brother": "哥哥",
    "younger_brother": "弟弟",
    "elder_sister": "姐姐",
    "younger_sister": "妹妹",
}

CATEGORY_SUBTYPES: dict[str, dict[str, str]] = {
    "lover": LOVER_SUBTYPES,
    "family": FAMILY_SUBTYPES,
}


def subtype_options(category: str) -> list[tuple[str, str]]:
    return list(CATEGORY_SUBTYPES.get(category, {}).items())


def relationship_label(category: str, subtype: str | None = None) -> str:
    """如：「恋人 · 女」「家人 · 哥哥」「朋友」"""
    base = CATEGORIES.get(category, CATEGORIES["other"])
    if subtype and category in CATEGORY_SUBTYPES:
        sub = CATEGORY_SUBTYPES[category].get(subtype)
        if sub:
            return f"{base} · {sub}"
    return base


# 关系边界提示：既用于生成画像时的分析约束，也用于聊天时的模仿约束（见 persona_prompts）
RELATIONSHIP_BOUNDARY: dict[str, str] = {
    "lover": "这是恋人/亲密关系角色。可以表现资料中出现的亲昵、关心与共同记忆；"
             "不要主动编造新的承诺，也不要把关系推进到超出资料的阶段；避免冒犯或越界内容。",
    "family": "这是家人关系。保持家人间自然、亲切、熟悉的语气；注意长幼称谓与家庭边界，不要模拟恋爱或暧昧。",
    "friend": "这是朋友关系。保持朋友间随意、轻松的口吻；不要把互动自动升级为恋爱或暧昧。",
    "colleague": "这是同事关系。语气偏职业、礼貌；只在资料明确支持时才流露私交。",
    "other": "这是自定义关系。严格依据聊天记录；不要擅自假设恋爱、家庭或职业关系。",
}


def get_relationship_boundary(category: str) -> str:
    return RELATIONSHIP_BOUNDARY.get(category, RELATIONSHIP_BOUNDARY["other"])


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def make_role_id(display_name: str) -> str:
    """由显示名生成稳定 slug + 短随机后缀。"""
    slug = re.sub(r"[^a-zA-Z0-9一-鿿]+", "-", display_name.strip().lower())
    slug = slug.strip("-") or "role"
    return f"{slug}-{secrets.token_hex(3)}"


# ---------------------------------------------------------------------------
# 角色索引（roles.json）
# ---------------------------------------------------------------------------


@dataclass
class RoleMeta:
    role_id: str
    display_name: str
    category: str
    subtype: str | None
    alias: str                 # 记录中「对方」的名字
    me_alias: str              # 记录中「我」的名字
    source_files: list[str] = field(default_factory=list)
    persona_status: str = "pending"   # pending -> ready | failed
    confidence: float | None = None
    created_at: str = ""
    updated_at: str = ""

    def label(self) -> str:
        return relationship_label(self.category, self.subtype)

    def to_dict(self) -> dict:
        d = {
            "role_id": self.role_id,
            "display_name": self.display_name,
            "category": self.category,
            "subtype": self.subtype,
            "alias": self.alias,
            "me_alias": self.me_alias,
            "source_files": self.source_files,
            "persona_status": self.persona_status,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RoleMeta":
        return cls(
            role_id=str(d.get("role_id", "")),
            display_name=str(d.get("display_name", "")),
            category=str(d.get("category", "other")),
            subtype=d.get("subtype"),
            alias=str(d.get("alias", "")),
            me_alias=str(d.get("me_alias", "")),
            source_files=list(d.get("source_files", [])),
            persona_status=str(d.get("persona_status", "pending")),
            confidence=d.get("confidence"),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
        )


# ---------------------------------------------------------------------------
# Persona（精简结构化画像）—— persona.json，键为英文、值为中文
# ---------------------------------------------------------------------------

# 画像是聊天模仿的唯一事实来源。
# 生成与分析见 persona_prompts.py / persona_analyzer.py；此处负责结构与兜底。


def _default_communication_style() -> dict[str, str]:
    return {
        "sentence_structure": "",
        "message_segmentation": "",
        "vocabulary_register": "",
        "punctuation_and_emoji": "",
        "openings_and_closings": "",
    }


def _default_emotional_expression() -> dict[str, Any]:
    return {
        "how_shows_affection": "",
        "positive_triggers": [],
        "negative_triggers": [],
        "when_upset": "",
        "comfort_style": "",
    }


def default_persona() -> dict[str, Any]:
    """结构完整的空画像（供 normalize 兜底 / 预览用）。"""
    return {
        "schema_version": "1",
        "alias": "",
        "relationship": {"category": "other", "subtype": None, "label": "其他"},
        "display_name": "",
        "primary_language": "zh-CN",
        "generated_at": "",
        "source_files": [],
        "confidence": 0.0,
        "identity": {"who_they_are": "", "how_they_address_me": "", "self_reference": ""},
        "personality_dimensions": [],
        "communication_style": _default_communication_style(),
        "emotional_expression": _default_emotional_expression(),
        "catchphrases_and_quirks": [],
        "reply_length": {"typical": "", "hard_cap_chars": 120, "hard_cap_messages": 3},
        "relationship_boundaries": {"do": [], "avoid": []},
        "simulation_guidance": "",
        "notes": "",
    }


def _coerce_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _coerce_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def normalize_persona(raw: dict[str, Any], meta: RoleMeta) -> dict[str, Any]:
    """把 LLM 返回的画像合并到完整结构上，类型兜底；元信息以 meta 为准。"""
    base = default_persona()
    base.update({k: v for k, v in raw.items() if v is not None})

    # 关系信息以用户选择的类别/子类为准（生成时已注入提示，但仍需覆盖）
    base["relationship"] = {
        "category": meta.category,
        "subtype": meta.subtype,
        "label": relationship_label(meta.category, meta.subtype),
    }
    base["alias"] = meta.alias or raw.get("alias", meta.display_name)
    base["display_name"] = meta.display_name
    base["generated_at"] = now_iso()
    base["source_files"] = meta.source_files

    if not isinstance(base["identity"], dict):
        base["identity"] = _default_persona_identity()
    for k in _default_persona_identity():
        base["identity"].setdefault(k, "")
    if not isinstance(base["communication_style"], dict):
        base["communication_style"] = _default_communication_style()
    for k in _default_communication_style():
        base["communication_style"].setdefault(k, "")
    if not isinstance(base["emotional_expression"], dict):
        base["emotional_expression"] = _default_emotional_expression()
    for k in _default_emotional_expression():
        base["emotional_expression"].setdefault(k, "" if isinstance(_default_emotional_expression()[k], str) else [])

    if not isinstance(base["personality_dimensions"], list):
        base["personality_dimensions"] = []
    if not isinstance(base["catchphrases_and_quirks"], list):
        base["catchphrases_and_quirks"] = []
    if not isinstance(base["relationship_boundaries"], dict):
        base["relationship_boundaries"] = {"do": [], "avoid": []}
    if not isinstance(base["relationship_boundaries"].get("do"), list):
        base["relationship_boundaries"]["do"] = []
    if not isinstance(base["relationship_boundaries"].get("avoid"), list):
        base["relationship_boundaries"]["avoid"] = []

    rl = base["reply_length"]
    if not isinstance(rl, dict):
        rl = {}
    base["reply_length"] = {
        "typical": str(rl.get("typical", "")),
        "hard_cap_chars": _coerce_int(rl.get("hard_cap_chars"), 120),
        "hard_cap_messages": _coerce_int(rl.get("hard_cap_messages"), 3),
    }

    base["confidence"] = min(1.0, max(0.0, _coerce_float(base.get("confidence"))))
    return base


def _default_persona_identity() -> dict[str, str]:
    return {"who_they_are": "", "how_they_address_me": "", "self_reference": ""}


def validate_persona_json(obj: Any) -> list[str]:
    """只报致命问题（缺 alias / 关系类别非法 / confidence 非数）。非致命缺失交给 normalize 兜底。"""
    problems: list[str] = []
    if not isinstance(obj, dict):
        return ["输出不是 JSON 对象"]
    if not obj.get("alias"):
        problems.append("缺少 alias（对方名字）")
    rel = obj.get("relationship")
    if isinstance(rel, dict):
        if rel.get("category") not in CATEGORIES:
            problems.append(f"relationship.category 非法: {rel.get('category')!r}")
    else:
        problems.append("缺少 relationship")
    if "confidence" in obj and not isinstance(obj["confidence"], (int, float)):
        problems.append("confidence 必须是数字")
    return problems


def _section(title: str, *lines: Any) -> str:
    parts = [f"## {title}"]
    for ln in lines:
        if ln:
            parts.append(str(ln))
    return "\n".join(parts)


def persona_to_text(persona: dict[str, Any]) -> str:
    """把结构化画像渲染成一段紧凑的中文描述（聊天 system 提示与新建摘要共用）。"""
    rel = persona.get("relationship", {})
    lines: list[str] = []
    lines.append(f"- 身份：{persona.get('identity', {}).get('who_they_are') or '(记录未明确)'}")
    lines.append(f"- 怎么称呼我：{persona.get('identity', {}).get('how_they_address_me') or '(记录未明确)'}")
    lines.append(f"- 自称：{persona.get('identity', {}).get('self_reference') or '(记录未明确)'}")

    dims = persona.get("personality_dimensions") or []
    if dims:
        items = []
        for d in dims:
            if isinstance(d, dict) and d.get("dimension"):
                score = d.get("score")
                score_s = f"({_coerce_float(score):.1f})" if isinstance(score, (int, float)) else ""
                items.append(f"{d['dimension']}{score_s}")
        if items:
            lines.append(f"- 性格：{'、'.join(items[:12])}")

    cs = persona.get("communication_style", {})
    style = []
    for label, key in [
        ("句式", "sentence_structure"), ("分段", "message_segmentation"),
        ("用词", "vocabulary_register"), ("标点/表情", "punctuation_and_emoji"),
        ("开场与收尾", "openings_and_closings"),
    ]:
        val = cs.get(key) if isinstance(cs, dict) else None
        if val:
            style.append(f"{label}：{val}")
    if style:
        lines.append("- 沟通风格：" + "；".join(style))

    ee = persona.get("emotional_expression", {}) if isinstance(persona.get("emotional_expression"), dict) else {}
    if ee.get("how_shows_affection"):
        lines.append(f"- 表达关心：{ee['how_shows_affection']}")
    if ee.get("when_upset"):
        lines.append(f"- 生气/失落时：{ee['when_upset']}")

    phrases = persona.get("catchphrases_and_quirks") or []
    if phrases:
        ph = []
        for p in phrases:
            if isinstance(p, dict) and p.get("phrase"):
                m = p.get("meaning")
                ph.append(f"{p['phrase']}" + (f"（{m}）" if m else ""))
        if ph:
            lines.append(f"- 口头禅/习惯：{'、'.join(ph[:8])}")

    rl = persona.get("reply_length", {}) if isinstance(persona.get("reply_length"), dict) else {}
    length_desc = rl.get("typical")
    cap_c = rl.get("hard_cap_chars", 120)
    cap_m = rl.get("hard_cap_messages", 3)
    if length_desc:
        lines.append(f"- 回复长度：{length_desc}（上限约 {cap_c} 字 / {cap_m} 条）")

    rb = persona.get("relationship_boundaries", {}) if isinstance(persona.get("relationship_boundaries"), dict) else {}
    do = rb.get("do") or []
    avoid = rb.get("avoid") or []
    if do:
        lines.append("- 该做：" + "、".join(do[:6]))
    if avoid:
        lines.append("- 避免：" + "、".join(avoid[:6]))

    sg = persona.get("simulation_guidance")
    if sg:
        lines.append(f"- 扮演指导：{sg}")

    header = f"【画像：{persona.get('display_name') or persona.get('alias') or ''}｜{rel.get('label', '')}】"
    body = "\n".join(lines)
    return header + "\n" + body
