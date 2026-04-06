"""Real-time cost ticker with ANSI escape codes."""

from __future__ import annotations
import sys
import time
import threading
from datetime import datetime
from typing import Optional, Callable

from .budget import BudgetStatus, BudgetManager


class CostTicker:
    """
    Real-time cost display that updates in-place using ANSI escape codes.
    Like a taxi meter for AI costs.
    """
    
    # ANSI codes
    CLEAR_LINE = "\033[2K"
    CURSOR_START = "\033[G"
    CURSOR_UP = "\033[A"
    CURSOR_DOWN = "\033[B"
    SAVE_CURSOR = "\033[s"
    RESTORE_CURSOR = "\033[u"
    
    # Colors
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    RESET = "\033[0m"
    
    def __init__(
        self,
        session_id: str,
        agent_name: str,
        budget_manager: Optional[BudgetManager] = None,
        get_daily_total: Optional[Callable[[], float]] = None,
    ):
        self.session_id = session_id
        self.agent_name = agent_name
        self.budget_manager = budget_manager
        self.get_daily_total = get_daily_total or (lambda: 0.0)
        
        self._cost = 0.0
        self._tokens_in = 0
        self._tokens_out = 0
        self._model: Optional[str] = None
        self._running = False
        self._start_time: Optional[datetime] = None
        self._last_status: Optional[BudgetStatus] = None
        self._ticker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def start(self) -> None:
        """Start the ticker display."""
        self._running = True
        self._start_time = datetime.now()
        # Print initial ticker line
        self._render()
    
    def stop(self) -> None:
        """Stop the ticker and print final line."""
        self._running = False
        # Move to new line so final output isn't overwritten
        sys.stdout.write("\n")
        sys.stdout.flush()
    
    def update(
        self,
        cost: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model: Optional[str] = None,
    ) -> BudgetStatus:
        """
        Update the ticker with new cost info.
        Returns budget status for kill switch checks.
        """
        with self._lock:
            self._cost = cost
            self._tokens_in = tokens_in
            self._tokens_out = tokens_out
            if model:
                self._model = model
        
        # Check budget
        status = self._check_budget()
        self._last_status = status
        
        # Re-render
        self._render()
        
        return status
    
    def _check_budget(self) -> BudgetStatus:
        """Check budget status."""
        if not self.budget_manager:
            return BudgetStatus(session_cost=self._cost, daily_cost=self.get_daily_total())
        
        return self.budget_manager.check(
            self.session_id,
            self._cost,
            self.get_daily_total(),
        )
    
    def _render(self) -> None:
        """Render the ticker line."""
        # Build ticker content
        parts = []
        
        # Agent name
        parts.append(f"{self.CYAN}⏱ {self.agent_name}{self.RESET}")
        
        # Duration
        if self._start_time:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            mins, secs = divmod(int(elapsed), 60)
            parts.append(f"{self.DIM}{mins:02d}:{secs:02d}{self.RESET}")
        
        # Cost (main number)
        cost_str = f"${self._cost:.4f}"
        if self._cost > 5.0:
            cost_color = self.RED
        elif self._cost > 1.0:
            cost_color = self.YELLOW
        else:
            cost_color = self.GREEN
        parts.append(f"{self.BOLD}{cost_color}{cost_str}{self.RESET}")
        
        # Tokens
        if self._tokens_in or self._tokens_out:
            parts.append(f"{self.DIM}{self._tokens_in:,}→ {self._tokens_out:,} tok{self.RESET}")
        
        # Model
        if self._model:
            parts.append(f"{self.DIM}{self._model}{self.RESET}")
        
        # Budget status
        if self._last_status:
            status_text = self._get_budget_text(self._last_status)
            if status_text:
                parts.append(status_text)
        
        # Clear line and print
        line = " │ ".join(parts)
        output = f"{self.CLEAR_LINE}{self.CURSOR_START}{line}"
        
        sys.stdout.write(output)
        sys.stdout.flush()
    
    def _get_budget_text(self, status: BudgetStatus) -> str:
        """Get budget display text with color coding."""
        texts = []
        
        if status.session_limit:
            pct = status.session_pct
            pct_str = f"{pct:.0f}%"
            if pct >= 100:
                texts.append(f"{self.RED}{self.BOLD}💥 {pct_str}{self.RESET}")
            elif pct >= 95:
                texts.append(f"{self.RED}⚠️ {pct_str}{self.RESET}")
            elif pct >= 80:
                texts.append(f"{self.YELLOW}⚡ {pct_str}{self.RESET}")
            else:
                texts.append(f"{self.GREEN}{pct_str}{self.RESET}")
        
        if status.daily_limit:
            pct = status.daily_pct
            pct_str = f"{pct:.0f}% day"
            if pct >= 100:
                texts.append(f"{self.RED}{self.BOLD}💀 {pct_str}{self.RESET}")
            elif pct >= 95:
                texts.append(f"{self.RED}⚠️ {pct_str}{self.RESET}")
            elif pct >= 80:
                texts.append(f"{self.YELLOW}⚡ {pct_str}{self.RESET}")
        
        return " │ ".join(texts) if texts else ""
    
    def print_warning(self, message: str, level: str = "yellow") -> None:
        """Print a warning message above the ticker."""
        color = self.YELLOW if level == "yellow" else self.RED
        # Move up, clear, print warning, then re-render ticker
        warning = f"{self.CURSOR_UP}{self.CLEAR_LINE}{self.CURSOR_START}{color}⚠️ {message}{self.RESET}\n"
        sys.stdout.write(warning)
        sys.stdout.flush()
        self._render()
    
    def print_kill_notice(self, reason: str) -> None:
        """Print kill notice and stop ticker."""
        msg = f"\n{self.RED}{self.BOLD}💀 BUDGET EXCEEDED: {reason}{self.RESET}\n"
        msg += f"{self.RED}Killing agent process...{self.RESET}\n"
        sys.stdout.write(msg)
        sys.stdout.flush()


