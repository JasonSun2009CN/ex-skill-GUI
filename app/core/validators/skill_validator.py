import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationError:
    severity: str
    code: str
    message: str


def validate_skill_dir(skill_dir: Path) -> list[ValidationError]:
    errors: list[ValidationError] = []
    skill_dir = Path(skill_dir)

    if not skill_dir.exists():
        return [ValidationError("error", "NO_DIR", f"Skill directory not found: {skill_dir}")]

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        errors.append(ValidationError("error", "NO_SKILL_MD", "Missing SKILL.md"))
    else:
        content = skill_md.read_text(encoding="utf-8")
        _validate_skill_md(content, errors)

    refs_dir = skill_dir / "references"
    if not refs_dir.exists():
        errors.append(ValidationError("error", "NO_REFS", "Missing references/ directory"))
    else:
        profile_md = None
        for f in refs_dir.iterdir():
            if f.name.endswith("_personality_profile.md"):
                profile_md = f
                break
        if not profile_md:
            errors.append(ValidationError("error", "NO_PROFILE_REF", "Missing bundled *_personality_profile.md in references/"))

    return errors


def _validate_skill_md(content: str, errors: list[ValidationError]) -> None:
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        errors.append(ValidationError("error", "NO_FRONTMATTER", "SKILL.md missing YAML frontmatter"))
        return
    fm = match.group(1)
    if not re.search(r"^\s*name\s*:", fm, re.MULTILINE):
        errors.append(ValidationError("error", "NO_NAME", "Missing 'name' in frontmatter"))
    if not re.search(r"^\s*description\s*:", fm, re.MULTILINE):
        errors.append(ValidationError("error", "NO_DESC", "Missing 'description' in frontmatter"))

    if "references/" not in content:
        errors.append(ValidationError(
            "warning", "NO_REF_LINK", "SKILL.md does not reference the bundled profile via references/"
        ))
