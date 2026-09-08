from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

EVIDENCE_DIR = PROJECT_ROOT / "evidence"
GENERATED_DIR = PROJECT_ROOT / "generated"
PROFILES_DIR = GENERATED_DIR / "profiles"
SKILLS_DIR = GENERATED_DIR / "skills"

SKILL_TEMPLATES_DIR = PROJECT_ROOT / "personality-analysis-skill"
IMITATION_TEMPLATES_DIR = PROJECT_ROOT / "imitation-skill-generator"

def get_config_dir() -> Path:
    candidates = [
        Path.home() / ".ex-skill",
        PROJECT_ROOT / ".local_config",
    ]
    import tempfile
    for c in candidates:
        try:
            c.mkdir(parents=True, exist_ok=True)
            probe = c / ".write_test"
            probe.write_text("ok")
            probe.unlink()
            return c
        except Exception:
            continue
    fallback = Path(tempfile.mkdtemp(prefix="ex-skill-config-"))
    return fallback

CONFIG_PATH = get_config_dir() / "config.json"

for d in [EVIDENCE_DIR, GENERATED_DIR, PROFILES_DIR, SKILLS_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
