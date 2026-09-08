import httpx

from .types import ChatParams, ChatMessage


class OpenAIProvider:
    id = "openai"

    def __init__(self):
        self._client = httpx.Client(timeout=120.0)

    def _build_url(self, base_url: str | None) -> str:
        if base_url:
            return base_url.rstrip("/") + "/chat/completions"
        return "https://api.openai.com/v1/chat/completions"

    def chat(self, params: ChatParams) -> str:
        url = self._build_url(params.base_url)
        headers = {
            "Authorization": f"Bearer {params.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": params.model or "gpt-4o-mini",
            "messages": [{"role": m.role, "content": m.content} for m in params.messages],
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
        }
        if params.json_mode:
            body["response_format"] = {"type": "json_object"}

        resp = self._client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def chat_async(self, params: ChatParams) -> str:
        url = self._build_url(params.base_url)
        headers = {
            "Authorization": f"Bearer {params.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": params.model or "gpt-4o-mini",
            "messages": [{"role": m.role, "content": m.content} for m in params.messages],
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
        }
        if params.json_mode:
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
