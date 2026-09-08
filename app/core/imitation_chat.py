from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .llm.types import LLMProvider, ChatMessage, ChatParams


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _extract_alias_from_skill_dir(skill_dir: Path) -> str:
    name = skill_dir.name
    m = re.match(r"^imitation-(.+)$", name)
    if m:
        return m.group(1)
    for f in (skill_dir / "references").iterdir():
        mm = re.match(r"^(.+?)_personality_profile\.md$", f.name)
        if mm:
            return mm.group(1)
    return name


class ImitationChatSession:
    def __init__(self, llm: LLMProvider, skill_dir: str | Path, temperature: float = 0.85, max_tokens: int = 300):
        self.llm = llm
        self.skill_dir = Path(skill_dir)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.history: list[ChatMessage] = []

        skill_md = _read_text(self.skill_dir / "SKILL.md")
        alias = _extract_alias_from_skill_dir(self.skill_dir)
        profile_md = _read_text(self.skill_dir / "references" / f"{alias}_personality_profile.md")

        self.system_prompt = (
            "# Role & Instructions (use as system prompt)\n\n"
            + skill_md
            + "\n\n# Personality Source of Truth (treat as authoritative)\n\n"
            + profile_md
            + "\n\n---\n"
            + "## Runtime Rules\n"
            + f"- 你现在就是 **{alias}** 本人，用第一人称回复。\n"
            + "- 回复必须严格符合上面 profile 中描述的说话方式、语气、句长、emoji 习惯、口头禅。\n"
            + "- 不要输出任何角色外的解释、元评论、括号内说明；只输出你（对方）说的话。\n"
            + "- 不要在回复里重复用户的话；像真人聊天一样自然接上。\n"
            + "- 如果用户提到 profile 里某个 memory moment，用你（对方）当时的视角和情绪回应。\n"
            + "- 如果用户问的问题超出 profile 记忆范围，就用符合你性格的方式搪塞过去，不要编造新记忆。\n"
        )

    def reset(self) -> None:
        self.history = []

    def send(
        self,
        user_text: str,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> str:
        self.history.append(ChatMessage("user", user_text))
        recent = self.history[-40:]

        reply = self.llm.chat(ChatParams(
            api_key=api_key,
            model=model,
            base_url=base_url,
            messages=[
                ChatMessage("system", self.system_prompt),
                *recent,
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        ))
        self.history.append(ChatMessage("assistant", reply))
        return reply
