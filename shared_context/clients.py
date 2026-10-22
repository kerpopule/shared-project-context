"""Client-specific connection recipes; core operations never depend on a vendor.

Recipes are not claims of a successful vendor session. Cloud UI fields differ
from local config files; do not invent an import format for them.
"""

import json
import re
import shlex
from pathlib import Path

from .install import InstallError, atomic_text
from .scope import Scope

NAME = "shared-project-context"
CLIENTS = {
    "claude": ("mcpServers", "https://code.claude.com/docs/en/mcp"),
    "codex": ("mcp_servers", "https://developers.openai.com/codex/mcp/"),
    "hermes": (
        "mcp_servers",
        "https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/",
    ),
    "gemini": ("mcpServers", "https://geminicli.com/docs/tools/mcp-server/"),
    "pi": (
        "mcpServers",
        "https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md",
    ),
    "opencode": ("mcp", "https://opencode.ai/docs/mcp-servers/"),
    "openclaw": ("mcp.servers", "https://docs.openclaw.ai/cli/mcp/registry"),
    "cursor": ("mcpServers", "https://cursor.com/docs/context/mcp"),
    "claude-desktop": ("mcpServers", "https://modelcontextprotocol.io/quickstart/user"),
    "vscode": (
        "servers",
        "https://code.visualstudio.com/docs/copilot/customization/mcp-servers",
    ),
    "generic": (
        "mcpServers",
        "https://modelcontextprotocol.io/docs/develop/connect-local-servers",
    ),
    "grok-bot": (None, "https://docs.x.ai/grok-bot/team-bots"),
    "dots": (None, "https://learn.chatgpt.com/codex/dots/computers-and-apps"),
}


def connection(
    client,
    launcher,
    *,
    project=None,
    read_only=False,
    actor=None,
    session=None,
    ssh=None,
):
    if client not in CLIENTS:
        raise InstallError("unknown_client")
    launcher = str(launcher)
    if not Path(launcher).is_absolute() or "\x00" in launcher:
        raise InstallError("absolute_launcher_required")
    Scope(
        project, read_only, actor, session
    )  # Same validation as the actual transport.
    args = ["serve"]
    for flag, value in (
        ("--project", project),
        ("--actor", actor),
        ("--session", session),
    ):
        if value is not None:
            args += [flag, value]
    if read_only:
        args.append("--read-only")
    server = {"command": launcher, "args": args}
    if ssh is not None:
        if (
            not project
            or not isinstance(ssh, str)
            or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:@-]{0,199}", ssh)
        ):
            raise InstallError("explicit_project_and_safe_ssh_target_required")
        server = {
            "command": "ssh",
            "args": [
                "-T",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                "ForwardAgent=no",
                "-o",
                "ClearAllForwardings=yes",
                "-o",
                "PermitLocalCommand=no",
                "--",
                ssh,
                shlex.join([launcher, *args]),
            ],
        }
    shape, source = CLIENTS[client]
    requirements = [
        "Python 3.9+ and the installed launcher must be on the computer running the MCP client."
    ]
    if ssh is not None:
        requirements = [
            "Python 3.9+ and the launcher must exist on the remote POSIX host; an existing authorized SSH alias, authentication and pinned host key must already work.",
            "This recipe does not connect, provision a server, copy credentials or grant SSH authority. The SSH account is not an OS sandbox; MCP scoping restricts only this connection.",
        ]
    configuration = None
    if shape == "mcp":
        configuration = {
            "mcp": {
                NAME: {
                    "type": "local",
                    "command": [server["command"], *server["args"]],
                    "enabled": True,
                }
            }
        }
    elif shape == "mcp.servers":
        configuration = {"mcp": {"servers": {NAME: {**server, "enabled": True}}}}
        requirements += [
            "Requires OpenClaw native MCP registry support, not just mcporter. Respect Gateway state ownership; use Settings for a live Gateway."
        ]
    elif shape == "servers":
        configuration = {"servers": {NAME: {"type": "stdio", **server}}}
    elif shape:
        configuration = {shape: {NAME: server}}
    elif client == "grok-bot":
        requirements += [
            "Use Apps > MCP > Command on the conversation computer. Enter command and arguments from server below; this object is not a Grok import file.",
            "A cloud conversation computer cannot read a Mac path. Install on that computer, or use an explicitly authorized private bridge to the shared host.",
            "Remote HTTPS connectors require separate authenticated deployment; this package does not publish an endpoint.",
            "Team Bot setup changes can reach every teammate. A Command runs on each conversation's computer; do not put credentials in argv or grant team-wide access to private project context without explicit sharing approval.",
        ]
    elif client == "dots":
        requirements += [
            "In the ChatGPT app on the chosen computer, open the exact dot profile > Computers > Your computer > Allow access, and confirm. This is a separate persistent permission from Codex computer access or Work Sync.",
            "Configure scoped MCP in that computer's Codex client, then verify discovery and project reads in an actual dot-created local Codex task. A Codex transport probe alone does not qualify the dot connection.",
            "Cloud-only and remote plugin access need a separately deployed authenticated HTTPS MCP server and account setup. Local stdio is not a cloud connector.",
            "No dot account or cloud execution is inferred from generating this recipe.",
        ]
    if client == "pi":
        requirements += [
            "Requires a Pi build with native MCP mcp.json support; older Pi builds need their own extension. Verify pi mcp --help."
        ]
    return {
        "client": client,
        "server": server,
        "configuration": configuration,
        "source": source,
        "requirements": requirements,
        "verified_in_vendor_runtime": False,
        "notice": "A recipe is not runtime verification. No configuration or account has been changed.",
    }


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise InstallError("duplicate_json_key")
        value[key] = item
    return value


