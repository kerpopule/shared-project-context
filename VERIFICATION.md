# Verification and support boundaries

## Release checks

The v0.1.0 release is qualified with the following reproducible checks:

- `python3 -m unittest discover -s tests -v`: 20 tests, including cross-interface state, revisions/retries, decision supersession, concurrent receipts, expiring ownership, dirty edits and linked worktrees, future-schema refusal, bounded reference reads, directory escape denial, managed configuration preservation, runtime upgrades and uninstall data retention.
- `ruff check shared_context tests tools bootstrap.py` and `ruff format --check shared_context tests tools bootstrap.py`.
- `python3 tools/verify_native.py`: disposable-home registration/readback using the installed Claude Code and Codex CLIs, native Hermes plugin discovery and per-turn callback, idempotent install and data retention after uninstall. Requires the actual client executables and an installed Hermes development runtime; not part of portable CI.
- `python3 tools/probe_codex.py`: the official Codex app-server discovers the shared MCP tools, reads a synthetic project and writes a decision that supersedes the previous one. This is an actual native client transport test, **not a model inference turn**.
- Build both sdist and wheel; inspect the member lists for private/config/state files; install the wheel into an isolated environment, away from the source checkout, and exercise shared state and setup.
- Scan the publishable source and Git history for accidental credentials before publication. Inspect the source archive and verify uploaded release asset checksums after publication.
- Hosted CI exercises portable tests on Linux/macOS with Python 3.9, 3.11 and 3.13, plus wheel build/install smoke. The badge/run results, rather than this document, establish the status of a specific Git commit.

## What this does not prove

Passing native configuration/transport checks does not prove that every model will follow the protocol, every desktop UI reconnects automatically, a currently running Telegram gateway loaded a new plugin, or an unconfigured cloud session can reach the local store. No such universal guarantee is made. Installed configuration must be loaded by its owning client runtime.

The local setup qualification uses a single trusted account and synthetic projects. It does not test a remote authentication service, multi-user tenant isolation, production migrations, customer data, model inference budgets or credential handling. Those are not supplied features.

Update retention is verified through an installed-runtime upgrade fixture, not a guarantee about all future vendor changes. Explicit unsupported/disabled/disconnected states and bounded/incomplete scans remain meaningful outcomes.

## Maintainer workstation caveat

Controlled fixture tests verify preservation of pre-existing settings. A repeat installation on the maintainer workstation also passed six preservation categories and all doctor checks. The initial workstation installation comparison flagged semantic/configuration differences and instruction framing; the complete initial baseline values were not retained, so full first-install unrelated pre/post equality was not established. Do not generalize the later passing reinstall into proof of that earlier comparison. Private workstation configurations and receipts are not distributed.

## License and publication

The generic package is MIT licensed. The license does not include private notebooks, linked knowledge, client configuration, exports, credentials or a maintainer's live database. These stay outside release archives.
