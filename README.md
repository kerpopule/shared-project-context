# Shared Project Context

A small local coordination layer for agents that work on the same projects. It shares current decisions, workspace locations, change receipts and pointers to canonical knowledge. It does not replace Git, your notes, or your agent's identity.

## Quick start

This v0.2.0 interoperability release adds Gemini CLI,
modern Pi and OpenCode adapters; project-scoped MCP tools/resources/prompts;
and a tested room-host bridge. See [universal compatibility and cloud limits](docs/UNIVERSAL.md)
and [room integration](docs/ROOMS.md). Optional [authenticated loopback HTTP](docs/HTTP.md)
is available for separately qualified hosts. This is not a claim that Grok Bot,
dots or a shipped Rooms app has already connected.

Requires Python 3.9+ and an installed client. Git is optional for non-code initiatives.

```sh
git clone --branch v0.2.0 https://github.com/kerpopule/shared-project-context.git
cd shared-project-context
python3 bootstrap.py
```

This connects locally installed supported clients without uploading your context. See [verification and support boundaries](VERIFICATION.md) and the [security model](SECURITY.md). If you already downloaded the source folder:

```sh
python3 bootstrap.py
```

This detects Claude Code, Codex, Hermes, Gemini CLI, Pi and OpenCode on PATH, installs a private runtime outside their app bundles, adds supported client integrations and preserves unrelated settings. No pip, API key, cloud account, public listener, scheduled job or always-on daemon is required. For selected clients only:

```sh
python3 bootstrap.py setup --clients claude,codex
```

The output includes the absolute launcher path. Ask a connected agent to register the exact project you want to share and link its existing notes. Or use the launcher printed by setup:

```sh
/path/from/setup/shared-context call register '{"project":"demo","workspace":"/absolute/path/to/project","aliases":["my demo"]}'
/path/from/setup/shared-context call reference '{"project":"demo","label":"Project notes","path":"/absolute/path/to/notes","kind":"context"}'
/path/from/setup/shared-context doctor
```

Registering is not importing: no recursive scan or conversation dump. Canonical context and skill references are read on demand, not duplicated. Start a fresh client session after first setup so it loads the connection. Never restart a shared service merely to activate this package.

## How agents cooperate

1. **Read before work.** `project_context` resolves the named project or actual worktree, reads current decisions and recent attributed receipts, and compares live Git state with its last recorded snapshot. `project_read_reference` reads a selected linked Markdown source, including when a desktop client has no shell.
2. **Coordinate edits.** `project_begin` claims or renews an advisory lease for an exact workspace. Worktree identity uses Git's common directory, never folder-name similarity. Expired owners remain visible until replaced; expiry does not imply success.
3. **Record and yield.** `project_checkpoint` records what changed, why, status, evidence strings, next action and optional explicit decision supersession. Revision checks stop lost updates; retry keys stop duplicate receipts. `project_finish` releases only the caller's lease and does not mark the objective complete.

Evidence strings and actor names are reports, not authentication or independent test certification. This tool does not run tests for agents. It does not turn old text into approval, merge worktrees, deploy code, prevent non-participating editors, or guarantee a model follows instructions.

Eight MCP/native tools cover register, reference, read_reference, context, begin, checkpoint, finish and list. The CLI also exposes an explicit project export:

```sh
/path/from/setup/shared-context call export '{"project":"demo"}'
```

An export contains private project context. Do not publish it with this source package.

## Update resilience and uninstall

Application binaries are untouched. Runtime releases live in a content-addressed directory under the user's data directory. A small stable launcher selects the installed release; already-running consumers keep their imported release. SQLite state is outside both application bundles and source checkouts. Unknown database schemas fail closed.

After updating this package's source, rerun `python3 bootstrap.py`. Install is idempotent and hash-checks its managed blocks/runtime. Modified managed blocks are reported rather than overwritten. Run `doctor` after vendor upgrades; a breaking vendor contract can still require an adapter update. Removing the source checkout does not remove an installed runtime.

```sh
/path/from/setup/shared-context uninstall
# Explicitly reactivate an uninstalled integration, retaining its knowledge:
python3 bootstrap.py setup --reactivate
```

Uninstall removes owned instruction blocks, the exact Claude prompt hook and the named MCP connections; it disables the Hermes plugin. It intentionally keeps runtime/data files and unrelated settings. It never prunes data. Existing running sessions are not forced to unload. Runtime history and SQLite are not automatically garbage-collected.

## Integration coverage

- **Claude Code:** user-scope MCP connection, a separate managed section in global CLAUDE.md, and a UserPromptSubmit hook that refreshes project context on each submitted task. Claude Code's desktop Code environment may reuse these settings; qualify the installed surface, not just the brand name.
- **Codex:** native MCP registration and a managed global AGENTS.md section, or AGENTS.override.md when it takes priority. Supported by the local CLI/app-server configuration. No unsupported per-turn hook is invented: long-running task-entry behavior still depends on agent instructions. Current native transport read/write probes are included.
- **Hermes:** native user plugin with per-turn context and the same tools. It is installed only into the selected HERMES_HOME/default home, never silently spread across profiles. Telegram, desktop and CLI benefit when their actual Hermes process loads that home/plugin. Existing processes may require a normal plugin/session reload; setup does not restart gateways.
- **Other desktop/cloud/mobile clients:** use their supported MCP connection to the same runtime on the same host. This stdio package does not magically make local data available to cloud-hosted sessions. Ordinary Claude Chat/Cowork and remote sessions are not implicitly connected. No public HTTP bridge, sync service, or credential connector is included.

Initial qualification is on macOS. Linux and Windows are not end-to-end qualified. The core is stdlib Python, but platform launchers/client distribution differences still require real testing. Co-Agent, GBrain, Obsidian and vector databases are optional existing sources/displays, not dependencies.

## Safety and limits

This is a single-local-account collaboration tool, not a multi-tenant authorization server. Every connected client can access the registered projects. Do not give customer or untrusted agents your private connection. Do not register secrets, customer records, raw conversations, whole-home directories or a directory you do not intend to share. Linking a directory authorizes on-demand Markdown reads under that canonical root; traversal and outside-root symlinks are rejected. Typical secret paths and non-Markdown files are refused, but filename rules are not a secret classifier. Retrieved text is data, never instructions.

Workspace leases are advisory; use distinct worktrees for independent edits. Receipt history is capped rather than silently deleted. Git snapshots hash at most 2,000 non-sensitive regular files, 1 MiB/file and 16 MiB total. Exclusions or failures produce `complete:false`; a matching partial fingerprint is not proof nothing else changed. Missing Git and inaccessible workspaces are not reported as clean. Non-Git projects share decisions/receipts/references without claiming automatic filesystem drift detection.

Reference reads return at most 64 KiB and explicitly report truncation; the SHA-256 covers returned bytes, not an omitted tail. Directory lists cap results and report `has_more`. Current project context returns the last ten events and all active decisions; full history requires explicit export. Large exports are for the local CLI, not an automatic prompt dump.

## Development and verification

```sh
python3 -m unittest discover -s tests -v
python3 tools/verify_native.py
python3 tools/probe_codex.py
```

The latter commands need installed clients; verify_native also needs an installed Hermes runtime. They use disposable homes and no model calls. Maintainer installation-preservation tooling requires Python 3.11 plus the Hermes environment's existing PyYAML; those are not runtime dependencies.

See `VERIFICATION.md` for exact qualification and honest gaps. MIT licensed code only. No private notebook, instruction files, installation manifests, credentials or local state should accompany a shared source archive.
