"""Budget tracking and kill switch for agent-tally."""

from __future__ import annotations
import json
import os
import signal
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Callable

import yaml


DEFAULT_CONFIG_DIR = Path.home() / ".agent-tally"
DEFAULT_BUDGET_FILE = DEFAULT_CONFIG_DIR / "budget.yaml"


@dataclass
class BudgetConfig:
    """Budget limits configuration."""
    daily_limit: Optional[float] = None  # USD
    session_limit: Optional[float] = None  # USD
    warn_at_80: bool = True
    warn_at_95: bool = True
    kill_at_100: bool = True
    webhook_url: Optional[str] = None  # For notifications


@dataclass 
class BudgetStatus:
    """Current budget status."""
    session_cost: float = 0.0
    daily_cost: float = 0.0
    daily_limit: Optional[float] = None
    session_limit: Optional[float] = None
    session_pct: float = 0.0
    daily_pct: float = 0.0
    session_exceeded: bool = False
    daily_exceeded: bool = False
    session_warning: Optional[str] = None  # "80" or "95"
    daily_warning: Optional[str] = None


class BudgetManager:
    """Manages budget limits and tracking."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_BUDGET_FILE
        self.config = self._load_config()
        self._session_costs: dict[str, float] = {}  # session_id -> cost
        self._warned_sessions: set[str] = set()  # sessions that hit 80%
        _warned_95_sessions: set[str] = set()  # sessions that hit 95%
    
    def _load_config(self) -> BudgetConfig:
        """Load budget configuration from file."""
        if not self.config_path.exists():
            return BudgetConfig()
        
        with open(self.config_path) as f:
            data = yaml.safe_load(f) or {}
        
        return BudgetConfig(
            daily_limit=data.get("daily_limit"),
            session_limit=data.get("session_limit"),
            warn_at_80=data.get("warn_at_80", True),
            warn_at_95=data.get("warn_at_95", True),
            kill_at_100=data.get("kill_at_100", True),
            webhook_url=data.get("webhook_url"),
        )
    
    def save_config(self) -> None:
        """Save current config to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump({
                "daily_limit": self.config.daily_limit,
                "session_limit": self.config.session_limit,
                "warn_at_80": self.config.warn_at_80,
                "warn_at_95": self.config.warn_at_95,
                "kill_at_100": self.config.kill_at_100,
                "webhook_url": self.config.webhook_url,
            }, f, default_flow_style=False)
    
    def set_limits(self, daily: Optional[float] = None, session: Optional[float] = None) -> None:
        """Set budget limits.

        Raises:
            ValueError: If daily or session limit is negative.
        """
        if daily is not None:
            if daily < 0:
                raise ValueError(f"daily_limit cannot be negative, got {daily}")
            self.config.daily_limit = daily
        if session is not None:
            if session < 0:
                raise ValueError(f"session_limit cannot be negative, got {session}")
            self.config.session_limit = session
        self.save_config()
    
    def check(self, session_id: str, current_cost: float, daily_total: float) -> BudgetStatus:
        """Check budget status and return warnings/exceeded flags."""
        config = self.config
        
        # Calculate percentages
        session_pct = 0.0
        daily_pct = 0.0
        
        if config.session_limit and config.session_limit > 0:
            session_pct = (current_cost / config.session_limit) * 100
        
        if config.daily_limit and config.daily_limit > 0:
            daily_pct = (daily_total / config.daily_limit) * 100
        
        # Check warnings
        session_warning = None
        daily_warning = None
        
        if config.warn_at_80:
            if session_pct >= 80 and session_id not in self._warned_sessions:
                session_warning = "80"
                self._warned_sessions.add(session_id)
            if daily_pct >= 80:
                daily_warning = "80"
        
        if config.warn_at_95:
            if session_pct >= 95:
                session_warning = "95"
            if daily_pct >= 95:
                daily_warning = "95"
        
        # Check exceeded
        session_exceeded = config.kill_at_100 and config.session_limit and current_cost >= config.session_limit
        daily_exceeded = config.kill_at_100 and config.daily_limit and daily_total >= config.daily_limit
        
        return BudgetStatus(
            session_cost=current_cost,
            daily_cost=daily_total,
            daily_limit=config.daily_limit,
            session_limit=config.session_limit,
            session_pct=session_pct,
            daily_pct=daily_pct,
            session_exceeded=session_exceeded,
            daily_exceeded=daily_exceeded,
            session_warning=session_warning,
            daily_warning=daily_warning,
        )
    
    def should_kill(self, status: BudgetStatus) -> bool:
        """Return True if process should be killed due to budget exceeded."""
        return status.session_exceeded or status.daily_exceeded
    
    def get_warning_level(self, status: BudgetStatus) -> str:
        """Get warning level: 'none', 'yellow' (80%), 'red' (95%), 'kill' (100%)."""
        if status.session_exceeded or status.daily_exceeded:
            return "kill"
        if (status.session_warning == "95" or status.daily_warning == "95"):
            return "red"
        if (status.session_warning == "80" or status.daily_warning == "80"):
            return "yellow"
        return "none"
    
    @staticmethod
    def kill_process(pid: int) -> None:
        """Kill a process by PID."""
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Try SIGKILL if SIGTERM fails
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    
    def get_status_text(self, status: BudgetStatus) -> str:
        """Get human-readable status text."""
        lines = []
        
        if status.session_limit:
            pct = status.session_pct
            cost = status.session_cost
            limit = status.session_limit
            lines.append(f"Session: ${cost:.4f}/${limit:.2f} ({pct:.1f}%)")
        
        if status.daily_limit:
            pct = status.daily_pct
            cost = status.daily_cost
            limit = status.daily_limit
            lines.append(f"Daily: ${cost:.4f}/${limit:.2f} ({pct:.1f}%)")
        
        return " | ".join(lines) if lines else "No budget limits set"
