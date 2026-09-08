# Test Report: imitation-skill-generator

## Scope

This directory contains the template used by the desktop application to turn a validated personality profile into a self-contained imitation skill.

## Static checks

- `SKILL.md` exists and describes the generator workflow.
- `templates/imitation-skill.template.md` exists and is non-empty.
- The generated skill is written under the repository's ignored `generated/skills/` directory.
- The generated skill bundles its source profile under `references/`.

## Runtime checks

The repository-level `smoke_test.py` verifies that:

1. A minimal valid profile passes `profile_validator`.
2. `ImitationGenerator` loads the bundled template.
3. A skill directory and bundled profile are generated in a temporary directory.
4. `skill_validator` reports no errors for the generated result.

Run it from the repository root:

```bash
python3 smoke_test.py
```

The test does not call an LLM and does not write personal data into the repository.
