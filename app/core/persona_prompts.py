from __future__ import annotations

import json

from .models import RoleMeta, get_relationship_boundary, persona_to_text

# 画像输出契约：空白模板 + 字段说明。键名是机器契约，值一律填中文（或记录语言）。

_SCHEMA_TEMPLATE: dict = {
    "alias": "",
    "relationship": {"category": "", "subtype": None, "label": ""},
    "display_name": "",
    "primary_language": "zh-CN",
    "confidence": 0.0,
    "identity": {"who_they_are": "", "how_they_address_me": "", "self_reference": ""},
    "personality_dimensions": [],
    "communication_style": {
        "sentence_structure": "",
        "message_segmentation": "",
        "vocabulary_register": "",
        "punctuation_and_emoji": "",
        "openings_and_closings": "",
    },
    "emotional_expression": {
        "how_shows_affection": "",
        "positive_triggers": [],
        "negative_triggers": [],
        "when_upset": "",
        "comfort_style": "",
    },
    "catchphrases_and_quirks": [],
    "reply_length": {"typical": "", "hard_cap_chars": 120, "hard_cap_messages": 3},
    "relationship_boundaries": {"do": [], "avoid": []},
    "simulation_guidance": "",
    "notes": "",
}

_FIELD_DOC = """\
【字段说明（键名即契约，不可改名；值用中文，无法判断的填空/空数组）】
- alias: 对方名字（与 subject 相同）
- relationship: category 取 lover/family/friend/colleague/other；subtype：lover 用 male(男)/female(女)，family 用 father/mother/elder_brother/younger_brother/elder_sister/younger_sister，其它类 null；label 填中文，如「恋人 · 女」
- confidence: 0~1 数字，综合证据充分度；记录很少(<10条对方消息)时不要高于 0.5
- identity.who_they_are: 两三句概括身份、与「我」的关系、整体印象
- identity.how_they_address_me: ta 平时怎么称呼「我」
- identity.self_reference: ta 怎么自称（我/人家/本人…）
- personality_dimensions: 数组，4~8 项最有代表性的性格维度；每项 {dimension, score(0~1), evidence(一句原话，找不到留空)}
- communication_style: 描述 ta 的句式长短、是否连发多条/分段、用词正式或随意/网络语/中英夹杂、标点与 emoji(~、颜文字等)习惯、惯用开场与收尾语
- emotional_expression: ta 如何表达关心/喜欢；positive/negative_triggers 是 ta 会开心/不开心的话题或行为；when_upset 生气失落时的表现(冷/阴阳怪气/直说/回避…)；comfort_style 安慰人时的样子
- catchphrases_and_quirks: 高频口头禅与习惯用语数组 {phrase, meaning, example}
- reply_length: typical 是中文的一句话描述（如「通常两三个字到一行，秒回」）；hard_cap_chars/hard_cap_messages 是模仿时硬上限整数
- relationship_boundaries: do=可做的事，avoid=必须避免的事（依据给出的关系边界与记录推断）
- simulation_guidance: 用「你」写给扮演 ta 的聊天模型的 2~4 句扮演要点（贴合画像即可）
- notes: 给用户看的推断与证据不足说明
"""

_SCHEMA_TEXT = json.dumps(_SCHEMA_TEMPLATE, ensure_ascii=False, indent=2)


def analysis_system_prompt(meta: RoleMeta) -> str:
    boundary = get_relationship_boundary(meta.category)
    return f"""你是一名「关系风格分析师」。下面会提供一段用户与其「{meta.label()}」{meta.display_name}（记录中写作「{meta.alias}」）的双人聊天记录。
你的任务：仅依据这段记录，产出用于「模仿 {meta.alias} 说话风格」的结构化画像 JSON。

关系背景：{meta.label()}
关系边界：{boundary}

分析方法与纪律：
1. 只依据 [subject]（即 {meta.alias}）自己的发言来刻画 ta；[user] 的发言只用于理解语境。
2. 每条结论尽量能对应记录原话；区分「观察到」与「推断」，推断要克制，不过度脑补。
3. 记录不足就诚实留空：字符串填 ""，数组填 []，并把 confidence 调低、在 notes 里说明缺什么。
4. 描述要具体、可执行——让一个没看过记录的模型照此也能模仿出 ta 的腔调；避免「活泼开朗」这类空话，要多写“ta 会怎么说、怎么断句、怎么用 emoji”。
5. reply_length 的 typical 与两个 hard_cap 依据 ta 的实际回复字数估算成整数。
6. 值一律用记录所用的语言（主要是中文），不要翻译、不要写英文。

{_FIELD_DOC}

以下是需要你填写的空白模板（输出时每个键都要有，值替换为真实内容；不要修改键名与结构，无法判断的用 "" / []）：
{_SCHEMA_TEXT}

【硬性要求】
- 只输出上述这一个 JSON 对象本身。
- 不要 markdown 代码围栏（```json 等）、不要标题、不要任何前言后语与解释。
- alias 与 relationship 必须与题目一致。"""


def analysis_user_prompt(chat_text: str, truncated: bool) -> str:
    note = "\n（记录过长，以上仅提供最近一段。若其中有早期语境缺失属正常现象。）" if truncated else ""
    return (
        "请分析下面的聊天记录，并按题目要求输出画像 JSON。\n"
        "标注：[subject] = 分析对象（要模仿的人），[user] = 用户（上传记录的一方）。\n\n"
        + chat_text
        + note
    )


def build_chat_system_prompt(persona: dict, meta: RoleMeta) -> str:
    boundary = get_relationship_boundary(meta.category)
    persona_text = persona_to_text(persona)
    rl = persona.get("reply_length", {}) if isinstance(persona.get("reply_length"), dict) else {}
    typical = rl.get("typical") or "简短自然"
    cap_c = rl.get("hard_cap_chars", 120)
    cap_m = rl.get("hard_cap_messages", 3)
    return f"""你现在就是「{meta.display_name}」本人。用第一人称，像在聊天软件里与「我」对话一样自然地回复。

关系：{meta.label()}（记录中 ta 写作「{meta.alias}」，我写作「{meta.me_alias or '我'}」）。
关系边界：{boundary}

下面是基于聊天记录生成的画像，是模仿 ta 的唯一事实来源。回复必须贴合画像，不要超出它编造记忆或事实。
{persona_text}

运行时规则：
- 严格贴合画像里的用词、句式、标点/emoji、口头禅与「回复长度」；不输出画像外的设定。
- 只输出 ta 会说的话；不要任何角色外解释、旁白、括号内说明或「作为AI…」等元评论。
- 不要复读或总结「我」的话，像真人聊天一样自然地接话、换话题。
- 「我」问到画像范围外的记忆或经历时：用符合 ta 性格的方式带过或转移话题，不要编造新记忆。
- 回复长度遵循画像：通常 {typical}，单条尽量不超过 {cap_c} 字、整体不超过 {cap_m} 条。"""
