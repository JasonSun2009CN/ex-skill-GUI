#!/usr/bin/env python3
"""无 GUI、无网络依赖的引擎层冒烟测试。

直接运行（在仓库根目录、项目 venv 内）：
    python smoke_test.py
退出码 0 = 全部通过。

需要真实 LLM 的集成测试不在此运行（见 persona_analyzer/pipeline 的 EX_SKILL_LIVE 探针）。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

# 把测试数据写到临时目录，避免污染 ~/.ex-skill
_TMP = tempfile.mkdtemp(prefix="exskill-smoke-")
os.environ["EX_SKILL_DATA_DIR"] = _TMP

from app.core import chat_session, config, evidence, models, paths, persona_analyzer, persona_store, pipeline  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "tests" / "fixtures" / "sample_chat.txt"

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok  {name}")
    else:
        _failures.append(f"{name}: {detail}")
        print(f"FAIL  {name}  {detail}")


# ---------------------------------------------------------------------------
# config / paths
# ---------------------------------------------------------------------------


def test_config() -> None:
    print("[config / paths]")
    c = config.Config.from_dict({"provider": "anthropic", "api_key": "k", "model": "m"})
    check("旧 provider 键迁移到 anthropic", c.api_mode == "anthropic")
    c2 = config.Config.from_dict({"provider": "deepseek", "api_key": "k"})
    check("旧 provider 键迁移到 openai", c2.api_mode == "openai")
    cfg = config.Config(api_mode="openai", api_key="sk-x", base_url="https://x/v1", model="deepseek-chat")
    config.save_config(cfg)
    check("config 落盘后读取一致", config.load_config() == cfg)

    paths.ensure_layout()
    check("data_root 指向临时目录", str(paths.data_root()) == _TMP)
    check("roles 目录已建", (paths.data_root() / "roles").is_dir())


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


def test_models() -> None:
    print("[models]")
    check("关系标签 恋人·女", models.relationship_label("lover", "female") == "恋人 · 女")
    check("关系标签 家人·哥哥", models.relationship_label("family", "elder_brother") == "家人 · 哥哥")
    check("关系标签 同事(无子类)", models.relationship_label("colleague") == "同事")

    meta = models.RoleMeta(
        role_id=models.make_role_id("Joanna"),
        display_name="Joanna",
        category="lover",
        subtype="female",
        alias="Joanna",
        me_alias="我",
        source_files=["sample_chat.txt"],
    )
    check("role_id slug 稳定前缀", meta.role_id.startswith("joanna-"))
    check("RoleMeta 往返", models.RoleMeta.from_dict(meta.to_dict()).to_dict() == meta.to_dict())

    persona = models.normalize_persona(
        {
            "alias": "Joanna",
            "confidence": "0.85",
            "identity": {"who_they_are": "我的恋人"},
            "reply_length": {"hard_cap_chars": "140"},
            "personality_dimensions": [{"dimension": "幽默", "score": 0.9, "evidence": ""}],
        },
        meta,
    )
    check("normalize 覆盖关系信息", persona["relationship"]["category"] == "lover")
    check("normalize confidence 转 float", persona["confidence"] == 0.85)
    check("normalize reply_length 转 int", persona["reply_length"]["hard_cap_chars"] == 140)
    check("normalize 补齐 identity 字段", persona["identity"]["self_reference"] == "")
    check("normalize 兜底 communication_style", persona["communication_style"]["vocabulary_register"] == "")

    fatal = models.validate_persona_json({"alias": "J"})
    check("validate: 缺 relationship 报致命", any("relationship" in x for x in fatal))
    ok = models.validate_persona_json(persona)
    check("validate: 合法画像无致命", ok == [])

    text = models.persona_to_text(persona)
    check("persona_to_text 含身份", "我的恋人" in text)
    check("persona_to_text 含关系标签", "恋人" in text)


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------


def test_evidence() -> None:
    print("[evidence]")
    content = FIXTURE.read_text(encoding="utf-8")
    turns = evidence.parse_text(content)
    counts = evidence.detect_speakers(turns)
    check("fixture 解析出 13 条消息", len(turns) == 13, f"got {len(turns)}")
    check("说话人只有 Joanna/我", set(counts) == {"Joanna", "我"}, f"got {set(counts)}")
    check("Joanna 9 条 / 我 4 条", counts.get("Joanna") == 9 and counts.get("我") == 4, str(counts))

    check("suggest_me_alias 选 我", evidence.suggest_me_alias(counts, "Joanna") == "我")
    labeled, dropped_speakers, dropped_count = evidence.label_turns(turns, "Joanna", "我")
    check("label_turns 全保留", dropped_count == 0 and len(labeled) == 13, f"{dropped_count}/{len(labeled)}")
    check("标注顺序正确", labeled[0].role == "subject" and labeled[2].role == "user")

    text, truncated = evidence.format_turns(labeled)
    check("format_turns 全文未截断", not truncated and "[subject]" in text and "[user]" in text)
    short, short_trunc = evidence.format_turns(labeled, max_chars=100)
    check("超长保留尾部并置截断标记", short_trunc and "你到时候不许" in short, short[:80])

    # 群聊场景：第三方被丢弃并计数
    group = (
        "Joanna  23:04\n今天的月亮很好看\n\n我  23:05\n是呀\n\n"
        "路人甲  23:06\n哈哈哈围观\n\nJoanna  23:07\n你别理他\n"
    )
    g_turns = evidence.parse_text(group)
    gl, gd, gc = evidence.label_turns(g_turns, "Joanna", "我")
    check("第三方说话人被丢弃", set(gd) == {"路人甲"} and gc == 1, str(gd))
    check("群聊丢弃后条数正确", len(gl) == 3, str(len(gl)))

    raw, all_turns = evidence.read_evidence_files([FIXTURE])
    check("read_evidence_files 拼接", "===== sample_chat.txt =====" in raw and len(all_turns) == 13)


# ---------------------------------------------------------------------------
# persona_store
# ---------------------------------------------------------------------------


def test_store() -> None:
    print("[persona_store]")
    meta = models.RoleMeta(
        role_id=models.make_role_id("Joanna"),
        display_name="Joanna",
        category="lover",
        subtype="female",
        alias="Joanna",
        me_alias="我",
        source_files=["sample_chat.txt"],
    )
    persona_store.create_role(meta, evidence_raw="raw-text")
    check("create_role 目录与 evidence 落盘", persona_store.evidence_path(meta.role_id).exists())
    loaded = persona_store.get_role(meta.role_id)
    check("get_role 命中", loaded is not None and loaded.role_id == meta.role_id)

    persona = models.normalize_persona({"alias": "Joanna", "confidence": 0.7}, meta)
    persona_store.save_persona(meta.role_id, persona)
    back = persona_store.load_persona(meta.role_id)
    check("persona 落盘往返", back is not None and back["confidence"] == 0.7)
    check("保存画像后 persona_status=ready", persona_store.get_role(meta.role_id).persona_status == "ready")

    persona_store.append_history(meta.role_id, "user", "你好")
    persona_store.append_history(meta.role_id, "assistant", "在呀")
    hist = persona_store.read_history(meta.role_id)
    check("history 写入两条", len(hist) == 2 and hist[0]["role"] == "user")

    persona_store.delete_role(meta.role_id)
    check("delete_role 清理索引与目录", persona_store.get_role(meta.role_id) is None
          and not persona_store.evidence_path(meta.role_id).exists())


# ---------------------------------------------------------------------------
# persona_analyzer / pipeline / chat_session（用假 LLM，无网络）
# ---------------------------------------------------------------------------


class FakeLLM:
    """按顺序返回预设输出的假客户端。"""

    def __init__(self, outputs: list[str]):
        self.outputs = list(outputs)
        self.calls: list[tuple] = []

    def chat(self, messages, **kwargs):
        self.calls.append(([dict(role=m.role, content=m.content) for m in messages], kwargs))
        if not self.outputs:
            raise RuntimeError("FakeLLM 输出用尽")
        return self.outputs.pop(0)


def _make_valid_persona() -> dict:
    return {
        "alias": "Joanna",
        "relationship": {"category": "lover", "subtype": "female", "label": "恋人 · 女"},
        "confidence": 0.75,
        "identity": {"who_they_are": "我的恋人，说话爱用波浪号"},
        "communication_style": {"punctuation_and_emoji": "句尾常加 ~ 和颜文字"},
        "catchphrases_and_quirks": [{"phrase": "诶呀~", "meaning": "撒娇/无奈"}],
        "reply_length": {"typical": "通常一句话", "hard_cap_chars": 80, "hard_cap_messages": 2},
        "simulation_guidance": "你语气软软的，爱用 ~",
    }


def test_analyzer() -> None:
    print("[persona_analyzer]")
    meta = models.RoleMeta(
        role_id=models.make_role_id("Joanna"),
        display_name="Joanna", category="lover", subtype="female",
        alias="Joanna", me_alias="我",
    )
    raw = json.dumps(_make_valid_persona(), ensure_ascii=False)
    fake = FakeLLM(["抱歉我重说一次", f"```json\n{raw}\n```"])
    persona = persona_analyzer.analyze(fake, meta, chat_text="[subject] 今天月亮好看\n[user] 是呀", progress_cb=None)
    check("analyzer: 首次非法 JSON 触发重试", len(fake.calls) == 2, str(len(fake.calls)))
    check("analyzer: 重试带修正上下文", len(fake.calls[1][0]) == 4)
    check("analyzer: 带围栏 JSON 被解析", persona["alias"] == "Joanna")
    check("analyzer: relationship 以 meta 覆盖", persona["relationship"]["subtype"] == "female")


def test_pipeline_and_chat() -> None:
    print("[pipeline / chat_session]")
    raw = json.dumps(_make_valid_persona(), ensure_ascii=False)
    fake = FakeLLM([raw])
    draft = pipeline.NewRoleDraft(
        display_name="Joanna", category="lover", subtype="female",
        alias="Joanna", me_alias="我", files=[str(FIXTURE)],
    )
    meta = pipeline.build_role(fake, draft, progress_cb=None)
    check("pipeline: 返回角色 meta", meta is not None and meta.persona_status == "ready")
    check("pipeline: persona 落盘", persona_store.load_persona(meta.role_id) is not None)
    check("pipeline: 目录有 evidence 与 history", persona_store.evidence_path(meta.role_id).exists())

    persona = persona_store.load_persona(meta.role_id)
    reply_fake = FakeLLM(["在呀 怎么啦~"])
    sess = chat_session.ChatSession(reply_fake, meta, persona)
    check("chat: 系统提示含口头禅", "诶呀" in sess.system_prompt)
    check("chat: 系统提示含长度约束", "80" in sess.system_prompt or "2" in sess.system_prompt)
    check("chat: max_tokens 依字软上限换算", 80 <= sess.max_tokens <= 800, str(sess.max_tokens))

    before = len(persona_store.read_history(meta.role_id))
    reply = sess.send("今晚出来吃饭吗")
    check("chat: 返回回复", reply == "在呀 怎么啦~")
    after = persona_store.read_history(meta.role_id)
    check("chat: 历史追加 user+assistant", len(after) == before + 2, f"{len(after)} vs {before + 2}")
    check("chat: 发送内容入历史", after[-1]["role"] == "assistant" and after[-1]["content"] == reply)

    # 新会话能重载已持久化历史
    sess2 = chat_session.ChatSession(FakeLLM(["好呀"]), meta, persona)
    check("chat: 重载历史", len(sess2.history) == len(after))

    # 字数上限换算的边界
    check("chat: tokens_for_cap 下限夹紧", chat_session.tokens_for_cap(1) == 80)
    check("chat: tokens_for_cap 上限夹紧", chat_session.tokens_for_cap(10000) == 800)


def main() -> int:
    test_config()
    test_models()
    test_evidence()
    test_store()
    test_analyzer()
    test_pipeline_and_chat()
    if _failures:
        print(f"\n{len(_failures)} 项失败：")
        for f in _failures:
            print("  - " + f)
        return 1
    print("\n全部通过 ✔")
    return 0


# ---------------------------------------------------------------------------
# 可选：真实 LLM 集成探针（EX_SKILL_LIVE=1 python smoke_test.py）
# 读取已保存配置，用 fixture 真实跑一次画像生成（不落盘）。
# ---------------------------------------------------------------------------


def live_probe() -> int:
    from app.core import evidence, persona_analyzer
    from app.core.config import make_client
    from app.core.models import make_role_id

    cfg = config.load_config()
    if not cfg.is_configured():
        print("未配置模型。请先在 GUI「设置」里保存 API Key 与模型名，或手动写 ~/.ex-skill/config.json。")
        return 1
    llm = make_client()

    meta = models.RoleMeta(
        role_id=make_role_id("Joanna"),
        display_name="Joanna", category="lover", subtype="female",
        alias="Joanna", me_alias="我", source_files=[FIXTURE.name],
    )
    content = FIXTURE.read_text(encoding="utf-8")
    turns = evidence.parse_text(content)
    labeled, _t, _d = evidence.label_turns(turns, "Joanna", "我")
    text, truncated = evidence.format_turns(labeled)
    print("发送中…（分析阶段约需 10–60s）")
    persona = persona_analyzer.analyze(llm, meta, text, truncated=truncated)
    print(json.dumps(persona, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        if os.environ.get("EX_SKILL_LIVE") == "1":
            raise SystemExit(live_probe())
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
