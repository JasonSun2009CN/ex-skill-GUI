from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .paths import config_path

# 模型服务预设：名称 -> (api_mode, base_url, 默认模型)
# api_mode 只分两种：openai（OpenAI 兼容 /chat/completions）与 anthropic（/v1/messages）。
PROVIDER_PRESETS: dict[str, tuple[str, str, str]] = {
    "OpenAI": ("openai", "https://api.openai.com/v1", "gpt-4o-mini"),
    "Anthropic Claude": ("anthropic", "https://api.anthropic.com", "claude-sonnet-5"),
    "DeepSeek": ("openai", "https://api.deepseek.com/v1", "deepseek-chat"),
    "阿里云百炼 Qwen": ("openai", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
    "智谱 GLM": ("openai", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
    "OpenRouter": ("openai", "https://openrouter.ai/api/v1", "anthropic/claude-sonnet-5"),
}

# 旧版 config 里 openai 兼容 provider 集合（用于字段迁移）
_OLD_OPENAI_COMPAT = {
    "openai", "deepseek", "qwen", "moonshot", "zhipu", "groq",
    "mistral", "together", "siliconflow", "custom-openai", "openrouter",
    "orcarouter", "gemini",
}


@dataclass
class Config:
    api_mode: str = "openai"  # "openai" | "anthropic"
    api_key: str = ""
    base_url: str = ""        # 留空表示该形态官方默认
    model: str = ""
    theme_mode: str = "system"  # "system" | "light" | "dark"
    sidebar_width: int = 240

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        api_mode = data.get("api_mode")
        # 迁移旧字段：没有 api_mode，但有旧 provider 键
        if not api_mode and data.get("provider"):
            provider = str(data["provider"]).lower()
            api_mode = "anthropic" if provider == "anthropic" else "openai"
        theme_mode = data.get("theme_mode", "system")
        if theme_mode not in ("system", "light", "dark"):
            theme_mode = "system"
        return cls(
            api_mode=api_mode if api_mode in ("openai", "anthropic") else "openai",
            api_key=str(data.get("api_key", "")),
            base_url=str(data.get("base_url", "")),
            model=str(data.get("model", "")),
            theme_mode=theme_mode,
            sidebar_width=int(data.get("sidebar_width", 240)),
        )

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)


def load_config() -> Config:
    p = config_path()
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return Config.from_dict(json.load(f))
        except Exception:
            pass
    return Config()


def make_client() -> "LLMClient":
    """按当前已保存配置构造 LLMClient（延迟 import 避免循环依赖）。"""
    from .llm.client import LLMClient

    return LLMClient(load_config())


def save_config(config: Config) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
