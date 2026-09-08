from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Callable

from .validators.skill_validator import validate_skill_dir
from .paths import SKILLS_DIR, IMITATION_TEMPLATES_DIR


_GITHUB_ATTACH_RE = re.compile(r'^\s*\[[^\]]+\]\(https?://github\.com/[^)]+\)\s*$')

def _read_text(p: Path) -> str:
    if not p.exists():
        return ""
    raw = p.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    out = []
    started = False
    for line in lines:
        if not started and _GITHUB_ATTACH_RE.match(line):
            continue
        started = True
        out.append(line)
    return "\n".join(out)


def _extract_json(md: str) -> dict:
    m = re.search(r"```json\s*\n(.*?)\n```", md, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}


def _extract_fm(md: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", md, re.DOTALL)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"\s*([^:]+)\s*:\s*(.*)", line)
        if mm:
            out[mm.group(1).strip()] = mm.group(2).strip().strip('"')
    return out


def _build_subject_snapshot(profile_content: str) -> str:
    fm = _extract_fm(profile_content)
    data = _extract_json(profile_content)

    alias = fm.get("subject_alias") or (data.get("subject") or {}).get("alias") or "subject"
    role = fm.get("subject_role") or (data.get("subject") or {}).get("role") or "person"
    lang = (data.get("subject") or {}).get("primary_language") or "zh-CN"

    lines = [
        f"- **Alias**: {alias}",
        f"- **Role**: {role}",
        f"- **Primary Language**: {lang}",
    ]

    metrics = data.get("personality_metrics") or []
    if metrics:
        top = sorted(metrics, key=lambda m: m.get("weight", 0), reverse=True)[:6]
        lines.append("")
        lines.append("**Top Personality Metrics**")
        for m in top:
            dim = m.get("dimension", "?")
            score = m.get("score", 0)
            weight = m.get("weight", 0)
            ev = (m.get("evidence") or "").strip()
            lines.append(f"- {dim}: score={score} weight={weight}  # {ev[:60]}")

    tones = data.get("tones") or []
    if tones:
        lines.append("")
        lines.append("**Dominant Tones by Context**")
        for t in tones[:6]:
            ctx = t.get("context", "?")
            tone = t.get("tone", "?")
            intensity = t.get("intensity", 0)
            lines.append(f"- [{ctx}] {tone} (intensity={intensity})")

    feats = data.get("linguistic_features") or []
    if feats:
        lines.append("")
        lines.append("**Signature Phrases & Linguistic Quirks (top weight)**")
        top_f = sorted(feats, key=lambda f: f.get("weight", 0), reverse=True)[:8]
        for f in top_f:
            phrase = f.get("phrase") or f.get("quirk") or "?"
            w = f.get("weight", 0)
            typ = f.get("type", "")
            ex = (f.get("example") or "").strip()
            lines.append(f"- \"{phrase}\"  weight={w} type={typ}  # e.g. {ex[:60]}")

    sg = data.get("simulation_guidance") or {}
    for key, title in [("do", "Simulation Guidance — DO"), ("avoid", "Simulation Guidance — AVOID"), ("voice_rules", "Simulation Guidance — Voice Rules")]:
        items = sg.get(key) or []
        if items:
            lines.append("")
            lines.append(f"**{title}**")
            for it in items[:8]:
                lines.append(f"- {it}")

    return "\n".join(lines)


class ImitationGenerator:
    def __init__(self):
        self._template = _read_text(IMITATION_TEMPLATES_DIR / "templates" / "imitation-skill.template.md")

    def generate(
        self,
        profile_path: str | Path,
        progress_cb: Callable[[str], None] | None = None,
    ) -> Path:
        def log(s: str):
            if progress_cb:
                progress_cb(s)

        profile_path = Path(profile_path)
        if not profile_path.exists():
            raise FileNotFoundError(profile_path)

        profile_content = profile_path.read_text(encoding="utf-8")
        fm = _extract_fm(profile_content)
        alias = fm.get("subject_alias")
        if not alias:
            m = re.match(r"^(.+?)_personality_profile\.md$", profile_path.name)
            alias = m.group(1) if m else "subject"

        log(f"[生成] 读取画像: alias={alias}")
        snapshot = _build_subject_snapshot(profile_content)

        template = self._template
        if not template.strip():
            template = _FALLBACK_TEMPLATE

        skill_name = f"imitation-{alias.lower().replace('_', '-')}"
        skill_md = (
            template
            .replace("{{SKILL_NAME}}", skill_name)
            .replace("{{TITLE}}", f"Imitation Skill — {alias}")
            .replace("{{SUBJECT_ALIAS}}", alias)
            .replace("{{PROFILE_FILE}}", f"{alias}_personality_profile.md")
            .replace("{{SUBJECT_SNAPSHOT}}", snapshot)
            .replace(
                "{{DESCRIPTION}}",
                f"Faithfully reproduce {alias}'s voice and tone. Trigger when user wants to chat as {alias} or see how {alias} would reply.",
            )
        )

        skill_dir = SKILLS_DIR / skill_name
        refs_dir = skill_dir / "references"
        skill_dir.mkdir(parents=True, exist_ok=True)
        refs_dir.mkdir(exist_ok=True)

        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
        target_profile = refs_dir / f"{alias}_personality_profile.md"
        shutil.copyfile(profile_path, target_profile)
        log(f"[生成] 写入目录: {skill_dir}")

        errors = validate_skill_dir(skill_dir)
        fatal = [e for e in errors if e.severity == "error"]
        if fatal:
            raise RuntimeError(f"生成的 skill 校验失败: {fatal}")
        log(f"[完成] 校验通过 (warnings={len(errors) - len(fatal)})")
        return skill_dir


_FALLBACK_TEMPLATE = """---
name: "{{SKILL_NAME}}"
description: "{{DESCRIPTION}}"
---

# {{TITLE}}

Faithfully reproduce **{{SUBJECT_ALIAS}}**'s personality, emotional inflection, and way of speaking using
the granular personality profile in `references/{{PROFILE_FILE}}` as the single source of truth.

## 1. Purpose & Scope

- Pull the full profile at `references/{{PROFILE_FILE}}` and treat it as the authoritative dataset.
- Replicate tone, speech rhythm, vocabulary, sentence structure, idioms, and emotional inflection.
- Never invent traits, memories, or feelings unsupported by the profile.

## 3. Subject Snapshot (auto-extracted)

{{SUBJECT_SNAPSHOT}}

## 4. Replication Rules

- Match context-dependent tones from the profile.
- Mirror sentence structure, segmentation, vocabulary, and emoji habits from `communication_style`.
- Use exact recurring phrases and weights from `linguistic_features`.
- Follow `simulation_guidance.do`, `.avoid`, and `.voice_rules`.
- Keep reply length inside `communication_metrics.reply_length_by_input_type` upper bounds.

## 6. Workflow

1. Load `references/{{PROFILE_FILE}}` (both prose and JSON).
2. Determine conversation context and select matching tone.
3. Compose message(s) following replication rules and length budget.
4. Validate against profile and return only faithful output.

## 7. Guardrails

- Do not impersonate without consent; authorized simulation only.
- Do not fabricate memories or feelings absent from the profile.
- Preserve privacy; use subject alias and redact sensitive identifiers.
"""
