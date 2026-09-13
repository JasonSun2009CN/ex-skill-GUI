# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local-only PySide6 desktop app: import a chat log with one person → one LLM call produces a
structured "personality profile" (人格画像) → chat with that simulated persona. All state lives on
disk under `~/.ex-skill` (overridable). The codebase, comments, UI strings and commit messages are
in Chinese; identifier names are English.

`README.md` is the user-facing source of truth for install, usage, and Qt troubleshooting — read it
before rewriting any of that narrative here.

## Commands

```bash
./.venv/bin/python launch.py        # run the GUI (bootstraps into .venv; see launch.py)
./.venv/bin/python smoke_test.py    # headless engine tests; exit 0 = pass (no GUI, no network)

# One test group only — smoke_test.py has no pytest; it's hand-rolled check() groups
./.venv/bin/python -c "import smoke_test as s; s.test_models(); print(s._failures or 'ok')"
#   groups: test_config, test_models, test_evidence, test_store, test_analyzer,
#           test_llm_client, test_pipeline_and_chat

EX_SKILL_LIVE=1 ./.venv/bin/python smoke_test.py   # opt-in real-LLM probe (uses saved config)

./.venv/bin/python -m compileall -q app/           # fastest syntax gate
```

`./.venv/bin/python <script>` is preferred over `source .venv/bin/activate`: it is immune to stale
`VIRTUAL_ENV`/`PATH` leftovers, which are a recurring source of confusing Qt errors in this project.

There is no linter/formatter config (no pyproject/ruff/flake8). Packaging is PyInstaller via
`.github/workflows/build.yml` → `scripts/package.py` (macOS `.app`, Windows `.exe`, Linux binary).
CI runs `smoke_test.py` on macOS/Linux only.

## Architecture

Hard split: **`app/core/` is the engine and must never import Qt** (it is headless and testable);
**`app/ui/` is PySide6**. `app/core/llm/` is also Qt-free.

### Creating a persona (`app/core/pipeline.py`)

```
preview(draft)                 # evidence parsing only, no LLM; raises PipelineError on bad input
  → evidence.read_evidence_files → parse_text → detect_speakers → suggest_me_alias
                                 → label_turns → format_turns   (capped 60k chars, keeps newest)
  → persona_analyzer.analyze(llm, meta, chat_text)             # up to 3 attempts
  → persona_store.create_role(meta, raw_evidence)              # evidence.txt, history.jsonl
  → persona_store.save_persona(role_id, persona)               # persona.json, status → ready
```

`build_role` returns the role **re-read from disk**, not the in-memory `RoleMeta`. Only the two
speaker lines you and the other person are kept; third parties are dropped with a warning.

### A chat turn (`app/core/chat_session.py`)

`ChatSession(llm, meta, persona)` builds the system prompt once and loads the last 40 history
records. `send(text)` appends the user line to memory + `history.jsonl`, calls the LLM
(`temperature=0.85`), appends the reply. `_sendable()` = `[system] + history[-40:]`.
Blank input short-circuits to `""` without a network call. `reset_context()` clears only memory.

### Exception types are UI strings

`PipelineError`, `AnalyzeError`, `LLMError` each carry a **ready-to-display Chinese message**; the UI
shows `str(e)` verbatim. When adding error paths, write the user-facing Chinese message in the
exception — do not add a translation layer, and do not let a generic `Exception` reach the UI.

### LLM client (`app/core/llm/client.py`)

One class, two shapes selected by `Config.api_mode`: `"openai"` (`/chat/completions`, Bearer) and
`"anthropic"` (`/v1/messages`, `x-api-key`, system messages hoisted to a top-level `system` field).
`chat(messages, *, temperature, max_tokens, json_mode)`, `probe()` (never raises; used by Settings'
"测试连接") and `list_models()` (Settings' "获取模型列表"; **not** every gateway implements
`GET /models`). JSON extraction/repair lives in `persona_analyzer.py` (code-fence stripping + brace
matching), not here.

**Sampling parameters are model-dependent.** Some models reject a custom `temperature` outright
with a 400 — Kimi (`invalid temperature: only 1 is allowed for this model`), Claude 5-family,
OpenAI reasoning models. `_apply_sampling()` consults `_NO_CUSTOM_TEMPERATURE_PREFIXES` and
**omits** the field for those; never pin it to a fixed value, since one model can require different
values per mode (kimi-k2.6 wants 1.0 thinking / 0.6 non-thinking). For models the table doesn't
know, `_post_json_adaptive()` retries after `_relax()` strips whatever the server complained about
(`response_format`, `temperature`, `max_tokens` ↔ `max_completion_tokens`) — bounded at 3
adjustments, and the verdict is cached in the process-level `_LEARNED` dict so later calls skip the
failed attempt. This is the *only* retry in the client; there is no backoff/retry-on-5xx loop.