class IncrementalCostTracker:
    """
    Tracks cost incrementally during agent execution.
    Estimates cost in real-time based on token patterns.
    """
    
    def __init__(
        self,
        ticker: CostTicker,
        budget_manager: Optional[BudgetManager] = None,
        pid: Optional[int] = None,
    ):
        self.ticker = ticker
        self.budget_manager = budget_manager
        self.pid = pid
        
        self._accumulated_cost = 0.0
        self._tokens_in = 0
        self._tokens_out = 0
        self._model: Optional[str] = None
        self._killed = False
    
    def update_tokens(self, tokens_in: int, tokens_out: int, model: str) -> None:
        """Update token counts and estimate cost."""
        self._tokens_in = tokens_in
        self._tokens_out = tokens_out
        self._model = model
        
        # Update ticker
        status = self.ticker.update(
            self._accumulated_cost,
            tokens_in,
            tokens_out,
            model,
        )
        
        # Check for kill
        if self.budget_manager and self.budget_manager.should_kill(status) and not self._killed:
            self._kill_agent(status)
    
    def set_cost(self, cost: float) -> None:
        """Set exact cost (called when final cost is known)."""
        self._accumulated_cost = cost
        status = self.ticker.update(
            cost,
            self._tokens_in,
            self._tokens_out,
            self._model,
        )
        
        if self.budget_manager and self.budget_manager.should_kill(status) and not self._killed:
            self._kill_agent(status)
    
    def _kill_agent(self, status: BudgetStatus) -> None:
        """Kill the agent process due to budget exceeded."""
        self._killed = True
        
        reason = "Session limit exceeded" if status.session_exceeded else "Daily limit exceeded"
        self.ticker.print_kill_notice(reason)
        
        if self.pid and self.budget_manager:
            self.budget_manager.kill_process(self.pid)
    
    @property
    def killed(self) -> bool:
        return self._killed
