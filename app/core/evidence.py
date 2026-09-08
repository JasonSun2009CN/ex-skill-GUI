from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# 喂给分析 LLM 的记录上限：保留最近一段（近期的说话风格最能代表当下）
MAX_TRANSCRIPT_CHARS = 60_000


@dataclass
class Turn:
    speaker: str
    timestamp: str | None
    content: str


@dataclass
class LabeledTurn:
    role: str       # "user" | "subject"
    content: str
    timestamp: str | None = None


_DATE_LINE_RE = re.compile(r"^\s*[-—=]{3,}\s*(?P<date>[\d\-/.]+\s*[\d:]*)?\s*[-—=]{3,}\s*$")
_TURN_RE = re.compile(r"^(?P<speaker>.+?)\s{2,}(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s*$")
_COLON_RE = re.compile(r"^(?P<speaker>[^\n:]{1,40}?)\s*[:：]\s*(?P<body>.*)$")


def _speaker_equals(a: str, b: str) -> bool:
    """别名匹配：允许彼此是对方子串（容忍微信/QQ 等结尾符号差异）。"""
    return bool(a and b and (a in b or b in a))


def parse_text(content: str) -> list[Turn]:
    """解析常见聊天导出格式：
    - 空行分隔的一整段 + 下一段的说话人行「名字  09:12」
    - 行内「名字：内容」
    - 纯「----- 日期 -----」分隔行（忽略）
    连续的说话人换行消息会并入同一条消息。
    """
    turns: list[Turn] = []
    cur_speaker: str | None = None
    cur_time: str | None = None
    cur_lines: list[str] = []

    def flush() -> None:
        nonlocal cur_speaker, cur_time, cur_lines
        if cur_speaker and cur_lines:
            text = "\n".join(cur_lines).strip()
            if text:
                turns.append(Turn(speaker=cur_speaker, timestamp=cur_time, content=text))
        cur_speaker, cur_time, cur_lines = None, None, []

    for raw in content.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if _DATE_LINE_RE.match(line):
            flush()
            continue
        m = _TURN_RE.match(line)
        if m:
            # 新的「名字  HH:MM」行：即使上一条没有空行分隔也视为新消息（贴近真实导出）
            flush()
            cur_speaker = m.group("speaker").strip()
            cur_time = m.group("time").strip()
            continue
        if cur_speaker is None:
            m2 = _COLON_RE.match(line)
            if m2 and len(m2.group("speaker").strip()) < 30:
                flush()
                cur_speaker = m2.group("speaker").strip()
                body = m2.group("body").strip()
                if body:
                    cur_lines.append(body)
                continue
        cur_lines.append(line)

    flush()
    return turns


def read_evidence_files(paths: list[str | Path]) -> tuple[str, list[Turn]]:
    """读取并拼接多个证据文件。返回 (原始拼接文本, 全部 turns)。
    每个文件之间用分隔注释标记，便于识别来源。"""
    raw_parts: list[str] = []
    all_turns: list[Turn] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if raw_parts:
            raw_parts.append("\n\n")  # 分隔
        raw_parts.append(f"===== {path.name} =====\n" + content)
        all_turns.extend(parse_text(content))
    return "\n".join(raw_parts), all_turns


def detect_speakers(turns: list[Turn]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in turns:
        counts[t.speaker] = counts.get(t.speaker, 0) + 1
    return counts


def suggest_me_alias(speaker_counts: dict[str, int], subject_alias: str) -> str:
    """在未知「我」的别名时推测：
    优先选择与 subject 明显不同的、发言最多者；
    含 我/me/I（作为自称）的名字优先。"""
    candidates = [s for s in speaker_counts if not _speaker_equals(s, subject_alias)]
    if not candidates:
        return ""
    # 自称型名字优先（去掉可能的前缀后精确含 me/我/I 且不是纯英文单词误判）
    def self_like(s: str) -> bool:
        low = s.lower().strip()
        return bool(re.search(r"(^|[^a-z])me([^a-z]|$)", low)) or low in ("我", "自己") or low.endswith("(我)") or "(我)" in s
    self_like_cands = [s for s in candidates if self_like(s)]
    pool = self_like_cands or candidates
    pool.sort(key=lambda s: (-speaker_counts[s], s))
    return pool[0]


def label_turns(turns: list[Turn], subject_alias: str, me_alias: str) -> tuple[list[LabeledTurn], list[str], int]:
    """标注为 subject / user；无法归入任一别名的第三方说话人被丢弃。
    返回 (标注后的 turns, 丢弃的说话人名, 丢弃条数)。"""
    labeled: list[LabeledTurn] = []
    dropped_speakers: list[str] = []
    dropped_count = 0
    for t in turns:
        if _speaker_equals(t.speaker, subject_alias):
            labeled.append(LabeledTurn("subject", t.content, t.timestamp))
        elif _speaker_equals(t.speaker, me_alias):
            labeled.append(LabeledTurn("user", t.content, t.timestamp))
        else:
            if t.speaker not in dropped_speakers:
                dropped_speakers.append(t.speaker)
            dropped_count += 1
    return labeled, dropped_speakers, dropped_count


def format_turns(labeled: list[LabeledTurn], max_chars: int = MAX_TRANSCRIPT_CHARS) -> tuple[str, bool]:
    """转成 [user]/[subject] 前缀文本；超过 max_chars 时保留「最近一段」并返回是否截断。
    从尾部向前累加，保证最新消息完整进入上下文。"""
    if not labeled:
        return "", False
    lines = [f"[{t.role}] {t.timestamp or ''}".rstrip() + "\n" + t.content for t in labeled]
    # 从后往前逐条装入
    kept_reversed: list[str] = []
    total = 0
    for line in reversed(lines):
        if kept_reversed and total + len(line) + 1 > max_chars:
            break
        kept_reversed.append(line)
        total += len(line) + 1
    kept = list(reversed(kept_reversed))
    truncated = total < sum(len(x) for x in lines)
    return "\n".join(kept), truncated
