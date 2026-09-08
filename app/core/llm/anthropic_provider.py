import httpx

from .types import ChatParams, ChatMessage


class AnthropicProvider:
    id = "anthropic"

    def __init__(self):
        self._client = httpx.Client(timeout=120.0)

    def _build_url(self, base_url: str | None) -> str:
        if base_url:
            return base_url.rstrip("/") + "/v1/messages"
        return "https://api.anthropic.com/v1/messages"

    @staticmethod
    def _extract_system(messages: list[ChatMessage]) -> tuple[str, list[ChatMessage]]:
        sys_parts = []
        rest = []
        for m in messages:
            if m.role == "system":
                sys_parts.append(m.content)
            else:
                rest.append(m)
        return "\n\n".join(sys_parts), rest

    def chat(self, params: ChatParams) -> str:
        url = self._build_url(params.base_url)
        headers = {
            "x-api-key": params.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        system, rest = self._extract_system(params.messages)
        body = {
            "model": params.model or "claude-3-haiku-20240307",
            "messages": [{"role": m.role, "content": m.content} for m in rest],
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
        }
        if system:
            body["system"] = system

        resp = self._client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]

    async def chat_async(self, params: ChatParams) -> str:
        url = self._build_url(params.base_url)
        headers = {
            "x-api-key": params.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        system, rest = self._extract_system(params.messages)
        body = {
            "model": params.model or "claude-3-haiku-20240307",
            "messages": [{"role": m.role, "content": m.content} for m in rest],
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
        }
        if system:
            body["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]
