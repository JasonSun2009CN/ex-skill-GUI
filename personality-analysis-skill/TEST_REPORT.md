# Test Report: personality-analysis-skill

## Scope

This directory contains the analysis instructions, rubric, and profile template used by the desktop application to generate a machine-readable personality profile.

## Static checks

- `SKILL.md` exists and describes the analysis workflow.
- `references/analysis_rubric.md` exists and is bundled with the skill.
- `templates/personality-profile.template.md` exists and defines the expected Markdown and JSON structure.
- The application loads these resources through `app/core/paths.py`; no external skill directory is required.

## Runtime checks

The repository-level `smoke_test.py` verifies that:

1. An empty profile is rejected.
2. A minimal profile with the required sections and JSON block passes `profile_validator`.
3. The profile data can be converted into an imitation subject snapshot.
4. The complete profile-to-skill flow succeeds without an LLM call.

Run it from the repository root:

```bash
python3 smoke_test.py
```

The real analysis workflow calls the provider configured in the GUI and writes the resulting profile under the ignored `generated/profiles/` directory.
