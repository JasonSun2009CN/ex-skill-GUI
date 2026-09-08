from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .llm.types import LLMProvider, ChatMessage, ChatParams
from .evidence_parser import ChatTurn, format_for_llm
from .validators.profile_validator import validate_profile, ValidationError
from .paths import PROFILES_DIR, SKILL_TEMPLATES_DIR


@dataclass
class LLMCallConfig:
    api_key: str
    model: Optional[str] = None
    base_url: Optional[str] = None


import re as _re
_GITHUB_ATTACH_RE = _re.compile(r'^\s*\[[^\]]+\]\(https?://github\.com/[^)]+\)\s*$')

def _read_text(p: Path) -> str:
    if not p.exists():
        return ""
    raw = p.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    out = []
    started = False
    for line in lines:
        if not started and _GITHUB_ATTACH_RE.match(line):
            continue
        started = True
        out.append(line)
    return "\n".join(out)


class PersonalityAnalyzer:
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self._skill_md = _read_text(SKILL_TEMPLATES_DIR / "SKILL.md")
        self._rubric_md = _read_text(SKILL_TEMPLATES_DIR / "references" / "analysis_rubric.md")
        self._template_md = _read_text(SKILL_TEMPLATES_DIR / "templates" / "personality-profile.template.md")

    def _build_system_prompt(self) -> str:
        parts = [
            self._skill_md or "",
            "\n\n---\n## Analysis Rubric\n\n",
            self._rubric_md or "",
            "\n\n---\n## Output Template (you MUST follow this EXACT structure)\n\n",
            self._template_md or "",
            "\n\n---\n## 硬性要求\n",
            "1. 只输出最终的 profile.md 完整内容，不要任何解释、前言、后话。\n",
            "2. 所有 section 标题必须与 template 完全一致（文字和层级）。\n",
            "3. 第 15 节 Machine-Readable Profile 必须是合法 JSON，放在 ```json ... ``` 代码块里。\n",
            "4. 数据不足或无法判断的字段填 null 或 []，不要省略 section。\n",
            "5. 把所有推断明确标注为 \"[推断]\"，观察到的事实标注为 \"[观察]\"。\n",
        ]
        return "\n".join(parts)

    def analyze(
        self,
        chat_turns: list[ChatTurn],
        subject_alias: str,
        llm_cfg: LLMCallConfig,
        subject_role: str = "ex-partner",
        source_files: list[str] | None = None,
        progress_cb: Callable[[str], None] | None = None,
    ) -> Path:
        def log(s: str):
            if progress_cb:
                progress_cb(s)

        system_prompt = self._build_system_prompt()
        chat_text = format_for_llm(chat_turns)
        now = datetime.utcnow().isoformat() + "Z"
        sf = source_files or []

        user_prompt = (
            f"subject_alias={subject_alias}\n"
            f"subject_role={subject_role}\n"
            f"generated_at={now}\n"
            f"source_files={', '.join(sf) if sf else '(inline)'}\n\n"
            f"## 聊天记录 / 证据材料\n\n"
            "说明: [user] = 用户(上传者)的发言, [subject] = 分析对象的发言。\n\n"
            f"{chat_text}\n"
        )

        raw_output = ""
        errors: list[ValidationError] = []
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            log(f"[分析] 第 {attempt}/{max_attempts} 次调用 LLM...")
            messages = [
                ChatMessage("system", system_prompt),
                ChatMessage("user", user_prompt),
            ]
            if attempt > 1 and raw_output and errors:
                messages.append(ChatMessage("assistant", raw_output))
                err_text = "\n".join(
                    f"- [{e.severity}] {e.code}: {e.message}" for e in errors
                )
                messages.append(ChatMessage(
                    "user",
                    "校验失败，请修复以下问题并重新输出完整的 profile.md 全文（不要只输出修复部分）：\n"
                    + err_text,
                ))

            try:
                raw_output = self.llm.chat(ChatParams(
                    api_key=llm_cfg.api_key,
                    base_url=llm_cfg.base_url,
                    model=llm_cfg.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=12000,
                    json_mode=False,
                ))
            except Exception as e:
                log(f"[错误] LLM 调用失败: {e}")
                raise

            errors = validate_profile(raw_output)
            fatal = [e for e in errors if e.severity == "error"]
            if not fatal:
                log(f"[分析] 校验通过 (warning={len(errors)})")
                break
            log(f"[分析] 校验未通过: errors={len(fatal)} warnings={len(errors) - len(fatal)}")
        else:
            raise RuntimeError(f"分析失败，{max_attempts} 次校验未通过: {errors}")

        out_path = PROFILES_DIR / f"{subject_alias}_personality_profile.md"
        out_path.write_text(raw_output, encoding="utf-8")
        log(f"[完成] 已写入: {out_path}")
        return out_path
