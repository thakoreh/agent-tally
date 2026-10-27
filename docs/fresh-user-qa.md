# Fresh-user QA, 2026-10-27

Baseline: `bf1d14b3391ebbe0393cc734afa63bccdc35ae5f` (`main`), source version
0.14.0, Python >=3.9. No AGENTS.md, .agents instructions, or existing CI workflow
was present. Reviewed README, pyproject.toml, setup.py, changelog, and cost-accuracy
docs before installing. setup.py duplicated stale 0.11.0 metadata; it now defers to
pyproject.toml.

Platform: Windows desktop, PowerShell, CPython 3.12.11 (uv environment), Git 2.52.0.
Clean clone in a new task workspace; all CLI subprocesses used synthetic fixtures,
an unrelated working directory, isolated HOME/USERPROFILE, and workspace TEMP/TMP.
No personal session data, provider credentials, paid APIs, or webhooks were used.

## Reproduced defects and fixes

| Reproduction | Before | Fixed behavior |
| --- | --- | --- |
| `agent-tally` | Welcome suggested invalid `agent-tally claude ...` | Suggests `agent-tally run claude ...` |
| `history/recent/top/export --json`, `hourly --json` on a fresh HOME | Successful plain text instead of JSON | Empty arrays or the documented empty hourly object |
| `budget set --daily -1` (also `nan`, `inf`) | Invalid limits persisted successfully | Exit 2, no partial changes to prior limits |
| `cost unknown-fixture-model 1000 500 --json` | Apparent zero dollar estimate | Explicit unknown pricing status, null estimate; text uses N/A |
| Start a wrapped process before usage detection | Ticker advertised $0.0000 | Ticker shows N/A until a priceable observation |
| Synthetic printed usage exceeds a configured budget | Kill target was wrapper's own PID; no final usage persistence | Targets child PID, saves detected usage, returns 137 |
| Historical daily cost 0.8 + current cost 0.3 with daily limit 1 | Daily check excluded current session | Daily budget is exceeded |
| Interrupt after synthetic usage | Child could survive and captured usage was discarded | Terminates/waits for child, saves detected usage, returns 130 |
| Missing executable | Session left without end time | Exit 127 with finalized session |
| `run --tag qa <child> --help --tag child` | Child flags could be consumed as wrapper options; tags and task were not stored | Options after child forwarded verbatim; task and wrapper tags persist |

The initial 14 new regression cases all failed before fixes. Additional cases
cover child flag forwarding, initial ticker uncertainty, and empty top output.
Existing tests were corrected to use portable Python child commands, workspace
temporary paths, current-day fixtures, and mocked process signaling instead of
arbitrary host PIDs.

## Commands and verification

```powershell
git clone https://github.com/thakoreh/agent-tally.git agent-tally
git switch -c fix/fresh-user-qa
uv venv .venv-published
uv pip install --python .venv-published/Scripts/python.exe --no-cache agent-tally
# After installing pip in that environment, verify the documented installer:
.venv-published/Scripts/python.exe -m pip install --no-cache-dir agent-tally
uv venv .venv-source
uv pip install --python .venv-source/Scripts/python.exe --no-cache '.[dev]' build
# All tests below set HOME/USERPROFILE to .qa-home and TEMP/TMP to .qa-temp.
.venv-source/Scripts/python.exe -m pytest -q
.venv-source/Scripts/python.exe examples/offline_cost_demo.py
uv build --out-dir dist
uv venv .venv-consumer
uv pip install --python .venv-consumer/Scripts/python.exe dist/agent_tally-0.14.0-py3-none-any.whl
.venv-consumer/Scripts/python.exe scripts/consumer_smoke.py
uv venv .venv-sdist
uv pip install --python .venv-sdist/Scripts/python.exe dist/agent_tally-0.14.0.tar.gz
.venv-sdist/Scripts/python.exe scripts/consumer_smoke.py
```

| Check | Result |
| --- | --- |
| Published installation and CLI help/version/missing argument | Pass, installed 0.9.0 |
| Published package empty JSON / invalid budget / unknown price / welcome | Fail, reproduced; release still contains these defects |
| Source pytest | 586 passed |
| Offline cost demo | Pass, 3 synthetic cases, no provider calls |
| Built wheel installed outside source | Pass; real budget kill, persistence, repeated sessions, child failure and missing executable |
| Built sdist installed outside source | Pass; same consumer script |
| Dashboard bounded empty render | Pass; no live provider usage |
| Python 3.9 and 3.13 on Ubuntu/Windows | Added CI matrix; use exact PR head checks for terminal results |
| Live provider integrations, billing accuracy, real agent sessions | Not run; no credentials/charges authorized |

## Release and coverage limits

The published package remains 0.9.0. These source fixes and newer 0.14.0 commands
are unavailable via `pip install agent-tally` until a maintainer reviews, merges,
and publishes a release. This QA does not authorize publication.

The parser still takes the first matched usage record, not a sum across requests.
It cannot enforce spend before usage is printed or account for every cache,
reasoning, retry, subscription, or provider-specific charge. Pricing is a local,
unverified table with fuzzy matching. Unknown session costs and batch estimates
retain legacy numeric zero; historical totals can understate actual spend.
Direct child termination does not guarantee termination of detached descendants
or cancellation of provider requests already sent. Use provider-side caps for
hard spending limits. Interrupted cleanup is regression tested with a deterministic
mock; actual OS budget termination is exercised against a synthetic subprocess.
