# agent-tally

[![PyPI version](https://img.shields.io/pypi/v/agent-tally.svg)](https://pypi.org/project/agent-tally/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://pypi.org/project/agent-tally/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/thakoreh/agent-tally?style=social)](https://github.com/thakoreh/agent-tally)

**Real-time cost tracker for AI coding agents.** Wrap any CLI agent, see a live cost ticker while it runs, and enforce budgets with an automatic kill switch.

**New here?** Try the [offline cost demo](docs/cost-accuracy.md) without an API key. It shows a detected estimate, missing usage, and an unpriced model using synthetic fixtures. Read the accuracy limits before relying on reported costs or budgets.

## Install

```bash
pip install agent-tally
```

Python 3.9 or newer is required. Check `agent-tally --version`: PyPI currently
serves 0.9.0, while this checkout is 0.14.0. Source fixes and newer commands
remain unavailable through the published install until a maintainer releases them.
The [0.14.0 release handoff](docs/release-0.14.0.md) records the tested artifacts
and the remaining publishing step. After publication, upgrade with
`python -m pip install --upgrade agent-tally` and verify the installed version.
For source setup in a fresh virtual environment:

```bash
python -m venv .venv
# Activate .venv (Windows: .venv\Scripts\activate; macOS/Linux: source .venv/bin/activate)
python -m pip install -e ".[dev]"
python -m pytest
```

## Quick Start

```bash
# Track a Claude Code session
agent-tally run claude "refactor auth module"

# Set budgets
agent-tally budget set --daily 5.00 --session 1.00

# Watch costs live
agent-tally dashboard
```

With no tracked sessions, `history`, `recent`, `top`, and `export` return `[]`
in JSON mode. `hourly --json` returns an object containing an empty `hourly` list.
Running `agent-tally` alone displays onboarding help and does not discover past
agent sessions or require credentials.

Put wrapper options before the agent command: `agent-tally run --tag demo claude --help`.
Options after the command belong to the child. Missing commands return 127;
child failures preserve their exit code; interruption returns 130; budget termination
returns 137 and saves detected partial usage.

Costs are local estimates from printed usage and configured model prices. Missing
usage or prices display `N/A`; `cost --json` reports `estimated_cost_usd: null` and
`pricing_status: "unknown"` for an unpriced model. Stored session costs still use
numeric zero for unknown estimates, so totals can understate spend. Confirm usage
coverage and rates before using budgets. The wrapper terminates the direct child;
detached descendants and provider requests already sent may continue.

Output while your agent runs:

```
$ agent-tally run claude "fix the login bug"
⠋ Running claude...  $0.42 │ 2.1k tokens │ 14s elapsed
```

## Features

- **Live cost ticker** — dollar amount updates in real-time as the agent runs, like a taxi meter
- **Budget enforcement** — set daily and per-session limits; auto-kills the process at 100%, warns at 80% and 95%
- **Shell-level interception** — wraps subprocess calls. No API hooks, no SDK changes, no config files
- **Cross-agent** — works with Claude Code, Codex CLI, Gemini CLI, OpenClaw, Cursor, and any CLI tool
- **TUI dashboard** — `agent-tally dashboard` for a live overview of all tracked sessions
- **Webhook alerts** — get Discord or Slack notifications when you hit budget thresholds
- **Export** — dump cost history as JSON or CSV for your own analytics

## CLI Reference

| Command | Description |
|---|---|
| `agent-tally run <command> [args...]` | Wrap and track an agent |
| `agent-tally budget set --daily 5.00 --session 1.00` | Set budget limits |
| `agent-tally budget show` | Show current budget and usage |
| `agent-tally dashboard` | Live TUI cost dashboard |
| `agent-tally summary [--by-agent\|--by-model] [--since 7d]` | Usage summary |
| `agent-tally export [--format json\|csv]` | Export cost data |
| `agent-tally agents` | List supported agents |

## How It Works

```
┌─────────────────────────────────────────────────────┐
│                   agent-tally                        │
│                                                      │
│  ┌──────────┐   ┌──────────────┐   ┌─────────────┐ │
│  │  CLI run  │──▶│   Wrapper    │──▶│  Subprocess  │ │
│  │  command  │   │  intercepts  │   │  (agent CLI) │ │
│  └──────────┘   │  stdout/err  │   └──────┬───────┘ │
│                  └──────┬───────┘          │         │
│                         │                  │         │
│                         ▼                  │         │
│                  ┌──────────────┐          │         │
│                  │ Token parser │◀─────────┘         │
│                  │ counts tokens│  (reads agent      │
│                  │ from output  │   output stream)   │
│                  └──────┬───────┘                    │
│                         │                            │
│              ┌──────────┴──────────┐                 │
│              ▼                     ▼                 │
│     ┌──────────────┐    ┌────────────────┐          │
│     │  Live ticker │    │ Budget checker │          │
│     │  $X.XX ████  │    │ warn @ 80/95%  │          │
│     └──────────────┘    │ kill @ 100%    │          │
│                         └───────┬────────┘          │
│                                 ▼                    │
│                    ┌────────────────────┐            │
│                    │  Webhook alerts    │            │
│                    │  Discord / Slack   │            │
│                    └────────────────────┘            │
└─────────────────────────────────────────────────────┘
```

agent-tally wraps your agent command as a subprocess. It parses the agent's output stream to count tokens in real-time, calculates cost using model-specific pricing, and displays a live ticker. If spending hits your budget limit, it kills the process automatically.

## Supported Agents

| Agent | Status |
|---|---|
| Claude Code | ✅ Supported |
| Codex CLI | ✅ Supported |
| Gemini CLI | ✅ Supported |
| OpenClaw | ✅ Supported |
| Cursor | ✅ Supported |
| Any CLI agent | ✅ Generic support |

## Why agent-tally over tokscale?

| | agent-tally | tokscale |
|---|---|---|
| **Approach** | Active — wraps commands in real-time | Passive — reads session logs after the fact |
| **Live cost display** | ✅ Ticker updates as the agent runs | ❌ Post-hoc only |
| **Budget enforcement** | ✅ Kill switch at budget limit | ❌ No enforcement |
| **Kill switch** | ✅ Auto-terminates runaway agents | ❌ Not possible (after the fact) |
| **Setup** | Wrap your command, done | Parse exported logs |

tokscale is great for retroactive analysis. agent-tally is for when you want to **control spend while it's happening**.

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feat/my-feature`
3. Make changes and add tests
4. Run `pytest`
5. Open a PR

Bug reports and feature requests welcome in [Issues](https://github.com/thakoreh/agent-tally/issues).

## License

[MIT](LICENSE)
