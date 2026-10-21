# v0.2.0 qualification receipt

Executed 2026-10-21 using synthetic projects and disposable client homes. This is a maintainer self-review and executed QA receipt, not an independent audit or model-compliance certification.

## Passed locally

- 35 core unittest cases, including client configuration preservation/tamper refusal, update retention, explicit reactivation, custom OpenCode configuration precedence, project/identity isolation, room cursors, failure status, leases and Git worktrees.
- Two optional HTTP contract tests and a real loopback official-MCP-SDK client round trip. Verified authentication denials and a deliberately disabled-auth negative control, Host/Origin denials, oversized-request rejection, project isolation, read-only tool listing, resources/prompts and listener closure.
- Real Claude Code/Codex configuration readbacks, actual Hermes plugin registration/hook execution, repeat setup and data-preserving uninstall. Codex app-server performed a synthetic MCP read/write without a model turn.
- Gemini CLI 0.42.0, Pi 1.3.0 and OpenCode 1.19.3 reported connected native MCP servers. Pi's shipped runtime recalled a decision, wrote a checkpoint read back by the core, discovered resources and rejected an ungranted project.
- OpenClaw 2026.10.5 native MCP probe discovered the three granted read-only tools, resources and prompts with no diagnostics. No live Gateway operation or model inference.
- Ruff lint/format, source and Git-history secret scans, distribution member inspection, and wheel installation away from the checkout. Installed-wheel setup, shared state, Gemini hook, doctor, connection recipe and data-preserving uninstall passed.
- Temporary HTTP/OpenClaw process leases were released. A separate owner's active resource was preserved, not treated as a leak from this qualification.

## Review repairs

Corrected SDK result-field names during HTTP qualification; verified case-insensitive bearer scheme parsing; refused custom OpenCode config precedence instead of shadowing it; made Hermes plugin metadata track the package version; updated archive inspection and optional HTTP CI definitions; reconciled security documentation with scoped/HTTP behavior.

## Limits

Grok Bot/dots recipes are researched configuration routes, not connected accounts. No hosted endpoint, OAuth service, cloud connector, customer connection, Windows installer, live Rooms application integration or automatic fleet rollout was qualified. RoomBinding is a tested library, not a shipped host feature. No model inference calls were made. Exact-head hosted CI results, if present, are separate from these local receipts.

Reproduce with the commands in VERIFICATION.md, docs/UNIVERSAL.md and docs/HTTP.md, plus tools/verify_openclaw.py, tools/verify_dist.py and tools/verify_wheel.py. Native tests require the named installed client versions; missing clients must not be counted as passes.
