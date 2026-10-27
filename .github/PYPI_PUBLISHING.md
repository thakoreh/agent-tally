# Manual PyPI publishing

The existing `agent-tally` project trusts only the GitHub workflow
`thakoreh/agent-tally/.github/workflows/publish-pypi.yml` with environment `pypi`.
The environment permits only the `main` branch. The workflow has no push,
pull request, tag, or release event trigger; publication is manual.

The current allowlist contains only `v0.14.0`. Source commit, wheel and sdist
names, metadata and SHA-256 digests are fixed in the verifier. It downloads
the already tested public release files and does not rebuild them. An existing
PyPI version with different or incomplete files causes failure; matching files
cause a safe no-op. Inspect registry state before retrying an uncertain upload.

```text
gh workflow run publish-pypi.yml --repo thakoreh/agent-tally --ref main -f release_tag=v0.14.0
```

The verification job has read-only repository access. Only the upload job has
`id-token: write`; it rechecks both hashes and invokes the pinned official PyPA
publishing action. It executes no package code and uses no stored API token.
All third-party actions are pinned to full reviewed commit hashes.

For a future release, test its immutable files first, then review a PR updating
the tag/source/hash allowlist. Keep the same package, repository, workflow and
environment mapping. Do not broaden permissions or overwrite a released version.
After any upload, compare PyPI file hashes and verify fresh no-cache installs.