### Storage (`app/core/persona_store.py`, `paths.py`)

```
<data_root>/                     # $EX_SKILL_DATA_DIR or ~/.ex-skill
  config.json
  roles.json                     # {"version": 1, "roles": [...]}
  roles/<role_id>/
    evidence.txt  persona.json  history.jsonl  avatar.png?
```

JSON writes go through `_write_json` (`.json.tmp` + `os.replace`) and are atomic; `history.jsonl` is
plain append-only and never rewritten. Corrupt JSON and bad lines are skipped, never fatal.
`paths.ensure_layout()` is called explicitly — there are **no filesystem side effects at import**.
Persona JSON keys are a frozen contract (Chinese values, English keys); `normalize_persona` is the
single place defaults get filled, and `RoleMeta` fields win over LLM output for
relationship/alias/display_name.

`config.json` carries `provider_preset` = a `ProviderPreset.key` from `config.PROVIDER_PRESETS`
(`app/core/config.py`), which is what makes the Settings dialog reopen on the same vendor instead of
"自定义". `Config.from_dict` is the single normalizer for it: a missing/unknown key falls back to
`infer_preset_key(base_url)`. Preset `models` tuples are display hints only — the first entry is the
default — so adding or reordering them is safe; renaming a `key` is not (it would orphan saved
configs, though they'd still degrade gracefully to a URL lookup).

### Threading (`app/ui/workers.py`)

`run_in_thread(fn, on_done, on_fail, on_progress=None, parent=None)` runs `fn(progress_emit)` on a
`QThread` and **guarantees the callbacks run on the GUI thread** (via a `Qt.QueuedConnection`
relay), so callbacks may touch widgets directly. The returned thread may be discarded.

Invariant: module-level `_ACTIVE_THREADS` plus `thread._worker` / `thread._relay` keep Python refs
alive. Dropping these causes the notorious "thread runs but the callback never fires" GC bug.

### Qt startup gate (`app/ui/qtgate.py`)

Runs **before** QtWidgets is imported, because a platform-plugin failure aborts the process with no
catchable Python exception. It (a) strips polluting Qt/DYLD env vars, (b) on macOS clears
`UF_HIDDEN` flags from the PySide6 plugin dir — `chflags -R nohidden …`, because Qt's `QDir` loader
skips hidden files, which makes a perfectly good PySide6 install report "Could not find the Qt
platform plugin" — and (c) probes Qt in a subprocess (`EX_SKILL_PROBE=1` suppresses recursion).

## UI conventions that have already caused bugs

- **Never call `setStyleSheet` on a container without a selector.** A selector-less declaration in
  Qt applies to the widget *and all its descendants*. This silently painted child
  `QPushButton`s with the container's background while `QPushButton { color: text_on_accent }`
  kept the text white — three buttons rendered as invisible white-on-white. Always scope:
  `w.setObjectName("roleDialogFooter")` + `w.setStyleSheet("#roleDialogFooter { … }")`, and set
  `Qt.WA_StyledBackground` so a plain `QWidget` paints its own background/border.
- **Do not poll for system appearance.** Reading it via the `defaults` subprocess costs ~30–90 ms
  and blocks the UI thread. `theme.system_is_dark()` uses Qt's native
  `styleHints().colorScheme()` (sub-ms); `MainWindow` subscribes to `colorSchemeChanged` instead of
  running a timer. Keep any remaining `subprocess` path as a fallback only.
- `app/ui/theme.py` owns `LIGHT`/`DARK` `Theme` dataclasses and the one global stylesheet
  (`apply_theme`); per-widget colour tweaks read from the `Theme` rather than hardcoding hex.

## Environment variables

| Var | Purpose |
|---|---|
| `EX_SKILL_DATA_DIR` | Override the data root (tests/portable mode). `smoke_test.py` sets it at import. |
| `EX_SKILL_LIVE=1` | Enable the real-LLM probe in `smoke_test.py`. Default tests are offline. |
| `EX_SKILL_PROBE=1` | Set by `qtgate` in its subprocess; suppresses the recursive probe. |
| `EX_SKILL_BOOTSTRAPPED` | Set by `launch.py` when re-execing into `.venv`; prevents bootstrapping loops. |

## Conventions

- Commits follow Conventional Commits (`feat:`, `fix:`) in Chinese or English.
- Length caps are deliberate tuning, not arbitrary: transcript 60k chars (newest kept), history
  window 40, reply `hard_cap_chars=120` / `hard_cap_messages=3`, `MAX_TOKENS` 80–800, analysis
  `temperature=0.3` / `max_tokens=6000`, chat `temperature=0.85`.
- `RELATIONSHIP_BOUNDARY` text is injected into **both** the analysis prompt and the chat prompt —
  two enforcement points, keep them in sync.
