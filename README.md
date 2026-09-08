# ex-skill

> Language / 语言: [中文版](README.zh.md)

A local desktop application that turns relationship conversation evidence into a personality profile and a reusable imitation skill.

## Features

- Import `.txt`, `.md`, or `.log` conversation files from the desktop GUI.
- Label the user and the analysis subject, then preview parsed turns.
- Supports OrcaRouter, OpenRouter, OpenAI, Anthropic, Gemini, DeepSeek, Qwen, Kimi, GLM, Groq, Mistral, Together, SiliconFlow, and custom OpenAI-compatible services.
- Supports ex-partners, partners, dating subjects, friends, specific family relationships, colleagues, and custom relationships. Relationship boundaries are included in analysis and chat prompts.
- Validate the generated profile and create a self-contained imitation skill.
- Chat with the generated skill while keeping evidence and generated files on the local filesystem.

## Requirements

- Python 3.10 or newer
- macOS, Linux, or Windows
- An API key for one of the supported providers

Install dependencies with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate`.

## Run

```bash
python3 launch.py
```

## GUI workflow

1. Open **Settings** and choose a provider, API key, base URL, and model. OrcaRouter is listed first; enter its API URL according to its account documentation.
2. Open **Evidence**, add a conversation file, and enter the user and subject aliases.
3. Preview and confirm the parsed evidence.
4. In **Analysis**, generate the profile and imitation skill, or run the combined preparation flow.
5. In **Chat**, load the generated skill and start a conversation.

Configuration is stored in `~/.ex-skill/config.json` when possible. Evidence is stored in `evidence/`; generated profiles and skills are stored in `generated/`.

## Repository layout

```text
app/                              Python application code
app/core/                         Parsing, analysis, generation, validation, and LLM providers
app/ui/                           PySide6 desktop interface
personality-analysis-skill/       Analysis prompt, rubric, and profile template
imitation-skill-generator/       Imitation skill template and validation report
evidence/                         Local input evidence; ignored except for .gitkeep
generated/                        Local profiles and skills; ignored by Git
smoke_test.py                     Dependency-light engine smoke test
requirements.txt                  Runtime dependencies
launch.py                         The GUI launch script
```

## Validation

Run the built-in smoke test and syntax check:

```bash
python3 smoke_test.py
python3 -m compileall -q app smoke_test.py
```

The smoke test covers transcript parsing, profile validation, subject snapshot extraction, and imitation skill generation.

## Privacy

The GUI writes evidence and generated artifacts locally, but calls the provider configured in **Settings** when analysis or chat is requested. Do not commit private evidence, generated profiles, API keys, or other sensitive data. Use imitation features only with appropriate consent, and treat personality analysis as an interpretation rather than a diagnosis.
