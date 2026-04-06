"""Shell wrapper that intercepts agent CLI commands."""

from __future__ import annotations
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional

from .detector import AgentInfo, detect_agent, parse_tokens, parse_model
from .pricing import PricingConfig
from .storage import Session, Storage


class AgentWrapper:
    """Wraps an agent CLI command and tracks its execution."""

    def __init__(
        self,
        args: list[str],
        pricing: Optional[PricingConfig] = None,
        storage: Optional[Storage] = None,
    ):
        self.args = args
        self.agent_info = detect_agent(args)
        self.pricing = pricing or PricingConfig()
        self.storage = storage or Storage()

        self.session = Session(
            agent=self.agent_info.display_name,
            started_at=datetime.now(),
        )
        self.session.id = self.storage.insert(self.session)

        self._captured_output: list[str] = []

    def run(self) -> int:
        """Run the wrapped agent command and track it."""
        print(f"\033[36m⏱ agent-tally: tracking {self.agent_info.display_name}\033[0m")

        start_time = time.time()

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

            process.wait()
            return_code = process.returncode

        except FileNotFoundError:
            print(f"\033[31m✗ agent-tally: command not found: {self.args[0]}\033[0m", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print(f"\n\033[33m⏸ agent-tally: interrupted by user\033[0m")
            return 130

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
        print(f"\033[{color}m──────────────────────────────────────\033[0m")
