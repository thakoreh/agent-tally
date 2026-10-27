"""Show cost-estimation limits with synthetic output and no provider calls.

Run from an editable install: python examples/offline_cost_demo.py
All prices and usage below are fictional fixtures, not provider billing data.
"""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from agent_tally.budget import BudgetManager
from agent_tally.pricing import PricingConfig
from agent_tally.storage import Storage
from agent_tally.wrapper import AgentWrapper


CASES = (
    ("recognized_usage", "model: demo-model\ninput: 1000 output: 500\n", 1000, 500, 0.006),
    ("missing_usage", "model: demo-model\nTask finished.\n", 0, 0, 0.0),
    ("unpriced_model", "model: unpriced-fixture\ninput: 1000 output: 500\n", 1000, 500, 0.0),
)


def main() -> None:
    results = []
    with TemporaryDirectory(prefix="agent-tally-demo-") as temporary:
        directory = Path(temporary)
        pricing_file = directory / "pricing.yaml"
        # Fictional USD rates per million input/output tokens.
        pricing_file.write_text(
            "models:\n  demo-model:\n    input: 2.0\n    output: 8.0\n",
            encoding="utf-8",
        )
        pricing = PricingConfig(config_path=pricing_file)
        # Explicit paths keep the demo away from your normal ~/.agent-tally data.
        budget = BudgetManager(config_path=directory / "budget.yaml")
        storage = Storage(db_path=directory / "sessions.sqlite")
        try:
            for name, output, expected_in, expected_out, expected_cost in CASES:
                wrapper = AgentWrapper(
                    [sys.executable, "-c", "print(" + repr(output) + ")"],
                    pricing=pricing,
                    storage=storage,
                    budget_manager=budget,
                    enable_ticker=False,
                )
                # The real wrapper runs a local Python subprocess and parses its output.
                with redirect_stdout(StringIO()):
                    return_code = wrapper.run()
                session = next(row for row in storage.query() if row.id == wrapper.session.id)
                if (
                    return_code != 0
                    or session.tokens_in != expected_in
                    or session.tokens_out != expected_out
                    or abs(session.cost - expected_cost) > 1e-9
                ):
                    raise RuntimeError("Unexpected wrapper result for " + name)
                results.append({
                    "case": name,
                    "detected_model": session.model,
                    "tokens_in": session.tokens_in,
                    "tokens_out": session.tokens_out,
                    "estimated_usd": session.cost,
                })
        finally:
            storage.close()
    print(json.dumps({"synthetic_data": True, "provider_calls": 0, "results": results}, indent=2))


if __name__ == "__main__":
    main()
