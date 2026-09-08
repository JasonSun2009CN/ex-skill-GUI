import httpx

from .types import ChatParams, ChatMessage


class GeminiProvider:
    id = "gemini"

    def __init__(self):
        self._client = httpx.Client(timeout=120.0)

    def _build_url(self, base_url: str | None, model: str, json_mode: bool) -> str:
        base = base_url or "https://generativelanguage.googleapis.com"
        base = base.rstrip("/")
        return f"{base}/v1beta/models/{model or 'gemini-1.5-flash-latest'}:generateContent"

    @staticmethod
    def _to_parts(messages: list[ChatMessage]) -> list[dict]:
        parts = []
        for m in messages:
            role = "model" if m.role == "assistant" else "user"
            parts.append({"role": role, "parts": [{"text": m.content}]})
        return parts

    def chat(self, params: ChatParams) -> str:
        url = self._build_url(params.base_url, params.model, params.json_mode)
        headers = {"Content-Type": "application/json"}
        query = {"key": params.api_key}

        sys_parts = []
        rest = []
        for m in params.messages:
            if m.role == "system":
                sys_parts.append(m.content)
            else:
                rest.append(m)

        body = {"contents": self._to_parts(rest)}
        if sys_parts:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(sys_parts)}]}

        config = {
            "temperature": params.temperature,
            "maxOutputTokens": params.max_tokens,
        }
        if params.json_mode:
            config["responseMimeType"] = "application/json"
        body["generationConfig"] = config

        resp = self._client.post(url, headers=headers, params=query, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    async def chat_async(self, params: ChatParams) -> str:
        url = self._build_url(params.base_url, params.model, params.json_mode)
        headers = {"Content-Type": "application/json"}
        query = {"key": params.api_key}

        sys_parts = []
        rest = []
        for m in params.messages:
            if m.role == "system":
                sys_parts.append(m.content)
            else:
                rest.append(m)

        body = {"contents": self._to_parts(rest)}
        if sys_parts:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(sys_parts)}]}

        config = {
            "temperature": params.temperature,
            "maxOutputTokens": params.max_tokens,
        }
        if params.json_mode:
            config["responseMimeType"] = "application/json"
        body["generationConfig"] = config

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, params=query, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
