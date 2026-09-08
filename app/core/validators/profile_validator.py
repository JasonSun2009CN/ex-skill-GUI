import re
import json
from dataclasses import dataclass
from typing import Optional


REQUIRED_SECTIONS = [
    "Executive Summary",
    "Core Personality Metrics",
    "Communication Style",
    "Emotional Profile",
    "Tonal Characteristics by Context",
    "Mentality & Psychology",
    "Thematic Preferences",
    "Response Latency & Engagement Dynamics",
    "Idioms, Recurring Phrases & Linguistic Quirks",
    "Relationship Dynamics & Temporal Evolution",
    "Memory Moments & Significant Events",
    "Annotated Sample Excerpts",
    "Deep Interpretation & Synthesis",
    "Simulation Guidance",
    "Machine-Readable Profile",
    "Limitations & Disclaimer",
]

REQUIRED_FRONTMATTER_KEYS = [
    "schema_version",
    "profile_type",
    "subject_alias",
    "subject_role",
    "generated_at",
    "primary_language",
    "confidence",
    "status",
]

REQUIRED_JSON_KEYS = [
    "schema_version",
    "subject",
    "confidence",
    "status",
    "personality_metrics",
    "communication_style",
    "communication_metrics",
    "emotional_profile",
    "tones",
    "mentality",
    "themes",
    "response_latency",
    "linguistic_features",
    "relationship_dynamics",
    "temporal_evolution",
    "memory_moments",
    "sample_excerpts",
    "interpretation",
    "simulation_guidance",
    "limitations",
]


@dataclass
class ValidationError:
    severity: str
    code: str
    message: str


def validate_profile(md_content: str) -> list[ValidationError]:
    errors: list[ValidationError] = []

    if not md_content or not md_content.strip():
        return [ValidationError("error", "EMPTY", "Profile content is empty")]

    _validate_frontmatter(md_content, errors)
    _validate_sections(md_content, errors)
    _validate_json_block(md_content, errors)

    return errors


def _validate_frontmatter(content: str, errors: list[ValidationError]) -> None:
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        errors.append(ValidationError("error", "NO_FRONTMATTER", "Missing YAML frontmatter"))
        return
    fm = match.group(1)
    for key in REQUIRED_FRONTMATTER_KEYS:
        if not re.search(rf"^\s*{key}\s*:", fm, re.MULTILINE):
            errors.append(ValidationError(
                "warning", "MISSING_FM_KEY", f"Missing frontmatter key: {key}"
            ))


def _validate_sections(content: str, errors: list[ValidationError]) -> None:
    for section in REQUIRED_SECTIONS:
        if not re.search(rf"^#+\s+.*{re.escape(section)}", content, re.MULTILINE):
            errors.append(ValidationError(
                "warning", "MISSING_SECTION", f"Missing section: {section}"
            ))


def _validate_json_block(content: str, errors: list[ValidationError]) -> None:
    match = re.search(r"```json\s*\n(.*?)\n```", content, re.DOTALL)
    if not match:
        errors.append(ValidationError("error", "NO_JSON", "Missing Machine-Readable Profile JSON block"))
        return
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        errors.append(ValidationError("error", "INVALID_JSON", f"JSON parse error: {e}"))
        return
    for key in REQUIRED_JSON_KEYS:
        if key not in data:
            errors.append(ValidationError(
                "warning", "MISSING_JSON_KEY", f"Missing JSON key: {key}"
            ))
