# agent-tally

[![PyPI version](https://img.shields.io/pypi/v/agent-tally.svg)](https://pypi.org/project/agent-tally/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://pypi.org/project/agent-tally/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/thakoreh/agent-tally?style=social)](https://github.com/thakoreh/agent-tally)

**Real-time cost tracker for AI coding agents.** Wrap any CLI agent, see a live cost ticker while it runs, and enforce budgets with an automatic kill switch.

## Install

```bash
pip install agent-tally
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
