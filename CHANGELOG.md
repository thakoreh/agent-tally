# Changelog

All notable changes to agent-tally will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.12.0] - 2026-05-26

### Fixed
- **agents --json command crash**: Fixed `TypeError` when using `--json` flag on `agents` command — was incorrectly accessing `AgentInfo` dataclass as dict (`info["display_name"]`) instead of using attribute access (`info.display_name`)
- **Alert.timestamp type annotation**: Changed from `datetime = None` to `Optional[datetime] = None` for correct type checking

### Added
- `__all__` exports in `agent_tally/__init__.py` for cleaner public API
- 15 new tests (test_v12.py) covering:
  - Agents command JSON output validation
  - Alert timestamp type handling
  - AgentInfo dataclass field validation
  - CLI version flag consistency
  - Summary/cost command edge cases

### Changed
- Version bumped to 0.12.0

## [0.11.0] - 2026-05-25

### Added
- **11 new frontier models (2026 Q2)** across all major providers:
  - Anthropic: claude-sonnet-5 ($3.50/$17.50), claude-haiku-5 ($1.20/$6.00)
  - OpenAI: gpt-6.5 ($5.00/$25.00), gpt-6.5-turbo ($20.00/$80.00)
  - Google: gemini-5.0-pro ($2.00/$15.00), gemini-5.0-flash ($0.20/$0.80)
  - xAI: grok-5-mini ($0.40/$1.50)
  - DeepSeek: deepseek-v5.5 ($0.22/$0.88), deepseek-r5 ($0.80/$3.20)
  - Meta: llama-5 ($0.30/$1.20)
  - Mistral: mistral-7b-v2 ($0.10/$0.30)
- **7 new token detection patterns** for 2026 structured output formats:
  - `token_usage: {input: N, output: M}` (structured key-value)
  - `usage_stats {input_tokens: N output_tokens: M}` (Go-style struct)
  - `tok_in=N tok_out=M` (compact key=value)
  - `num_tokens {input: N output: M}` (Rust-style)
  - `$0.42 (N in / M out)` (cost-prefixed)
  - `N → M tokens` (Unicode arrow format)
  - `"token_count": {"input": N, "output": M}` (NDJSON)
- **30+ new tests** (test_v11.py) covering frontier models, cost calculations, provider detection, and edge cases
- Total model count now 130+ across 19 providers

### Changed
- Version bumped to 0.11.0 across `__init__.py`, `pyproject.toml`, and `setup.py`
- Provider groups updated to include all new frontier models

## [0.10.0] - 2026-05-25

### Added
- **Three new LLM providers** with full pricing support:
  - **Snowflake**: arctic-instruct ($0.20/$0.60), arctic-embed ($0.05/$0.05)
  - **Writer**: palmyra-x5 ($1.00/$4.00), palmyra-x4 ($0.50/$2.00)
  - **Microsoft**: phi-4 ($0.15/$0.60), mai-ds-r1 ($0.20/$0.80)
- **New model variants across existing providers**:
  - Anthropic: claude-haiku-4 ($1.00/$5.00)
  - xAI: grok-3.5 ($0.60/$2.50), grok-mini ($0.15/$0.50)
  - DeepSeek: deepseek-v5.1 ($0.18/$0.70), deepseek-coder-v3 ($0.20/$0.80)
  - ZhipuAI: glm-7.1 ($0.16/$0.64)
  - Qwen: qwen-4 ($0.20/$0.80), qwen-4-coder ($0.15/$0.60)
- **Updated provider groups** — all new models registered in PROVIDER_GROUPS for detection
- **25 new tests** (test_v10.py) covering new providers, models, cost calculations, and provider detection
- **Version sync** — setup.py fixed from stale 0.7.0 to match 0.10.0

### Changed
- Version bumped to 0.10.0 across `__init__.py`, `pyproject.toml`, and `setup.py`
- Provider groups now include Snowflake, Writer, Microsoft entries
- Total model count: 120+ models across 18 providers

## [0.9.0] - 2026-04-09

### Added
- **Enhanced token detection patterns** — 12 new regex patterns for modern LLM output formats
- **Extended model pricing** — Added GLM-6, Qwen-3.5, DeepSeek-V2 models
- **Type hint consistency** — Added `from __future__ import annotations` to `__init__.py`
- **Improved error handling** — Better handling of large token counts, Unicode, empty outputs
- **Robust provider detection** — Case-insensitive prefix/contains matching with all providers tested

### Changed
- **Version bump to 0.9.0** — All modules updated
- **Test suite expanded** — 345 total tests (was 280)

### Fixed
- **Integration test version mismatch**
- **Empty string parsing**
- **Unicode resilience**
- **Edge case coverage**

## [0.8.0] - 2026-04-09

### Added
- **`detect_provider()` utility**
- **Session tagging**
- **`cost-batch` command**
- **`summary --by-hour`**
- **`agents --json`**
- **DB migration** for `tags` column
- **22 new tests**

## [0.7.0] - 2026-04-08

### Added
- **`cost` command** with `--json`
- **`session` command** with `--json`
- **Token rate** property
- **`budget show --json`**

## [0.6.0] - 2026-04-08

### Added
- **Cursor agent detection**
- **`top` command**
- **Markdown export**
- **Flexible `--since` parsing**
- 33 new tests (226 total)

## [0.5.0] - 2026-04-07

### Added
- 45 edge case tests (193 total)
- Input validation: negative budget limits raise `ValueError`
- `MAX_TASK_PROMPT_LENGTH` (10,000 chars)

## [0.4.0] - 2026-04-07

### Added
- `history` command
- `completion` command
- 29 integration tests
- `.gitignore`
- `py.typed` marker

## [0.3.0] - 2026-04-07

### Added
- Config file support (`~/.agent-tally/config.yaml`)
- `config init/show/edit/pricing` commands
- `--json` flag on `summary`
- 30+ model prices
- 40 new tests

## [0.2.0] - 2026-03-22

### Added
- Rich TUI dashboard
- Budget enforcement with kill switch
- Webhook alerts (Discord/Slack)
- CSV export
- `summary --by-agent/--by-model/--by-task` grouping
- PyPI package with proper setup.py

## [0.1.0] - 2026-03-15

### Added
- Initial MVP: universal AI agent cost tracker
- Wraps any CLI agent with real-time cost ticker
- Token detection for Claude Code, Codex CLI, Gemini CLI, OpenClaw
- SQLite storage for session history
- Model pricing with fuzzy matching
- Basic CLI: `run`, `summary`, `export`, `agents`, `budget`
