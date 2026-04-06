"""Pretty terminal output for agent-tally."""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .storage import Storage, Session


console = Console()


def print_session_table(sessions: list[Session], title: Optional[str] = None) -> None:
    """Print a table of sessions."""
    table = Table(
        title=title or "Agent Sessions",
        box=box.ROUNDED,
        show_lines=False,
        title_style="bold cyan",
    )

    table.add_column("When", style="dim", width=16)
    table.add_column("Agent", style="bold")
    table.add_column("Model", style="cyan")
    table.add_column("Tokens In", justify="right", style="green")
    table.add_column("Tokens Out", justify="right", style="green")
    table.add_column("Cost", justify="right", style="bold yellow")
    table.add_column("Duration", justify="right")

    total_cost = 0.0
    total_in = 0
    total_out = 0

    for s in sessions:
        cost_str = f"${s.cost:.4f}" if s.cost > 0 else "-"
        tokens_in_str = f"{s.tokens_in:,}" if s.tokens_in else "-"
        tokens_out_str = f"{s.tokens_out:,}" if s.tokens_out else "-"
        model_str = s.model or "-"
        duration_str = f"{s.duration_sec:.1f}s" if s.duration_sec else "-"
        when_str = s.started_at.strftime("%b %d %H:%M") if s.started_at else "-"

        # Color code cost
        cost_style = "green"
        if s.cost > 1.0:
            cost_style = "yellow"
        if s.cost > 5.0:
            cost_style = "red"

        table.add_row(
            when_str,
            s.agent,
            model_str,
            tokens_in_str,
            tokens_out_str,
            f"[{cost_style}]{cost_str}[/{cost_style}]",
            duration_str,
        )

        total_cost += s.cost
        total_in += s.tokens_in
        total_out += s.tokens_out

    # Totals row
    table.add_row(
        "─" * 16,
        "─" * 10,
        "─" * 10,
        "─" * 10,
        "─" * 10,
        "─" * 10,
        "─" * 8,
    )
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"{len(sessions)} sessions",
        "",
        f"{total_in:,}",
        f"{total_out:,}",
        f"[bold yellow]${total_cost:.4f}[/bold yellow]",
        "",
    )

    console.print(table)


def print_summary_table(
    summaries: list[dict],
    group_by: str = "agent",
    title: Optional[str] = None,
) -> None:
    """Print a summary grouped by agent/model/task."""
    table = Table(
        title=title or f"Cost Summary (by {group_by})",
        box=box.ROUNDED,
        title_style="bold cyan",
    )

    key_label = group_by.capitalize()
    table.add_column(key_label, style="bold")
    table.add_column("Sessions", justify="right")
    table.add_column("Tokens In", justify="right", style="green")
    table.add_column("Tokens Out", justify="right", style="green")
    table.add_column("Cost", justify="right", style="bold yellow")
    table.add_column("Avg Duration", justify="right")

    total_cost = 0.0

    for row in summaries:
        key = row.get("grp_key", "unknown") or "unknown"
        sessions_count = row.get("session_count", 0)
        tokens_in = row.get("total_tokens_in", 0) or 0
        tokens_out = row.get("total_tokens_out", 0) or 0
        cost = row.get("total_cost", 0.0) or 0.0
        avg_dur = row.get("avg_duration", 0.0) or 0.0

        # Truncate long keys
        if len(str(key)) > 50:
            key = str(key)[:47] + "..."

        cost_str = f"${cost:.4f}" if cost > 0 else "-"
        tokens_in_str = f"{tokens_in:,}" if tokens_in else "-"
        tokens_out_str = f"{tokens_out:,}" if tokens_out else "-"
        avg_str = f"{avg_dur:.1f}s" if avg_dur else "-"

        cost_style = "green"
        if cost > 1.0:
            cost_style = "yellow"
        if cost > 5.0:
            cost_style = "red"

        table.add_row(
            str(key),
            str(sessions_count),
            tokens_in_str,
            tokens_out_str,
            f"[{cost_style}]{cost_str}[/{cost_style}]",
            avg_str,
        )

        total_cost += cost

    console.print(table)
    console.print(f"\n[bold]Total across all groups: ${total_cost:.4f}[/bold]\n")


def print_agents_list() -> None:
    """Print supported agents."""
    from .detector import AGENT_MAP

    table = Table(
        title="Supported Agents",
        box=box.ROUNDED,
        title_style="bold cyan",
    )
    table.add_column("Command", style="bold")
    table.add_column("Agent", style="cyan")
    table.add_column("Detection", style="green")

    for cmd, info in AGENT_MAP.items():
        table.add_row(cmd, info.display_name, "✅")

    # Generic fallback
    table.add_row("*", "Generic (any CLI)", "✅ (basic)")

    console.print(table)


def print_welcome() -> None:
    """Print welcome banner."""
    console.print(Panel(
        "[bold]agent-tally[/bold] — track costs across every AI coding agent\n"
        "[dim]Wrap any agent command: agent-tally claude 'fix the bug'[/dim]",
        box=box.ROUNDED,
        border_style="cyan",
    ))
