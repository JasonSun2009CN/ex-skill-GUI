from __future__ import annotations

import json
from typing import Any, Callable

from .llm.client import ChatMessage, LLMClient
from .models import RoleMeta, normalize_persona, validate_persona_json
from .persona_prompts import analysis_system_prompt, analysis_user_prompt

MAX_ATTEMPTS = 3


class AnalyzeError(Exception):
    """画像分析失败（多次校验未通过等）。"""


def _extract_json_object(text: str) -> dict:
    """从模型输出里取第一个 JSON 对象（容忍围栏与前后杂音）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.lstrip("`")
        # 去掉可能的 json 标识行
        if text.lower().startswith("json"):
            text = text[4:]
        if text.startswith("\n"):
            text = text[1:]
    start = text.find("{")
    if start == -1:
        raise AnalyzeError("输出中没有找到 JSON 对象。")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                except ValueError as e:
                    raise AnalyzeError(f"JSON 解析失败：{e}") from None
                if isinstance(obj, dict):
                    return obj
                raise AnalyzeError("解析出的 JSON 不是对象。")
    raise AnalyzeError("JSON 对象不完整（未闭合）。")


def analyze(
    llm: LLMClient,
    meta: RoleMeta,
    chat_text: str,
    truncated: bool = False,
    progress_cb: Callable[[str], None] | None = None,
) -> dict:
    """一次（最多 3 次）LLM 调用生成画像 dict。失败抛 AnalyzeError/LLMError。"""
    def log(s: str) -> None:
        if progress_cb:
            progress_cb(s)

    system = analysis_system_prompt(meta)
    user = analysis_user_prompt(chat_text, truncated)

    last_raw = ""
    fatal: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        log(f"[画像] 第 {attempt}/{MAX_ATTEMPTS} 次生成中…")
        messages = [ChatMessage("system", system), ChatMessage("user", user)]
        if attempt > 1 and last_raw and fatal:
            messages.append(ChatMessage("assistant", last_raw))
            messages.append(
                ChatMessage(
                    "user",
                    "校验未通过，请修复后重新输出完整 JSON：\n- " + "\n- ".join(fatal),
                )
            )
        try:
            last_raw = llm.chat(
                messages,
                temperature=0.3,
                max_tokens=6000,
                json_mode=True,
            )
        except Exception as e:
            log(f"[错误] LLM 调用失败：{e}")
            raise
        try:
            obj = _extract_json_object(last_raw)
        except AnalyzeError as e:
            fatal = [str(e)]
            log(f"[画像] 第 {attempt} 次 JSON 解析失败：{e}")
            continue
        fatal = validate_persona_json(obj)
        if not fatal:
            persona = normalize_persona(obj, meta)
            log(f"[画像] 生成完成（confidence={persona['confidence']}）")
            return persona
        log(f"[画像] 第 {attempt} 次校验未通过：{'；'.join(fatal)}")
    else:
        raise AnalyzeError(f"{MAX_ATTEMPTS} 次尝试均未产出合法画像：{'；'.join(fatal)}")
