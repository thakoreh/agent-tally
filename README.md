# agent-tally

Track what you spend across every AI coding agent. One CLI, all agents.

## Why?

People are burning tokens blind. Claude Code, Codex, Gemini CLI, OpenClaw, NeMoCLAW, Cursor, Auggie, Goose — each has its own cost structure, its own logging, its own way of showing (or hiding) what you spent. Nobody wants to check 5 dashboards.

`agent-tally` sits in your shell and watches. It intercepts agent CLI sessions, parses token usage in real-time, normalizes everything to a common format, and shows you exactly what you spent — per task, per agent, per day.

## Features

- **Universal** — Works with Claude Code, Codex, Gemini CLI, OpenClaw, NeMoCLAW, Cursor, Auggie, Goose CLI, and any agent that runs in your terminal
- **Zero config** — Auto-detects which agent you're running
- **Real-time** — See costs accumulate as the agent works
- **Shell-level** — No API hooks, no agent modifications, no plugins needed
- **Normalized** — Different agents, one cost format
- **Reports** — Daily, weekly, per-task, per-agent breakdowns
- **Estimates** — Configurable pricing per model (YAML)
- **Export** — JSON, CSV, or pretty terminal tables

## Install

```bash
# npm
npm install -g agent-tally

# Or with pip
pip install agent-tally
```

## Usage

### Wrap any agent command
```bash
# Instead of: claude "fix the auth bug"
agent-tally claude "fix the auth bug"

# Instead of: codex exec "add tests"
agent-tally codex exec "add tests"

# Works with any agent
agent-tally openclaw run "deploy to prod"
agent-tally nemoclaw "optimize the pipeline"
```

### Check your spending
```bash
# Today's summary
agent-tally summary

# By agent
agent-tally summary --by-agent

# By task
agent-tally summary --by-task

# This week
agent-tally summary --since "7 days ago"

# Export
agent-tally export --format json > costs.json
```

### Configure pricing
```bash
# Edit pricing config
agent-tally config edit

# Or set manually
agent-tally config set claude-sonnet-4 input 3.00 output 15.00
agent-tally config set gpt-5.2-codex input 2.50 output 10.00
```

## How It Works

1. `agent-tally` wraps your agent CLI command
2. Captures stdout/stderr in real-time
3. Parses agent-specific token usage patterns (each agent logs differently)
4. Normalizes to: `{agent, model, task, tokens_in, tokens_out, estimated_cost, timestamp}`
5. Appends to local SQLite DB (`~/.agent-tally/db.sqlite`)
6. Reports on demand

## Supported Agents

| Agent | Detection | Token Parsing |
|-------|-----------|---------------|
| Claude Code | ✅ | ✅ |
| Codex CLI | ✅ | ✅ |
| Gemini CLI | ✅ | ✅ |
| OpenClaw | ✅ | ✅ |
| NeMoCLAW | ✅ | ✅ |
| Cursor | ✅ | 🔜 |
| Auggie | ✅ | 🔜 |
| Goose CLI | ✅ | 🔜 |
| Any CLI | ✅ (generic) | 🔜 |

## License

MIT
