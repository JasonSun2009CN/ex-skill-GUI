from dataclasses import dataclass, field
from typing import Protocol, AsyncIterable, Literal

ChatRole = Literal["system", "user", "assistant"]


@dataclass
class ChatMessage:
    role: ChatRole
    content: str


@dataclass
class ChatParams:
    api_key: str
    messages: list[ChatMessage]
    model: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1024
    json_mode: bool = False


class LLMProvider(Protocol):
    id: str

    def chat(self, params: ChatParams) -> str: ...

    async def chat_async(self, params: ChatParams) -> str: ...
