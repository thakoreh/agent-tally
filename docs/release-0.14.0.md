# agent-tally 0.14.0 release handoff

Prepared 2026-10-27 from the merged fresh-user fixes in PR #1. This is a
release candidate, not a claim that PyPI has been updated.

## Version selection

PyPI's JSON metadata currently lists only 0.5.0 and 0.9.0, with 0.9.0 current.
Repository history already assigns 0.10.0 through 0.14.0 to additional source
features. Both pyproject.toml and agent_tally.__version__ are 0.14.0. Publish
0.14.0 as the first package release containing those features and the audited
fixes; do not invent a 0.14.1 version before releasing 0.14.0.

## Publishing prerequisite

Publication is authorized, but no configured upload route was found: the only
GitHub Actions workflow runs tests/builds; repository Actions secret names are
empty; TWINE_USERNAME, TWINE_PASSWORD, PYPI_API_TOKEN and UV_PUBLISH_TOKEN are
absent from the checked process environment; no .pypirc is present. Secret
values and credential stores were not read. No upload was attempted, so there
is no uncertain or partially published release to retry.

The remaining step requires the maintainer either to upload the reviewed files
using their existing secure PyPI publishing setup, or separately approve and
configure a project-scoped publishing credential/trusted publisher. Do not paste
credentials into issues, PRs, release notes, shell history, or this document.

## Validation and immutable artifacts

The release branch runs the existing Ubuntu/Windows Python 3.9/3.13 test matrix.
Before handing off, build a wheel and sdist from the final commit, check their
metadata, and run the installed consumer test separately against each artifact:

```text
python -m build --outdir <release-artifact-directory>
python -m twine check <release-artifact-directory>/*
python -m pip install --no-cache-dir --force-reinstall <exact-wheel>
python scripts/consumer_smoke.py
python -m pip install --no-cache-dir --force-reinstall <exact-sdist>
python scripts/consumer_smoke.py
```

Keep those tested bytes with their SHA256SUMS and source commit in the draft
GitHub release. Upload each file to PyPI once; do not rebuild between testing
and uploading, overwrite an existing release, or hide errors with skip-existing.
Immediately before upload, recheck https://pypi.org/pypi/agent-tally/0.14.0/json.
If the outcome is uncertain, check registry metadata and SHA-256 digests before
any retry.

After upload, install `agent-tally==0.14.0` with `--no-cache-dir` into a new
environment outside the checkout. Verify the version, no-session JSON commands,
unknown-price semantics, invalid budgets, repeated/error runs, and synthetic
budget termination using scripts/consumer_smoke.py. Compare PyPI file hashes
with SHA256SUMS. Until that succeeds, registry installation is not verified.

## Known limits

See [cost accuracy](cost-accuracy.md) for first-match parsing, unverified local
pricing, legacy numeric-zero session/batch estimates, and direct-child-only
termination. No live provider billing or credentialed agent integration was
tested; the fixtures make no provider calls.
