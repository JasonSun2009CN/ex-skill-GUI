from __future__ import annotations

from pathlib import Path

from . import persona_store
from .llm.client import ChatMessage, LLMClient
from .models import RoleMeta
from .persona_prompts import build_chat_system_prompt

HISTORY_WINDOW = 40
MAX_TOKENS_LOW, MAX_TOKENS_HIGH = 80, 800


def tokens_for_cap(cap_chars: int) -> int:
    """把字数软上限换算成 max_tokens（中文约 1 token/字 + 缓冲，再上下限夹紧）。"""
    est = int((cap_chars or 120) * 1.5) + 40
    return max(MAX_TOKENS_LOW, min(MAX_TOKENS_HIGH, est))


class ChatSession:
    """一次对话会话：加载/追加 history.jsonl，用 persona 拼系统提示后请求 LLM。"""

    def __init__(self, llm: LLMClient, meta: RoleMeta, persona: dict):
        self.llm = llm
        self.meta = meta
        self.persona = persona
        self.system_prompt = build_chat_system_prompt(persona, meta)
        rl = persona.get("reply_length", {}) if isinstance(persona.get("reply_length"), dict) else {}
        self.max_tokens = tokens_for_cap(rl.get("hard_cap_chars", 120))
        self.temperature = 0.85
        # 内存历史从本地持久化加载最近 N 条
        self.history: list[dict] = persona_store.read_history(meta.role_id, HISTORY_WINDOW)

    def reset_context(self) -> None:
        """清空对话上下文（不清磁盘历史），从下一句起只带画像。"""
        self.history = []

    def _sendable(self) -> list[ChatMessage]:
        msgs = [ChatMessage("system", self.system_prompt)]
        for h in self.history[-HISTORY_WINDOW:]:
            msgs.append(ChatMessage(h["role"], h["content"]))
        return msgs

    def send(self, user_text: str) -> str:
        """发送一句话：写历史 → 调 LLM → 返回回复文本（已持久化）。"""
        user_text = (user_text or "").strip()
        if not user_text:
            return ""
        self._append("user", user_text)

        reply = self.llm.chat(
            self._sendable(),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        reply = (reply or "").strip()
        if reply:
            self._append("assistant", reply)
        return reply

    def _append(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        persona_store.append_history(self.meta.role_id, role, content)
