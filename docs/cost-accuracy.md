# What an agent cost estimate can tell you

A low cost number is useful only when you know what was measured. agent-tally wraps a command, reads its printed output, extracts a model name and token counts, and applies a local pricing table. It does not read your provider's billing account.

## Reproduce it without an API key

From a clone of this repository, in a Python virtual environment:

```bash
python -m pip install -e .
python examples/offline_cost_demo.py
```

The [demo](../examples/offline_cost_demo.py) runs the real subprocess wrapper, parser, pricing calculation, and SQLite storage against three **synthetic** outputs. It makes no provider calls. Its configuration and database live in a temporary directory, away from your normal agent-tally data; the ticker and process kill switch are disabled for this demo.

| Synthetic case | Detected input/output tokens | Stored estimated USD |
| --- | --- | --- |
| Model and usage recognized | 1,000 / 500 | 0.006 |
| Model recognized, usage missing | 0 / 0 | 0.000 |
| Usage recognized, model has no price | 1,000 / 500 | 0.000 |

The first case uses **fictional** rates of $2 per million input tokens and $8 per million output tokens:

```text
(1,000 / 1,000,000 × 2) + (500 / 1,000,000 × 8) = $0.006
```

These are demo fixtures, not measured model usage, current provider prices, or a benchmark of one provider against another. The script checks the stored values and exits with an error if they differ from this example.

## Zero is not proof of zero spend

The two zero-valued rows mean different things. Missing token output leaves no usage for the estimator to price. An unpriced model can have detected usage while its cost remains zero. The terminal summary shows `N/A` when the final estimated cost is not positive; the stored numeric cost is still zero.

Before relying on an estimate:

1. Confirm that the wrapped CLI prints usage in a format the parser recognizes. Running a command successfully does not establish usage coverage.
2. Check the detected model and both input/output token counts against a redacted sample of the CLI's usage output.
3. Verify the applicable rates against your provider's billing documentation and override the local pricing table when needed. Name matching can fall back to a partial model-name match.
4. Compare a small real session with your provider's usage record. Cache discounts, reasoning tokens, retries, subscription terms, or other charges may need separate accounting.

The parser currently takes the first matching usage record from the captured output; it does not add up every event in a stream. Treat multi-request sessions and changing output formats as cases to verify explicitly. Budget checks depend on the usage the wrapper can detect. They are not a provider-enforced spending cap.

The ticker starts at `N/A (usage/pricing unknown)` until a recognized model and
usage can be priced. `agent-tally cost unknown-model 1000 500 --json` returns
`pricing_status: "unknown"` and `estimated_cost_usd: null`, rather than an apparent
free estimate. Numeric session storage and historical aggregate totals retain
their existing zero representation for unknown usage/pricing. Batch cost output
also retains that legacy numeric representation; verify every model price before
relying on batch totals.

Budget termination saves detected usage and returns 137; interruption saves the
captured partial usage and returns 130. Only the direct wrapped process is
terminated. Detached descendants, buffered usage, silent output, and requests
already sent to providers remain outside this guarantee. Use provider-side limits
when a hard spending cap is required.

## Help improve coverage

A useful [issue](https://github.com/thakoreh/agent-tally/issues) includes the agent CLI and version, model identifier, a minimal redacted usage-output sample, expected token counts, and the detected result. Include whether the sample is a per-request event or a cumulative session total.

Replace prompts, tokens, private paths, and account details with placeholders. A compact reproducible sample is more useful than a complete private session log.

Implementation references: [wrapper](../agent_tally/wrapper.py), [output parser](../agent_tally/detector.py), [pricing](../agent_tally/pricing.py), and [storage](../agent_tally/storage.py).
