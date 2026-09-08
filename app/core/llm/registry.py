from .types import LLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider

_REGISTRY: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def list_providers() -> list[str]:
    return list(_REGISTRY.keys())


def get_provider(provider_name: str) -> LLMProvider:
    cls = _REGISTRY.get(provider_name)
    if cls is None:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(_REGISTRY.keys())}")
    return cls()
