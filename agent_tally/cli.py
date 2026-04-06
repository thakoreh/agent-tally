"""agent-tally CLI — track costs across every AI coding agent."""

from __future__ import annotations
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import click

from .display import print_session_table, print_summary_table, print_agents_list, print_welcome
from .detector import AGENT_MAP
from .pricing import PricingConfig, DEFAULT_PRICING_FILE
from .storage import Storage
from .budget import BudgetManager, DEFAULT_BUDGET_FILE
from .dashboard import run_dashboard


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version")
@click.pass_context
def cli(ctx: click.Context, version: bool = False) -> None:
    """agent-tally — track costs across every AI coding agent in real-time."""
    if version:
        click.echo("agent-tally 0.2.0")
        return

    # If no subcommand, show welcome
    if ctx.invoked_subcommand is None:
        print_welcome()


# ═══════════════════════════════════════════════════════════════════════════
# RUN COMMAND (Primary entry point)
# ═══════════════════════════════════════════════════════════════════════════

@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("agent_args", nargs=-1, required=True)
def run(agent_args: tuple[str, ...]) -> None:
    """
    Wrap an agent command and track it with real-time cost display.
    
    Usage: agent-tally run <command> [args...]
    
    Examples:
        agent-tally run claude "fix the bug"
        agent-tally run codex --full-auto
        agent-tally run gemini "explain this code"
    """
    from .wrapper import AgentWrapper

    wrapper = AgentWrapper(list(agent_args))
    return_code = wrapper.run()
    sys.exit(return_code)


# Keep 'track' as alias for backwards compatibility
@cli.command(context_settings=dict(ignore_unknown_options=True), hidden=True)
@click.argument("agent_args", nargs=-1, required=False)
def track(agent_args: tuple[str, ...]) -> None:
    """Legacy alias for 'run'. Use 'run' instead."""
    if not agent_args:
        click.echo("Error: provide an agent command to wrap. E.g.: agent-tally run claude 'fix bugs'")
        sys.exit(1)

    from .wrapper import AgentWrapper

    wrapper = AgentWrapper(list(agent_args))
    return_code = wrapper.run()
    sys.exit(return_code)


# ═══════════════════════════════════════════════════════════════════════════
# BUDGET COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
def budget() -> None:
    """Manage budget limits and tracking."""
    pass


@budget.command(name="set")
@click.option("--daily", type=float, default=None, help="Daily budget limit (USD)")
@click.option("--session", "session_limit", type=float, default=None, help="Per-session budget limit (USD)")
@click.option("--webhook", type=str, default=None, help="Webhook URL for alerts (Discord/Slack)")
def budget_set(daily: Optional[float], session_limit: Optional[float], webhook: Optional[str]) -> None:
    """
    Set budget limits.
    
    Examples:
        agent-tally budget set --daily 5.00
        agent-tally budget set --daily 10.00 --session 2.00
        agent-tally budget set --webhook https://discord.com/api/webhooks/...
    """
    manager = BudgetManager()
    
    if daily is not None:
        manager.config.daily_limit = daily
    if session_limit is not None:
        manager.config.session_limit = session_limit
    if webhook is not None:
        manager.config.webhook_url = webhook
    
    manager.save_config()
    
    click.echo("Budget limits updated:")
    if manager.config.daily_limit:
        click.echo(f"  Daily limit: ${manager.config.daily_limit:.2f}")
    else:
        click.echo("  Daily limit: not set")
    
    if manager.config.session_limit:
        click.echo(f"  Session limit: ${manager.config.session_limit:.2f}")
    else:
        click.echo("  Session limit: not set")
    
    if manager.config.webhook_url:
        webhook_display = manager.config.webhook_url[:50] + "..." if len(manager.config.webhook_url) > 50 else manager.config.webhook_url
        click.echo(f"  Webhook: {webhook_display}")


