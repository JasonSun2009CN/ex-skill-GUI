import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ChatTurn:
    speaker: str
    timestamp: Optional[str]
    content: str


@dataclass
class EvidenceConfig:
    file_path: str
    subject_alias: str
    user_alias: str
    subject_role: str = "ex-partner"


@dataclass
class EvidenceSetup:
    file_path: str
    user_alias: str
    subject_alias: str
    subject_role: str = "ex-partner"
    turns: list[ChatTurn] = field(default_factory=list)


_DATE_LINE_RE = re.compile(r"^\s*[-—=]+\s*(?P<date>[\d\-/.]+\s*[\d:]*)?\s*[-—=]+\s*$")
_TURN_RE = re.compile(
    r"^(?P<speaker>.+?)\s{2,}(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s*$"
)


def parse_file(path: str | Path) -> list[ChatTurn]:
    path = Path(path)
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8", errors="replace")
    return parse_text(content)


def parse_text(content: str) -> list[ChatTurn]:
    lines = content.splitlines()
    turns: list[ChatTurn] = []
    current_speaker: Optional[str] = None
    current_time: Optional[str] = None
    current_lines: list[str] = []

    def flush():
        nonlocal current_speaker, current_time, current_lines
        if current_speaker is not None and current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                turns.append(ChatTurn(speaker=current_speaker, timestamp=current_time, content=text))
        current_speaker = None
        current_time = None
        current_lines = []

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            if current_lines:
                flush()
            continue
        if _DATE_LINE_RE.match(line):
            flush()
            continue
        m = _TURN_RE.match(line)
        if m:
            flush()
            current_speaker = m.group("speaker").strip()
            current_time = m.group("time").strip()
            continue
        if current_speaker is None:
            m2 = re.match(r"^(?P<speaker>[^\n:]{1,40}?)\s*[:：]\s*(?P<body>.*)$", line)
            if m2 and len(m2.group("speaker")) < 30:
                flush()
                current_speaker = m2.group("speaker").strip()
                body = m2.group("body").strip()
                if body:
                    current_lines.append(body)
                continue
        current_lines.append(line)

    flush()
    return turns


def label_turns(turns: list[ChatTurn], subject_alias: str, user_alias: str) -> list[ChatTurn]:
    labeled = []
    for t in turns:
        speaker = t.speaker
        if subject_alias and speaker and (subject_alias in speaker or speaker in subject_alias):
            role = "subject"
        elif user_alias and speaker and (user_alias in speaker or speaker in user_alias):
            role = "user"
        else:
            role = "user" if len(labeled) % 2 == 0 else "subject"
        labeled.append(ChatTurn(speaker=role, timestamp=t.timestamp, content=t.content))
    return labeled


def format_for_llm(turns: list[ChatTurn], max_chars: int = 120000) -> str:
    parts = []
    total = 0
    for t in turns:
        line = f"[{t.speaker}] {t.timestamp or ''}\n{t.content}\n"
        if total + len(line) > max_chars:
            break
        parts.append(line)
        total += len(line)
    return "".join(parts)
