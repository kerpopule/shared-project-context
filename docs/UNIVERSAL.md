# Universal interoperability, without universal access

Status: v0.2.0 interoperability release. Source research and local runtime qualification dated 2026-10-21.

Shared Project Context is a small shared contract, not a vendor-specific memory backend. The same store can be reached through MCP tools, MCP resources, MCP prompts, the JSON CLI, and an in-process Python API. Clients do not need to share model providers, accounts, conversation formats or a modified application binary.

## What is implemented

- Installer adapters for Claude Code, Codex, Hermes, Gemini CLI, modern Pi and OpenCode.
- Non-mutating connection recipes for those clients plus OpenClaw, Cursor, VS Code, Claude Desktop, generic MCP clients, Grok Bot and OpenAI dots. Each recipe names its source and limitations. A recipe is not evidence that an account connected.
- Per-connection project, read-only and optional actor/session restrictions. Tool listing, calls, resource reads and prompts enforce the same restrictions.
- Standard MCP resources and a resume-project prompt, with protocol negotiation through 2025-11-25. Older supported MCP versions remain available.
- Gemini BeforeAgent context refresh, alongside the existing Claude prompt hook and Hermes native hook. Pi and OpenCode receive instructions and MCP tools; automatic per-turn native injection is not implemented for them.
- A bounded, vendor-neutral RoomBinding bridge. See [ROOMS.md](ROOMS.md).

The installer changes owned blocks and connection entries, not application source. Content-addressed runtimes and a stable launcher keep context outside vendor update directories. Upstream updates can still break an API: doctor and the native verification scripts detect specific regressions, not every possible future change.

## Local setup

Python 3.9+; local automatic installation is qualified on macOS. CI schedules Linux/macOS checks; consult the exact tagged commit's Actions result rather than inferring hosted results from local tests. Windows installation has not been qualified.

```sh
shared-context setup --clients gemini,pi,opencode
shared-context doctor
```

Gemini uses ~/.gemini/settings.json and GEMINI.md. Modern Pi uses ~/.pi/agent/mcp.json and AGENTS.md. OpenCode uses ~/.config/opencode/opencode.json and AGENTS.md. Supported environment-specific home/config locations are honored. Instructions and unrelated JSON settings are preserved. User-edited owned entries, duplicate JSON keys and non-JSON configuration cause refusal instead of silent repair. Existing OpenCode JSONC/custom config precedence needs the manual connection recipe rather than a new shadow config file. Do not edit client settings concurrently with setup; file-byte checks are not an atomic transaction with unrelated applications.

Automatic setup does not install a vendor CLI, connect an account, enable blanket tool approval or certify a model's behavior. Explicit uninstall keeps shared data. Reinstallation after uninstall requires setup --reactivate.

## Any other MCP client

```sh
shared-context connect --client generic --project my-project --read-only
shared-context connect --client openclaw --project my-project
shared-context connect --client vscode --project my-project --read-only
```

The command prints JSON and changes nothing. Select the configuration object for the chosen client. OpenCode's command is an array; Gemini/Pi use command plus args; VS Code uses servers; OpenClaw uses mcp.servers. These formats are deliberately not treated as interchangeable. Codex/Hermes recipes express the mapping; use each application's documented native config command/format rather than saving JSON into a TOML/YAML file.

For direct access without MCP:

```sh
shared-context call context '{"project":"my-project"}'
```

A minimal client contract is: inspect current context before work, honor workspace ownership, use expected revisions and unique receipt keys, record attributed outcomes, and distinguish proposed/failed/tested/merged/deployed states. A provider that cannot run tools or reach the store has manual context export at most, not automatic live continuity.

## Scope a connection

```sh
shared-context serve --project my-project --read-only
shared-context serve --project my-project --actor approved-host --session task-42
```

A project-restricted connection cannot register projects or broaden references. Ungranted project names, aliases and paths are denied without revealing which exist. Read-only removes write tools and refuses write calls. A bound actor/session cannot be replaced by model arguments.

These are restrictions on this server connection, not an OS sandbox, user authentication or a substitute for a host authorization policy. The same local OS account may have separate direct file access. A host must authorize a principal before it creates a connection. No public listener, tunnel, OAuth service or secret-bearing config is installed.

## Grok Bot

For a command-capable client with an already authorized private SSH route, the same protocol can reach one canonical host without publishing an HTTP endpoint:

```sh
shared-context connect --client grok-bot --project demo --read-only \
  --ssh context-host --launcher /srv/shared-context/bin/shared-context
```

