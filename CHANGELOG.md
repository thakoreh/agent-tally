# Changelog

All notable changes to agent-tally will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-04-07

### Added
- 45 edge case tests covering pricing fuzzy matching, storage errors, budget validation, detector robustness, config edge cases, notifier resilience, and ticker edge cases (193 total tests)
- Input validation: negative budget limits now raise `ValueError`
- `MAX_TASK_PROMPT_LENGTH` (10,000 chars) — long prompts are silently truncated on insert

### Changed
- Malformed YAML config files now gracefully fall back to defaults (was already handled, now explicitly tested)
- Version bumped to 0.5.0 across `__init__.py`, `pyproject.toml`, and `setup.py`

## [0.4.0] - 2026-04-07

### Added
- `history` command — browse past session costs with `--agent`, `--since`, `--min-cost`, `--json` filters
- `completion` command — generate shell completions for bash/zsh/fish with `--install` flag
- 29 integration tests covering CLI, storage, pricing, detection, wrapper, and budget end-to-end
- `.gitignore` (was missing — __pycache__, eggs, build artifacts)
- `py.typed` marker for PEP 561 type hint support

### Changed
- Better error messages: distinct exit codes for command not found (127), permission denied (126), unexpected errors
- KeyboardInterrupt now saves partial session data before exiting
- Version now read from `__init__.__version__` instead of hardcoded in CLI
- Fixed version mismatch across pyproject.toml, setup.py, and __init__.py
- Cleaned up pyproject.toml for PyPI: proper `include` filter, project URLs

## [0.3.0] - 2026-04-07

### Added
- Config file support (`~/.agent-tally/config.yaml`) for default budgets, preferences, and model pricing overrides
- `agent-tally config init` — create a sample config file
- `agent-tally config show` — display current configuration
- `agent-tally config edit` — open config in your editor
- `agent-tally config pricing` — show pricing table for all models (was `config show`)
- `--json` flag on `summary` command for programmatic/scripting use
- 30+ model prices added across Anthropic, OpenAI, Google, xAI, DeepSeek, Meta, Mistral, Cohere, and Chinese providers
- Expanded token detection regex patterns:
  - JSON API style (`input_tokens`/`output_tokens`, `prompt_tokens`/`completion_tokens`)
  - Google API style (`totalTokenCount`/`candidatesTokenCount`)
  - Case-insensitive `Input tokens`/`Output tokens` variations
- 40 new tests covering config, detection, and pricing edge cases

### Changed
- `agent-tally config show` now shows unified config (use `config pricing` for model prices)
- Generic agent fallback now tries 6 regex patterns instead of 2

## [0.2.0] - 2026-03-22

### Added
- Rich TUI dashboard (`agent-tally dashboard`)
- Budget enforcement with kill switch
- Webhook alerts (Discord/Slack)
- CSV export
- `summary --by-agent/--by-model/--by-task` grouping
- PyPI package with proper setup.py

### Changed
- Renamed `track` command to `run` (old `track` still works as hidden alias)
- Improved real-time ticker display

## [0.1.0] - 2026-03-15

### Added
- Initial MVP: universal AI agent cost tracker
- Wraps any CLI agent with real-time cost ticker
- Token detection for Claude Code, Codex CLI, Gemini CLI, OpenClaw
- SQLite storage for session history
- Model pricing with fuzzy matching
- Basic CLI: `run`, `summary`, `export`, `agents`, `budget`
