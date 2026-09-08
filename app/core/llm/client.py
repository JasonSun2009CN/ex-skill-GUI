from __future__ import annotations

from dataclasses import dataclass

import httpx

from ..config import Config

DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-sonnet-5"}


class LLMError(Exception):
    """带可读信息的 LLM 调用错误（HTTP 状态 + 响应片段）。"""


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMClient:
    """统一 LLM 客户端，只支持两种 API 形态：

    - api_mode="anthropic": POST <base_url>/v1/messages
    - api_mode="openai":    POST <base_url>/chat/completions（OpenAI 兼容）
    """

    def __init__(self, cfg: Config, timeout: float = 180.0):
        self.cfg = cfg
        self.timeout = timeout

    # ------------------------------------------------------------------
    def _model(self) -> str:
        return self.cfg.model or DEFAULT_MODELS.get(self.cfg.api_mode, "")

    def _endpoint(self, path: str) -> str:
        base = (self.cfg.base_url or "").rstrip("/")
        if not base:
            base = {"openai": "https://api.openai.com/v1", "anthropic": "https://api.anthropic.com"}[self.cfg.api_mode]
        return base + path

    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        if not self.cfg.api_key:
            raise LLMError("未设置 API Key，请先在「设置」里填写模型配置。")
        if self.cfg.api_mode == "anthropic":
            return self._chat_anthropic(messages, temperature=temperature, max_tokens=max_tokens)
        return self._chat_openai(messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode)

    def probe(self, max_tokens: int = 32) -> tuple[bool, str]:
        """轻量连通性测试（设置对话框的「测试连接」用）。"""
        try:
            reply = self.chat(
                [
                    ChatMessage("system", "你是一个连通性测试助手。"),
                    ChatMessage("user", "只回复四个字：连接成功"),
                ],
                temperature=0,
                max_tokens=max_tokens,
            )
            return True, (reply or "(空回复)")
        except Exception as e:  # noqa: BLE001
            return False, str(e)

    # ------------------------------------------------------------------
    def _chat_openai(self, messages, *, temperature, max_tokens, json_mode) -> str:
        url = self._endpoint("/chat/completions")
        headers = {"Authorization": f"Bearer {self.cfg.api_key}", "Content-Type": "application/json"}
        body: dict = {
            "model": self._model(),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode and _text_has_json(messages):
            body["response_format"] = {"type": "json_object"}
        try:
            data = self._post_json(url, headers, body)
        except LLMError as e:
            # 部分 OpenAI 兼容端点不支持 response_format
            if json_mode and "response_format" in str(e):
                body.pop("response_format", None)
                data = self._post_json(url, headers, body)
            else:
                raise
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
        if content is None:
            raise LLMError("模型返回内容为空或响应结构异常。")
        return content

    def _chat_anthropic(self, messages, *, temperature, max_tokens) -> str:
        url = self._endpoint("/v1/messages")
        headers = {
            "x-api-key": self.cfg.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        system_parts = [m.content for m in messages if m.role == "system"]
        rest = [m for m in messages if m.role != "system"]
        body: dict = {
            "model": self._model(),
            "messages": [{"role": m.role, "content": m.content} for m in rest],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        data = self._post_json(url, headers, body)
        blocks = data.get("content") or []
        if blocks and isinstance(blocks[0], dict) and blocks[0].get("text") is not None:
            return blocks[0]["text"]
        raise LLMError("模型返回内容为空或响应结构异常。")

    def _post_json(self, url: str, headers: dict, body: dict) -> dict:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, json=body)
        except httpx.TimeoutException:
            raise LLMError(f"请求超时（>{self.timeout:.0f}s）：{url}") from None
        except httpx.HTTPError as e:
            raise LLMError(f"网络错误：{e}") from None
        if resp.status_code >= 400:
            snippet = resp.text[:300]
            raise LLMError(f"HTTP {resp.status_code}：{snippet}")
        try:
            return resp.json()
        except ValueError:
            raise LLMError("响应不是合法 JSON。") from None


def _text_has_json(messages: list[ChatMessage]) -> bool:
    joined = " ".join(m.content for m in messages).lower()
    return "json" in joined