@budget.command(name="show")
def budget_show() -> None:
    """Show current budget configuration and today's spending."""
    from rich.console import Console
    from rich.table import Table
    from rich import box
    
    manager = BudgetManager()
    storage = Storage()
    
    # Get today's total
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    sessions = storage.query(since=today, limit=10000)
    daily_total = sum(s.cost for s in sessions)
    
    console = Console()
    
    # Config table
    table = Table(title="Budget Configuration", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Setting", style="bold")
    table.add_column("Value", justify="right")
    
    table.add_row("Daily Limit", f"${manager.config.daily_limit:.2f}" if manager.config.daily_limit else "Not set")
    table.add_row("Session Limit", f"${manager.config.session_limit:.2f}" if manager.config.session_limit else "Not set")
    table.add_row("Kill at 100%", "Yes" if manager.config.kill_at_100 else "No")
    table.add_row("Warn at 80%", "Yes" if manager.config.warn_at_80 else "No")
    table.add_row("Warn at 95%", "Yes" if manager.config.warn_at_95 else "No")
    
    console.print(table)
    
    # Status
    console.print()
    status_table = Table(title="Today's Status", box=box.ROUNDED, title_style="bold yellow")
    status_table.add_column("Metric", style="bold")
    status_table.add_column("Value", justify="right")
    
    status_table.add_row("Sessions Today", str(len(sessions)))
    status_table.add_row("Total Spent", f"${daily_total:.4f}")
    
    if manager.config.daily_limit:
        remaining = manager.config.daily_limit - daily_total
        pct = (daily_total / manager.config.daily_limit) * 100 if manager.config.daily_limit > 0 else 0
        
        if pct >= 100:
            status_str = f"[red]${daily_total:.4f} / ${manager.config.daily_limit:.2f} ({pct:.1f}%)[/red]"
        elif pct >= 95:
            status_str = f"[red]${daily_total:.4f} / ${manager.config.daily_limit:.2f} ({pct:.1f}%)[/red]"
        elif pct >= 80:
            status_str = f"[yellow]${daily_total:.4f} / ${manager.config.daily_limit:.2f} ({pct:.1f}%)[/yellow]"
        else:
            status_str = f"[green]${daily_total:.4f} / ${manager.config.daily_limit:.2f} ({pct:.1f}%)[/green]"
        
        status_table.add_row("Budget Status", status_str)
        status_table.add_row("Remaining", f"${remaining:.4f}")
    
    console.print(status_table)
    storage.close()


@budget.command(name="clear")
def budget_clear() -> None:
    """Clear all budget limits."""
    manager = BudgetManager()
    manager.config.daily_limit = None
    manager.config.session_limit = None
    manager.config.webhook_url = None
    manager.save_config()
    click.echo("Budget limits cleared.")


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD COMMAND
# ═══════════════════════════════════════════════════════════════════════════

@cli.command()
def dashboard() -> None:
    """
    Launch the live TUI dashboard.
    
    Shows real-time cost tracking, budget status, recent sessions, and top agents.
    Press Ctrl+C to exit.
    """
    run_dashboard()


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY COMMAND
# ═══════════════════════════════════════════════════════════════════════════

@cli.command()
@click.option("--by-agent", "by_agent", is_flag=True, help="Group by agent")
@click.option("--by-model", "by_model", is_flag=True, help="Group by model")
@click.option("--by-task", "by_task", is_flag=True, help="Group by task")
@click.option("--since", "since", default="today", help="Time window: 'today', '7d', '30d', 'all', or ISO date")
@click.option("--limit", "limit", default=50, help="Max results")
def summary(by_agent: bool, by_model: bool, by_task: bool, since: str, limit: int) -> None:
    """Show cost summary."""
    storage = Storage()

    # Parse time window
    since_dt = _parse_since(since)

    if by_agent:
        group_by = "agent"
    elif by_model:
        group_by = "model"
    elif by_task:
        group_by = "task"
    else:
        group_by = "agent"

    # Get summary
    summaries = storage.summary(since=since_dt, group_by=group_by)
    if summaries:
        print_summary_table(summaries, group_by=group_by)
    else:
        click.echo("No sessions found for the given time range.")

    # Also show recent sessions
    sessions = storage.query(since=since_dt, limit=limit)
    if sessions:
        print_session_table(sessions, title="Recent Sessions")

    storage.close()


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT COMMAND
# ═══════════════════════════════════════════════════════════════════════════

@cli.command()
@click.option("--format", "format", type=click.Choice(["json", "csv"]), default="json", help="Export format")
@click.option("--since", "since", default="all", help="Time window")
@click.option("--output", "-o", "output", default=None, help="Output file (default: stdout)")
def export(format: str, since: str, output: Optional[str]) -> None:
    """Export session data."""
    import json
    import csv
    import io

    storage = Storage()
    since_dt = _parse_since(since) if since != "all" else None
    sessions = storage.query(since=since_dt, limit=10000)

    if not sessions:
        click.echo("No sessions to export.")
        return

    rows = []
    for s in sessions:
        rows.append({
            "id": s.id,
            "agent": s.agent,
            "model": s.model,
            "task_prompt": s.task_prompt,
            "tokens_in": s.tokens_in,
            "tokens_out": s.tokens_out,
            "cost": s.cost,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "duration_sec": s.duration_sec,
        })

    if format == "json":
        data = json.dumps(rows, indent=2)
    else:
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        data = buf.getvalue()

    if output:
        Path(output).write_text(data)
        click.echo(f"Exported {len(rows)} sessions to {output}")
    else:
        click.echo(data)

    storage.close()


# ═══════════════════════════════════════════════════════════════════════════
# AGENTS COMMAND
# ═══════════════════════════════════════════════════════════════════════════

@cli.command()
def agents() -> None:
    """List supported agents."""
    print_agents_list()


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

@cli.group()
def config() -> None:
    """Manage configuration."""
    pass


@config.command(name="edit")
def config_edit() -> None:
    """Open pricing config in your editor."""
    pricing = PricingConfig()
    # Ensure file exists
    if not pricing.config_path.exists():
        pricing._save()

    editor = subprocess.os.environ.get("EDITOR", "nano")
    subprocess.run([editor, str(pricing.config_path)])


@config.command(name="set")
@click.argument("model_name")
@click.argument("direction", type=click.Choice(["input", "output"]))
@click.argument("price", type=float)
def config_set(model_name: str, direction: str, price: float) -> None:
    """Set pricing for a model. E.g.: agent-tally config set claude-sonnet-4 input 3.00"""
    pricing = PricingConfig()
    existing = pricing.get(model_name)
    if direction == "input":
        pricing.set(model_name, price, existing.output)
    else:
        pricing.set(model_name, existing.input, price)
    click.echo(f"Set {model_name} {direction} = ${price:.2f}/M tokens")


@config.command(name="show")
def config_show() -> None:
    """Show current pricing configuration."""
    pricing = PricingConfig()
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()

    table = Table(title="Model Pricing", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("Model", style="bold")
    table.add_column("Input ($/M)", justify="right", style="green")
    table.add_column("Output ($/M)", justify="right", style="yellow")

    for name, p in sorted(pricing.all_models().items()):
        table.add_row(name, f"${p.input:.2f}", f"${p.output:.2f}")

    Console().print(table)


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _parse_since(since: str) -> Optional[datetime]:
    """Parse a time window string into a datetime."""
    now = datetime.now()

    if since == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif since == "yesterday":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif since == "7d":
        return now - timedelta(days=7)
    elif since == "30d":
        return now - timedelta(days=30)
    elif since == "90d":
        return now - timedelta(days=90)
    elif since == "all":
        return None
    else:
        # Try ISO format
        try:
            return datetime.fromisoformat(since)
        except ValueError:
            click.echo(f"Warning: couldn't parse '{since}', defaulting to today")
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
