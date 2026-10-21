# Verification and support boundaries

## v0.2.0 qualification

- The candidate unit suite exercises client-specific recipes, owned-setting preservation, modified-setting refusal, explicit reactivation, a fresh Gemini hook, scoped enumeration/resources/prompts, room identity isolation, stale room cursors, failed-status retention and safe SSH recipe generation. Exact executed counts and interpreter receipts belong to the candidate evidence, not the earlier release.
- `tools/verify_universal.py` exercises actual Gemini CLI 0.42.0, Pi 1.3.0 and OpenCode 1.19.3 configuration and connected MCP status in disposable homes. `tools/probe_pi.mjs` uses Pi's shipped `McpServerConnection` to recall a decision, write a checkpoint, discover resources and reject an ungranted project. This is not a model inference turn.
- `tools/verify_native.py` and `tools/probe_codex.py` pass again against the candidate: existing Claude/Codex/Hermes integration, a real Hermes hook and a real Codex app-server tool read/write remain functional.
- Scoped connections filter tools and enforce the same project grant across tools, resources and prompts. Read-only connections cannot call write tools; room bindings cannot spoof another bound actor/session.
- Room tests exercise the library contract, not a deployed room UI. No private room conversation was imported. No live Co-Agent/Hermes room runtime was changed.
- OpenClaw 2026.10.5 passed a later bounded native `mcp probe` in a disposable, uncredentialed home: three scoped read-only tools, resources and prompts discovered with no diagnostics. The earlier lifecycle refusal was not bypassed; the retry was admitted normally. No live Gateway or model turn was involved. Grok Bot and dots account/cloud connections remain unqualified and require an authorized deployment/connection path.
- Final local core suite: 35 tests; optional HTTP suite: two tests plus a real official-SDK loopback round trip. HTTP checks cover bearer authentication and its negative control, Host/Origin denials, oversized bodies, project isolation, read-only discovery and listener cleanup. See [HTTP.md](docs/HTTP.md).
- Local executed receipts are recorded in [QUALIFICATION-v0.2.md](docs/QUALIFICATION-v0.2.md). The v0.1.0 hosted CI receipts below are historical, not evidence that v0.2.0 CI ran. Consult the exact tagged commit's Actions run for hosted results.

See [the source-backed compatibility guide](docs/UNIVERSAL.md) and [room host contract](docs/ROOMS.md).

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
