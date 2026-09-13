from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .paths import config_path

# 模型服务预设。api_mode 只分两种：openai（OpenAI 兼容 /chat/completions）与
# anthropic（/v1/messages）。key 是稳定标识，会被写进 config.json 的 provider_preset
# 字段（旧版没有这个字段，所以设置界面里会退化成「自定义」——见 infer_preset_key）。
#
# models 的每一项是 (模型 ID, 中文说明)，**第一项即该预设的默认模型**。
# 模型 ID 会随厂商更新换代（如 moonshot-v1-8k、grok-3-mini、llama-3.3-70b-versatile
# 均已下线），这里只放相对长命的 ID；设置里的「获取模型列表」会向服务端
# GET /models 拉当前可用列表，以那个为准。
@dataclass(frozen=True)
class ProviderPreset:
    key: str
    label: str
    api_mode: str
    base_url: str
    models: tuple[tuple[str, str], ...]

    @property
    def default_model(self) -> str:
        return self.models[0][0] if self.models else ""


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset("openai", "OpenAI", "openai", "https://api.openai.com/v1", (
        ("gpt-4o-mini", "便宜、够用"),
        ("gpt-4o", "上一代旗舰"),
        ("gpt-5", "推理模型"),
    )),
    ProviderPreset("anthropic", "Anthropic Claude", "anthropic", "https://api.anthropic.com", (
        ("claude-sonnet-5", "均衡"),
        ("claude-opus-5", "最强"),
        ("claude-haiku-4-5", "最便宜"),
    )),
    ProviderPreset("gemini", "Google Gemini", "openai",
                   "https://generativelanguage.googleapis.com/v1beta/openai", (
        ("gemini-2.5-flash", "便宜、快"),
        ("gemini-2.5-pro", "更强"),
        ("gemini-3-flash-preview", "预览版"),
    )),
    ProviderPreset("xai", "xAI Grok", "openai", "https://api.x.ai/v1", (
        ("grok-4-fast-non-reasoning", "快"),
        ("grok-4.6", "旗舰"),
    )),
    ProviderPreset("mistral", "Mistral AI", "openai", "https://api.mistral.ai/v1", (
        ("mistral-small-latest", "便宜"),
        ("mistral-large-latest", "旗舰"),
    )),
    ProviderPreset("groq", "Groq", "openai", "https://api.groq.com/openai/v1", (
        ("openai/gpt-oss-20b", "最快最便宜"),
        ("openai/gpt-oss-120b", "更强"),
    )),
    ProviderPreset("together", "Together AI", "openai", "https://api.together.xyz/v1", (
        ("moonshotai/Kimi-K3", "旗舰"),
        ("zai-org/GLM-5.3-Flash", "便宜"),
    )),
    ProviderPreset("deepseek", "DeepSeek", "openai", "https://api.deepseek.com/v1", (
        ("deepseek-chat", "通用对话"),
        ("deepseek-reasoner", "推理"),
        ("deepseek-v4-pro", "新一代旗舰"),
    )),
    ProviderPreset("moonshot", "月之暗面 Kimi（国内站）", "openai", "https://api.moonshot.cn/v1", (
        ("kimi-k2.6", "通用，256K"),
        ("kimi-k3", "旗舰，1M"),
        ("kimi-k2.5", "上一代"),
    )),
    ProviderPreset("moonshot-intl", "月之暗面 Kimi（国际站）", "openai", "https://api.moonshot.ai/v1", (
        ("kimi-k2.6", "通用，256K"),
        ("kimi-k3", "旗舰，1M"),
        ("kimi-k2.5", "上一代"),
    )),
    ProviderPreset("qwen", "阿里云百炼 Qwen", "openai",
                   "https://dashscope.aliyuncs.com/compatible-mode/v1", (
        ("qwen-plus", "均衡"),
        ("qwen-max", "最强"),
        ("qwen-turbo", "最快"),
    )),
    ProviderPreset("zhipu", "智谱 GLM", "openai", "https://open.bigmodel.cn/api/paas/v4", (
        ("glm-4-flash", "免费/最便宜"),
        ("glm-4.6", "通用"),
        ("glm-5", "新一代旗舰"),
    )),
    ProviderPreset("siliconflow", "SiliconFlow", "openai", "https://api.siliconflow.cn/v1", (
        ("deepseek-ai/DeepSeek-V3", "通用"),
    )),
    ProviderPreset("minimax", "MiniMax", "openai", "https://api.minimaxi.com/v1", (
        ("MiniMax-M2.5", "通用"),
        ("MiniMax-M2.7", "更强"),
    )),
    ProviderPreset("hunyuan", "腾讯混元", "openai", "https://api.hunyuan.cloud.tencent.com/v1", (
        ("hunyuan-turbo", "通用"),
    )),
    ProviderPreset("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1", (
        ("anthropic/claude-sonnet-5", "Claude 5"),
        ("openai/gpt-4o-mini", "便宜"),
    )),
)


def preset_by_key(key: str) -> ProviderPreset | None:
    for preset in PROVIDER_PRESETS:
        if preset.key == key:
            return preset
    return None


def infer_preset_key(base_url: str) -> str:
    """按 Base URL 反查预设（旧版 config.json 没有 provider_preset 字段）。

    URL 不一致就返回空串（=「自定义」），不做模型名的模糊猜测。
    """
    target = (base_url or "").strip().rstrip("/")
    if not target:
        return ""
    for preset in PROVIDER_PRESETS:
        if preset.base_url.rstrip("/") == target:
            return preset.key
    return ""

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
    provider_preset: str = ""  # ProviderPreset.key；"" = 自定义

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
        config = cls(
            api_mode=api_mode if api_mode in ("openai", "anthropic") else "openai",
            api_key=str(data.get("api_key", "")),
            base_url=str(data.get("base_url", "")),
            model=str(data.get("model", "")),
            theme_mode=theme_mode,
            sidebar_width=int(data.get("sidebar_width", 240)),
            provider_preset=str(data.get("provider_preset", "")),
        )
        # 旧版没存过预设（或预设已改名）：按 Base URL 反查一次，设置界面就不会
        # 每次都显示成「自定义」。
        if config.provider_preset and preset_by_key(config.provider_preset) is None:
            config.provider_preset = ""
        if not config.provider_preset:
            config.provider_preset = infer_preset_key(config.base_url)
        return config

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
