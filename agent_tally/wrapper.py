"""Shell wrapper that intercepts agent CLI commands with real-time tracking."""

from __future__ import annotations
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional

from .detector import AgentInfo, detect_agent, parse_tokens, parse_model
from .pricing import PricingConfig
from .storage import Session, Storage
from .budget import BudgetManager, BudgetStatus
from .ticker import CostTicker, IncrementalCostTracker
from .notifier import Notifier


class AgentWrapper:
    """Wraps an agent CLI command and tracks its execution with real-time cost display."""

    def __init__(
        self,
        args: list[str],
        pricing: Optional[PricingConfig] = None,
        storage: Optional[Storage] = None,
        budget_manager: Optional[BudgetManager] = None,
        notifier: Optional[Notifier] = None,
        enable_ticker: bool = True,
    ):
        self.args = args
        self.agent_info = detect_agent(args)
        self.pricing = pricing or PricingConfig()
        self.storage = storage or Storage()
        self.budget_manager = budget_manager or BudgetManager()
        self.notifier = notifier or (Notifier(webhook_url=self.budget_manager.config.webhook_url) if self.budget_manager.config.webhook_url else None)
        self.enable_ticker = enable_ticker

        self.session = Session(
            agent=self.agent_info.display_name,
            started_at=datetime.now(),
        )
        self.session.id = self.storage.insert(self.session)

        self._captured_output: list[str] = []
        self._ticker: Optional[CostTicker] = None
        self._cost_tracker: Optional[IncrementalCostTracker] = None

    def run(self) -> int:
        """Run the wrapped agent command and track it with real-time updates."""
        # Start ticker
        if self.enable_ticker:
            self._ticker = CostTicker(
                session_id=str(self.session.id),
                agent_name=self.agent_info.display_name,
                budget_manager=self.budget_manager,
                get_daily_total=self._get_daily_total,
            )
            self._ticker.start()
            
            self._cost_tracker = IncrementalCostTracker(
                ticker=self._ticker,
                budget_manager=self.budget_manager,
                pid=os.getpid(),
            )

        start_time = time.time()
        return_code = 0

        try:
            process = subprocess.Popen(
                self.args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output in real-time
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                self._captured_output.append(line)
                
                # Try to parse incremental cost from output
                if self._cost_tracker:
                    self._update_incremental_cost("".join(self._captured_output))

            process.wait()
            return_code = process.returncode

        except FileNotFoundError:
            if self._ticker:
                print(f"\n\033[31m✗ agent-tally: command not found: {self.args[0]}\033[0m", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            if self._ticker:
                print(f"\n\033[33m⏸ agent-tally: interrupted by user\033[0m")
            return 130
        finally:
            if self._ticker:
                self._ticker.stop()

        # Check if killed by budget
        if self._cost_tracker and self._cost_tracker.killed:
            return 137  # Killed

        # Parse results
        end_time = time.time()
        duration = end_time - start_time

        full_output = "".join(self._captured_output)

        # Extract tokens
        tokens = parse_tokens(full_output, self.agent_info)
        if tokens:
            self.session.tokens_in = tokens.get("tokens_in", 0)
            self.session.tokens_out = tokens.get("tokens_out", 0)

        # Extract model
        model = parse_model(full_output, self.agent_info)
        if model:
            self.session.model = model

        # Calculate cost
        if self.session.model:
            self.session.cost = self.pricing.estimate(
                self.session.model,
                self.session.tokens_in,
                self.session.tokens_out,
            )

        # Store task prompt from args
        prompt_args = self.args[1:]
        self.session.task_prompt = " ".join(prompt_args)[:500] if prompt_args else ""

        # Update session
        self.session.ended_at = datetime.now()
        self.session.duration_sec = round(duration, 2)
        self.storage.update(self.session)

        # Print summary
        self._print_summary()

        return return_code

    def _update_incremental_cost(self, output: str) -> None:
        """Try to update cost incrementally from output."""
        if not self._cost_tracker:
            return
        
        # Parse tokens from output so far
        tokens = parse_tokens(output, self.agent_info)
        model = parse_model(output, self.agent_info)
        
        if tokens and model:
            # Estimate cost so far
            estimated_cost = self.pricing.estimate(
                model,
                tokens.get("tokens_in", 0),
                tokens.get("tokens_out", 0),
            )
            self._cost_tracker.update_tokens(
                tokens.get("tokens_in", 0),
                tokens.get("tokens_out", 0),
                model,
            )
            self._cost_tracker.set_cost(estimated_cost)
            
            # Send alerts if needed
            if self.notifier and self._ticker:
                status = self._ticker._last_status
                if status:
                    self.notifier.alert_from_status(status, str(self.session.id))

    def _print_summary(self) -> None:
        """Print a brief cost summary after the agent finishes."""
        cost_str = f"${self.session.cost:.4f}" if self.session.cost > 0 else "N/A"
        tokens_str = (
            f"{self.session.tokens_in:,} in / {self.session.tokens_out:,} out"
            if self.session.tokens_in or self.session.tokens_out
            else "tokens not detected"
        )

        color = "32"  # green
        if self.session.cost > 1.0:
            color = "33"  # yellow
        if self.session.cost > 5.0:
            color = "31"  # red

        print(f"\033[{color}m──────────────────────────────────────\033[0m")
        print(f"\033[{color}m⏱ agent-tally: {self.session.duration_sec:.1f}s | {tokens_str} | {cost_str}\033[0m")
        if self.session.model:
            print(f"\033[90m  model: {self.session.model}\033[0m")
        
        # Show budget status
        if self.budget_manager.config.daily_limit or self.budget_manager.config.session_limit:
            status = self.budget_manager.check(
                str(self.session.id),
                self.session.cost,
                self._get_daily_total(),
            )
            budget_text = self.budget_manager.get_status_text(status)
            print(f"\033[90m  budget: {budget_text}\033[0m")
        
        print(f"\033[{color}m──────────────────────────────────────\033[0m")

    def _get_daily_total(self) -> float:
        """Get total cost for today."""
        from datetime import date
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        sessions = self.storage.query(since=today, limit=10000)
        # Exclude current session to avoid double counting
        return sum(s.cost for s in sessions if s.id != self.session.id)