This generates a command recipe, not a connection. The existing SSH target and host key must work from the client computer; a private address on your laptop's network is not automatically reachable from a cloud computer. The remote host must be POSIX and have Python plus the package installed. Arguments are shell-quoted, interactive authentication is disabled, host-key checking remains strict, and agent/port forwarding is disabled. No SSH endpoint, account, key, tunnel, or public route is created. The generation/quoting contract is tested; a live cross-host SSH run is not claimed.

The official Team Bots documentation describes Command MCP servers on the conversation computer and Remote HTTPS servers. Use connect --client grok-bot to obtain the command/arguments and deployment requirements. The output is a setup recipe, not an invented Grok import file.

A command running in a Grok cloud computer cannot execute a path on a different Mac. Install the package on the selected computer and choose where the canonical context lives, or deliberately authorize a private bridge. Do not publish a laptop endpoint as a shortcut. The Grok web connector path has different network requirements from a Command server in a Bot computer.

## OpenAI dots

Official dots documentation distinguishes cloud and connected computers. For a connected local computer, configure this MCP server in that computer's Codex client and select the computer for the authorized task. This is a researched route, not a completed dot-account test.

Cloud-only/plugin usage needs an authenticated, reachable MCP deployment and account-side setup. A .mcp.json or a local CLI command does not make a cloud agent able to read a laptop. The optional [HTTP component](HTTP.md) provides a tested read-only loopback transport, not HTTP/OAuth hosting. This package does not distribute the user's context or credentials.

## OpenClaw

Current official docs describe a native MCP registry under mcp.servers and the mcp CLI, separate from the older mcporter workflow. Use the generated definition and the documented Settings/registry path for the installed version. Do not restart or overwrite a live Gateway just to configure a server. No Gateway change is part of setup here. OpenClaw 2026.10.5's actual `mcp probe` discovered the three scoped read-only tools, resources and prompts with no diagnostics in a disposable, uncredentialed home. The bounded retry was admitted by the lifecycle guard after an earlier refusal; no guard bypass was used. This is discovery evidence, not a live Gateway turn, tool-execution or model-compliance test. Repeat with `tools/verify_openclaw.py --openclaw /absolute/path/to/openclaw` under a bounded process lease.

## Multiple computers and privacy

One canonical store is not automatic filesystem synchronization. An MCP server observes its own filesystem. Returned context explicitly labels that observation source. A remote client's separate checkout is not thereby observed, merged or deployed. Preserve that distinction in receipts. Using an approved SSH/remote bridge can expose the canonical store, but provisioning it, credentials and network reachability are separate from generating a recipe.

Share a deliberately selected project with a room or remote principal. Do not copy all personal history, credentials, hidden files or unrelated customer projects. Project grant and room membership are different decisions.

## Qualification receipts

Local qualification exercised Gemini CLI 0.42.0, Pi 1.3.0 (@earendil-works/pi-coding-agent), and OpenCode 1.19.3 using disposable homes and no inference calls. Their native CLI commands reported a connected MCP server. Pi's shipped McpServerConnection additionally recalled a stored decision, wrote a checkpoint, read resources and failed an ungranted-project call. The existing Claude/Codex/Hermes native harness also passes.

This is transport/configuration and deterministic adapter evidence, not proof that every model automatically checkpoints, every desktop surface loads the same configuration, or every cloud account works. Pi's older @mariozechner 0.73.1 package does not provide this native MCP interface. OpenCode v2 and Antigravity are not inferred from tests of these versions.

Run python tools/verify_universal.py with explicit CLI paths to repeat the new-client checks; tools/probe_pi.mjs exercises Pi's actual runtime. The ordinary unit suite covers scopes, resources, prompts, room bindings, stale history, conflicts, updates and uninstall behavior.

## Primary sources

- [Gemini MCP](https://geminicli.com/docs/tools/mcp-server/), [hooks](https://geminicli.com/docs/hooks/reference/).
- [OpenCode MCP](https://opencode.ai/docs/mcp-servers/), [configuration](https://opencode.ai/docs/config/), [plugins](https://opencode.ai/docs/plugins/).
- [Pi MCP](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md), [extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md). Published 1.3.0 package declarations/runtime were also inspected.
- [OpenClaw MCP CLI](https://docs.openclaw.ai/cli/mcp), [registry](https://docs.openclaw.ai/cli/mcp/registry).
- [Grok Bot overview](https://docs.x.ai/grok-bot/overview), [Team Bots](https://docs.x.ai/grok-bot/team-bots), [Grok connectors](https://docs.x.ai/grok/connectors).
- [OpenAI dots computers/apps](https://learn.chatgpt.com/codex/dots/computers-and-apps), [plugin MCP](https://developers.openai.com/plugins/concepts/mcp-server).
- [MCP transport specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [Hermes documentation](https://hermes-agent.nousresearch.com/docs/).
