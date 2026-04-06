"""Rich TUI dashboard for agent-tally."""

from __future__ import annotations
import time
import threading
from datetime import datetime, timedelta
from typing import Optional

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box

from .storage import Storage, Session
from .budget import BudgetManager, BudgetStatus


console = Console()


class Dashboard:
    """
    Live TUI dashboard showing:
    - Current session cost (updating in real-time)
    - Daily total vs budget
    - Recent sessions table
    - Top agents by cost
    """
    
    def __init__(
        self,
        storage: Optional[Storage] = None,
        budget_manager: Optional[BudgetManager] = None,
        refresh_rate: float = 1.0,
    ):
        self.storage = storage or Storage()
        self.budget_manager = budget_manager or BudgetManager()
        self.refresh_rate = refresh_rate
        
        self._running = False
        self._current_session_cost = 0.0
        self._current_session_id: Optional[str] = None
    
    def set_current_session(self, session_id: str, cost: float) -> None:
        """Update current session cost for real-time display."""
        self._current_session_id = session_id
        self._current_session_cost = cost
    
    def run(self, duration: Optional[float] = None) -> None:
        """
        Run the dashboard.
        If duration is set, run for that many seconds then exit.
        Otherwise, run until Ctrl+C.
        """
        self._running = True
        start_time = time.time()
        
        try:
            with Live(
                self._render(),
                console=console,
                refresh_per_second=1 / self.refresh_rate,
            ) as live:
                while self._running:
                    if duration and (time.time() - start_time) >= duration:
                        break
                    time.sleep(self.refresh_rate)
                    live.update(self._render())
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
    
    def stop(self) -> None:
        """Stop the dashboard."""
        self._running = False
    
    def _render(self) -> Group:
        """Render the full dashboard."""
        return Group(
            self._render_header(),
            self._render_budget_panel(),
            self._render_current_session(),
            self._render_recent_sessions(),
            self._render_top_agents(),
            self._render_footer(),
        )
    
    def _render_header(self) -> Panel:
        """Render header panel."""
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        title = Text()
        title.append("📊 agent-tally Dashboard", style="bold cyan")
        title.append(f"  •  {time_str}", style="dim")
        
        return Panel(title, box=box.ROUNDED, border_style="cyan")
    
    def _render_budget_panel(self) -> Panel:
        """Render budget status panel."""
        config = self.budget_manager.config
        daily_total = self._get_daily_total()
        
        content = []
        
        # Daily budget
        if config.daily_limit:
            pct = (daily_total / config.daily_limit) * 100 if config.daily_limit > 0 else 0
            remaining = config.daily_limit - daily_total
            
            # Progress bar
            bar_width = 30
            filled = int(bar_width * min(pct / 100, 1.0))
            empty = bar_width - filled
            
            if pct >= 100:
                bar_color = "red"
                bar_char = "█"
            elif pct >= 95:
                bar_color = "red"
                bar_char = "▓"
            elif pct >= 80:
                bar_color = "yellow"
                bar_char = "▒"
            else:
                bar_color = "green"
                bar_char = "░"
            
            bar = f"[{bar_color}]{bar_char * filled}[/{bar_color}]{'░' * empty}"
            
            content.append(
                f"Daily Budget: ${daily_total:.4f} / ${config.daily_limit:.2f}\n"
                f"{bar} {pct:.1f}%\n"
                f"Remaining: ${remaining:.4f}"
            )
        else:
            content.append(f"Daily Total: ${daily_total:.4f} (no limit set)")
        
        # Session budget
        if config.session_limit:
            if self._current_session_cost > 0:
                pct = (self._current_session_cost / config.session_limit) * 100
                remaining = config.session_limit - self._current_session_cost
                content.append(
                    f"\nSession Limit: ${self._current_session_cost:.4f} / ${config.session_limit:.2f} ({pct:.1f}%)"
                )
            else:
                content.append(f"\nSession Limit: ${config.session_limit:.2f}")
        
        return Panel(
            "\n".join(content),
            title="Budget Status",
            box=box.ROUNDED,
            border_style="yellow" if config.daily_limit else "dim",
        )
    
    def _render_current_session(self) -> Panel:
        """Render current session panel."""
        if not self._current_session_id:
            return Panel(
                "No active session",
                title="Current Session",
                box=box.ROUNDED,
                border_style="dim",
            )
        
        content = f"Session ID: {self._current_session_id}\n"
        content += f"Cost: ${self._current_session_cost:.4f}"
        
        return Panel(
            content,
            title="Current Session",
            box=box.ROUNDED,
            border_style="green",
        )
    
    def _render_recent_sessions(self) -> Table:
        """Render recent sessions table."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        sessions = self.storage.query(since=today, limit=10)
        
        table = Table(
            title="Recent Sessions (Today)",
            box=box.ROUNDED,
            show_lines=False,
            title_style="bold cyan",
        )
        
        table.add_column("Time", style="dim", width=10)
        table.add_column("Agent", style="bold")
        table.add_column("Model", style="cyan", width=20)
        table.add_column("Tokens", justify="right")
        table.add_column("Cost", justify="right", style="yellow")
        
        if not sessions:
            table.add_row("—", "No sessions today", "—", "—", "—")
            return table
        
        for s in sessions:
            time_str = s.started_at.strftime("%H:%M:%S") if s.started_at else "—"
            tokens_str = f"{s.tokens_in:,}→{s.tokens_out:,}" if s.tokens_in or s.tokens_out else "—"
            model_str = (s.model[:18] + "..") if s.model and len(s.model) > 20 else (s.model or "—")
            
            cost_style = "green" if s.cost < 1.0 else ("yellow" if s.cost < 5.0 else "red")
            
            table.add_row(
                time_str,
                s.agent,
                model_str,
                tokens_str,
                f"[{cost_style}]${s.cost:.4f}[/{cost_style}]",
            )
        
        return table
    
    def _render_top_agents(self) -> Table:
        """Render top agents by cost table."""
        week_ago = datetime.now() - timedelta(days=7)
        summaries = self.storage.summary(since=week_ago, group_by="agent")
        
        table = Table(
            title="Top Agents (Last 7 Days)",
            box=box.ROUNDED,
            show_lines=False,
            title_style="bold cyan",
        )
        
        table.add_column("Agent", style="bold")
        table.add_column("Sessions", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Total Cost", justify="right", style="yellow")
        
        if not summaries:
            table.add_row("—", "No data", "—", "—")
            return table
        
        for row in summaries[:5]:  # Top 5
            key = row.get("grp_key", "unknown") or "unknown"
            sessions = row.get("session_count", 0)
            tokens_in = row.get("total_tokens_in", 0) or 0
            tokens_out = row.get("total_tokens_out", 0) or 0
            cost = row.get("total_cost", 0.0) or 0.0
            
            tokens_str = f"{tokens_in + tokens_out:,}"
            cost_style = "green" if cost < 5.0 else ("yellow" if cost < 20.0 else "red")
            
            table.add_row(
                str(key),
                str(sessions),
                tokens_str,
                f"[{cost_style}]${cost:.4f}[/{cost_style}]",
            )
        
        return table
    
    def _render_footer(self) -> Panel:
        """Render footer with controls."""
        return Panel(
            "[dim]Press Ctrl+C to exit[/dim]",
            box=box.ROUNDED,
            border_style="dim",
        )
    
    def _get_daily_total(self) -> float:
        """Get total cost for today."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        sessions = self.storage.query(since=today, limit=10000)
        return sum(s.cost for s in sessions)


def run_dashboard(duration: Optional[float] = None) -> None:
    """Run the dashboard (entry point)."""
    dashboard = Dashboard()
    dashboard.run(duration=duration)
