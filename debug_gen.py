import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
from app.core.imitation_generator import ImitationGenerator, _FALLBACK_TEMPLATE, _read_text
from app.core.paths import IMITATION_TEMPLATES_DIR

print("template path:", IMITATION_TEMPLATES_DIR / "templates" / "imitation-skill.template.md")
content = _read_text(IMITATION_TEMPLATES_DIR / "templates" / "imitation-skill.template.md")
print(f"template read: {len(content)} chars, first 3 lines:")
for i, line in enumerate(content.splitlines()[:3]):
    print(f"  {i}: {line!r}")
print()
print("FALLBACK first 3 lines:")
for i, line in enumerate(_FALLBACK_TEMPLATE.splitlines()[:3]):
    print(f"  {i}: {line!r}")
print()

MINIMAL_VALID = """---
schema_version: "1.0"
profile_type: "personality-speech-analysis"
subject_alias: "Joanna"
subject_role: "ex-partner"
generated_at: "2024-01-01T00:00:00Z"
primary_language: "zh-CN"
confidence: 0.5
status: "complete"
---
# Personality & Speech Profile — Joanna
## 1. Executive Summary
x
"""
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    profile = tmp / "Joanna_personality_profile.md"
    profile.write_text(MINIMAL_VALID, encoding="utf-8")
    skills_dir = tmp / "skills"
    from app.core import imitation_generator
    original = imitation_generator.SKILLS_DIR
    imitation_generator.SKILLS_DIR = skills_dir
    try:
        gen = ImitationGenerator()
        dir_ = gen.generate(str(profile))
        print("generated:", dir_)
        for f in dir_.rglob("*"):
            print(" -", f.relative_to(tmp))
        md = (dir_ / "SKILL.md").read_text(encoding="utf-8")
        print(f"\nSKILL.md content (first 500 chars:")
        print(md[:500])
    finally:
        imitation_generator.SKILLS_DIR = original