def manage_json_entry(path, keys, entry, *, previous=None, dry_run=False):
    """CAS against the owned entry, preserving all unrelated JSON values.

    Refuse JSONC/JSON5 rather than flattening comments or overriding precedence.
    Changed bytes abort the write. This is not an atomic compare-and-swap with
    unrelated native applications; do not edit settings concurrently with setup.
    """
    path = Path(path)
    if path.is_symlink():
        raise InstallError("config_symlink_requires_manual_setup")
    old = path.read_bytes() if path.exists() else None
    try:
        config = (
            json.loads(old, object_pairs_hook=_unique_object) if old is not None else {}
        )
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise InstallError("non_json_config_use_native_or_manual_setup") from None
    if (
        not isinstance(config, dict)
        or not keys
        or not all(isinstance(k, str) for k in keys)
    ):
        raise InstallError("invalid_config_shape")
    node = config
    for key in keys[:-1]:
        if key not in node:
            node[key] = {}
        if not isinstance(node[key], dict):
            raise InstallError("invalid_config_shape")
        node = node[key]
    key = keys[-1]
    if previous:
        if previous.get("path") != str(path) or previous.get("keys") != list(keys):
            raise InstallError("managed_connection_location_changed")
        if key not in node or node[key] != previous["entry"]:
            raise InstallError("managed_connection_modified")
    elif key in node:
        raise InstallError("connection_name_unowned")
    if entry is None:
        if not previous:
            raise InstallError("unowned_removal_refused")
        del node[key]
        # Remove only empty containers created by this installer.
        for depth in range(len(keys) - 1, 0, -1):
            container = config
            for parent in keys[: depth - 1]:
                container = container[parent]
            parent = keys[depth - 1]
            if not container[parent] and keys[:depth] in previous.get(
                "created_containers", []
            ):
                del container[parent]
    else:
        node[key] = entry
    created = list(previous.get("created_containers", [])) if previous else []
    if not previous:
        original = json.loads(old) if old is not None else {}
        for depth, parent in enumerate(keys[:-1], 1):
            if parent not in original:
                created.append(list(keys[:depth]))
                original = {}
            else:
                original = original[parent]
    receipt = {
        "path": str(path),
        "keys": list(keys),
        "entry": entry,
        "created_containers": created,
    }
    if dry_run:
        return receipt
    if (path.read_bytes() if path.exists() else None) != old:
        raise InstallError("config_changed_during_install")
    atomic_text(
        path,
        json.dumps(config, indent=2) + "\n",
        (path.stat().st_mode & 0o777) if path.exists() else 0o600,
    )
    return receipt
