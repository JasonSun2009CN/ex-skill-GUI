from __future__ import annotations

from dataclasses import dataclass

import httpx

from ..config import Config

DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-sonnet-5"}

# ---------------------------------------------------------------------------
# 采样参数能力表
#
# 有些模型不接受自定义 temperature，服务端直接 400，例如月之暗面 Kimi：
#   invalid temperature: only 1 is allowed for this model
# 这些模型必须**整个省略** temperature —— 写死成某个值反而会再撞 400，因为同一个
# 模型的不同模式要求的固定值不同（kimi-k2.6 思考模式 1.0、非思考模式 0.6）。
# 省略永远安全：服务端用自己的默认值。
#
# 这张表只覆盖有官方文档背书的家族；其余模型靠 _relax() 按服务端报错现场纠正，
# 结论记入 _LEARNED，避免每一轮对话都先白白失败一次。
# ---------------------------------------------------------------------------
_NO_CUSTOM_TEMPERATURE_PREFIXES = (
    # 月之暗面：K2.5 之后 temperature 固定
    "kimi-k2", "kimi-k3",
    # Anthropic：Claude 5 代起移除采样参数
    "claude-opus-5", "claude-opus-4-7", "claude-opus-4-8",
    "claude-sonnet-5", "claude-fable-5", "claude-mythos-5",
    # OpenAI：推理模型只接受默认值
    "o1", "o3", "o4", "gpt-5",
)
_MAX_COMPLETION_TOKENS_PREFIXES = ("o1", "o3", "o4", "gpt-5")

# "端点|模型" -> 实测需要调整的字段（"temperature" = 不能传、"max_completion_tokens" =
# 要换参数名、"max_tokens" = 换回来）。进程级共享，跨 LLMClient 实例生效。
_LEARNED: dict[str, set[str]] = {}


def _bare_model(model: str) -> str:
    """去掉网关命名空间：openai/gpt-4o-mini → gpt-4o-mini。"""
    return model.strip().lower().rsplit("/", 1)[-1]


def _rejects_temperature(model: str) -> bool:
    return _bare_model(model).startswith(_NO_CUSTOM_TEMPERATURE_PREFIXES)


def _prefers_max_completion_tokens(model: str) -> bool:
    return _bare_model(model).startswith(_MAX_COMPLETION_TOKENS_PREFIXES)


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

    def _memory_key(self) -> str:
        return f"{self._endpoint('')}|{self._model()}"

    def _learned(self) -> set[str]:
        return _LEARNED.get(self._memory_key(), set())

    def _remember(self, flag: str) -> None:
        _LEARNED.setdefault(self._memory_key(), set()).add(flag)

    def _apply_sampling(self, body: dict, *, temperature: float, max_tokens: int, anthropic: bool) -> None:
        """按模型能力写入 temperature / token 上限字段。"""
        learned = self._learned()
        if "temperature" not in learned and not _rejects_temperature(self._model()):
            body["temperature"] = temperature
        if anthropic:
            body["max_tokens"] = max_tokens
        elif "max_completion_tokens" in learned or (
            "max_tokens" not in learned and _prefers_max_completion_tokens(self._model())
        ):
            body["max_completion_tokens"] = max_tokens
        else:
            body["max_tokens"] = max_tokens

    def _relax(self, body: dict, message: str) -> bool:
        """按服务端报错去掉它不认的参数，返回是否改动了 body。"""
        text = message.lower()
        if "response_format" in text and "response_format" in body:
            body.pop("response_format")
            self._remember("response_format")
            return True
        if "temperature" in text and "temperature" in body:
            body.pop("temperature")
            self._remember("temperature")
            return True
        # 注意顺序：报错里的 max_completion_tokens 也含 "max_tokens" 子串
        if "max_completion_tokens" in text and "max_completion_tokens" in body:
            body["max_tokens"] = body.pop("max_completion_tokens")
            self._remember("max_tokens")
            return True
        if "max_tokens" in text and "max_tokens" in body:
            body["max_completion_tokens"] = body.pop("max_tokens")
            self._remember("max_completion_tokens")
            return True
        return False

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
        }
        self._apply_sampling(body, temperature=temperature, max_tokens=max_tokens, anthropic=False)
        if json_mode and _text_has_json(messages):
            body["response_format"] = {"type": "json_object"}
        data = self._post_json_adaptive(url, headers, body)
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
        }
        self._apply_sampling(body, temperature=temperature, max_tokens=max_tokens, anthropic=True)
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        data = self._post_json_adaptive(url, headers, body)
        blocks = data.get("content") or []
        if blocks and isinstance(blocks[0], dict) and blocks[0].get("text") is not None:
            return blocks[0]["text"]
        raise LLMError("模型返回内容为空或响应结构异常。")

    def list_models(self) -> list[str]:
        """拉取服务端当前可用的模型 ID（设置里「获取模型列表」用）。"""
        if not self.cfg.api_key:
            raise LLMError("未设置 API Key，请先在「设置」里填写模型配置。")
        if self.cfg.api_mode == "anthropic":
            url = self._endpoint("/v1/models")
            headers = {"x-api-key": self.cfg.api_key, "anthropic-version": "2023-06-01"}
        else:
            url = self._endpoint("/models")
            headers = {"Authorization": f"Bearer {self.cfg.api_key}"}
        data = self._request_json("GET", url, headers)
        items = data.get("data")
        if not isinstance(items, list):
            raise LLMError("该服务没有返回模型列表（响应里缺少 data 字段）。")
        ids = sorted({str(i["id"]) for i in items if isinstance(i, dict) and i.get("id")})
        if not ids:
            raise LLMError("该服务返回的模型列表是空的。")
        return ids

    def _post_json_adaptive(self, url: str, headers: dict, body: dict) -> dict:
        """发请求；服务端抱怨某个参数不支持时，去掉它重试（最多 3 次调整）。"""
        adjustments = 3
        while True:
            try:
                return self._post_json(url, headers, body)
            except LLMError as e:
                adjustments -= 1
                if adjustments < 0 or not self._relax(body, str(e)):
                    raise

    def _post_json(self, url: str, headers: dict, body: dict) -> dict:
        return self._request_json("POST", url, headers, body)

    def _request_json(self, method: str, url: str, headers: dict, body: dict | None = None) -> dict:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(method, url, headers=headers, json=body)
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
