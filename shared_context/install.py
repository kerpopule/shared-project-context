"""Installer-owned instruction blocks. No rewriting of unrelated configuration."""

import hashlib
import json
import shutil
import shlex
import subprocess
import os
import re
import tempfile
from pathlib import Path
from . import __version__

BEGIN = "<!-- shared-project-context:begin sha256="
END = "<!-- shared-project-context:end -->"
SETUP_CLIENTS = ("claude", "codex", "hermes", "gemini", "pi", "opencode")


class InstallError(ValueError):
    pass


def atomic_text(path, text, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".shared-context-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def manage_block(path, body, dry_run=False):
    path = Path(path)
    old = path.read_text() if path.exists() else ""
    pattern = re.compile(
        r"\n<!-- shared-project-context:begin sha256=([a-f0-9]{64}) -->\n(.*?)\n"
        + re.escape(END)
        + r"\n",
        re.S,
    )
    matches = list(pattern.finditer(old))
    if old.count(BEGIN) != len(matches) or len(matches) > 1:
        raise InstallError("managed_block_malformed")
    for m in matches:
        if hashlib.sha256(m[2].encode()).hexdigest() != m[1]:
            raise InstallError("managed_block_modified")
    new = ""
    if body is not None:
        digest = hashlib.sha256(body.encode()).hexdigest()
        new = "\n" + BEGIN + digest + " -->\n" + body + "\n" + END + "\n"
    text = (
        old[: matches[0].start()] + new + old[matches[0].end() :]
        if matches
        else old + new
    )
    if text != old and not dry_run:
        mode = (path.stat().st_mode & 0o777) if path.exists() else 0o600
        atomic_text(path, text, mode)
    return {
        "changed": text != old,
        "path": str(path),
        "block_present": body is not None,
    }


def manage_claude_hook(path, launcher, remove=False, client="claude", dry_run=False):
    path = Path(path)
    config = json.loads(path.read_text()) if path.exists() else {}
    hooks = config.setdefault("hooks", {})
    event = "BeforeAgent" if client == "gemini" else "UserPromptSubmit"
    groups = hooks.setdefault(event, [])
    command = (
        shlex.quote(str(launcher))
        + " hook"
        + (" --client gemini" if client == "gemini" else "")
    )
    owned = {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": 10000 if client == "gemini" else 10,
            }
        ]
    }
    found = [g for g in groups if g == owned]
    if len(found) > 1:
        raise InstallError("duplicate_managed_hooks")
    if any(
        any(h.get("command") == command for h in g.get("hooks", [])) and g != owned
        for g in groups
    ):
        raise InstallError("claude_hook_modified")
    if remove:
        groups[:] = [g for g in groups if g != owned]
    elif not found:
        groups.append(owned)
    if dry_run:
        return
    atomic_text(
        path,
        json.dumps(config, indent=2) + "\n",
        (path.stat().st_mode & 0o777) if path.exists() else 0o600,
    )


def native_environment(home):
    env = dict(os.environ)
    if Path(home).resolve() != Path.home().resolve():
        env.update(
            HOME=str(home),
            CODEX_HOME=str(home / ".codex"),
            CLAUDE_CONFIG_DIR=str(home / ".claude"),
            HERMES_HOME=str(home / ".hermes"),
            GEMINI_CLI_HOME=str(home),
            PI_CODING_AGENT_DIR=str(home / ".pi/agent"),
            XDG_CONFIG_HOME=str(home / ".config"),
            XDG_DATA_HOME=str(home / ".local/share"),
            XDG_CACHE_HOME=str(home / ".cache"),
            XDG_STATE_HOME=str(home / ".local/state"),
            OPENCODE_CONFIG_DIR=str(home / ".config/opencode"),
        )
    return env


def native_command(client, launcher, remove=False):
    name = "shared-project-context"
    if remove:
        if client == "claude":
            return ["claude", "mcp", "remove", "--scope", "user", name]
        return [client, "mcp", "remove", name]
    if client == "claude":
        return [
            "claude",
            "mcp",
            "add",
            "--scope",
            "user",
            name,
            "--",
            str(launcher),
            "serve",
        ]
    if client == "codex":
        return ["codex", "mcp", "add", name, "--", str(launcher), "serve"]
    return ["hermes", "mcp", "add", name, "--command", str(launcher), "--args", "serve"]


def run_native(command, env=None):
    p = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
    if p.returncode:
        raise InstallError("native_command_failed:" + command[0])
    return p.stdout


def setup(home=None, state=None, clients=None, native=True, reactivate=False):
    from .api import GUIDANCE
    from .core import Store, default_home

    home = Path(home or Path.home()).expanduser().resolve()
    state = Path(state or default_home()).expanduser().resolve()
    clients = (
        [c for c in SETUP_CLIENTS if shutil.which(c)] if clients is None else clients
    )
    if not set(clients) <= set(SETUP_CLIENTS):
        raise InstallError("unknown_client")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest_path = state / "installation.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if previous and not previous.get("active", True) and not reactivate:
        raise InstallError("installation_disabled_use_explicit_reinstall")
    if previous and not previous.get("active", True) and reactivate:
        previous = {
            key: value
            for key, value in previous.items()
            if key
            not in {
                "native",
                "clients",
                "instructions",
                "connections",
                "pending_clients",
                "claude_hook",
                "gemini_hook",
            }
        }
    source = Path(__file__).parent
    files = {p.name: p.read_text() for p in source.glob("*.py")}
    code_hash = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    runtime = state / "runtime" / code_hash[:16]
    for name, contents in files.items():
        target = runtime / "shared_context" / name
        if target.exists() and target.read_text() != contents:
            raise InstallError("immutable_runtime_modified")
        if not target.exists():
            atomic_text(target, contents)
    launcher = state / "bin" / "shared-context"
    launcher_text = (
        "#!/usr/bin/env python3\nimport os,sys\n"
        + "sys.path.insert(0, "
        + repr(str(runtime))
        + ")\n"
        + 'os.environ["SHARED_CONTEXT_HOME"] = '
        + repr(str(state))
        + "\n"
        + "from shared_context.__main__ import main\nsys.exit(main())\n"
    )
    # Keep user modifications rather than silently repairing over them.
    if (
        launcher.exists()
        and previous.get("launcher_hash")
        and hashlib.sha256(launcher.read_bytes()).hexdigest()
        != previous["launcher_hash"]
    ):
        raise InstallError("launcher_modified")
    env = native_environment(home)
    claude_root = Path(env.get("CLAUDE_CONFIG_DIR", str(home / ".claude")))
    codex_root = Path(env.get("CODEX_HOME", str(home / ".codex")))
    hermes_root = Path(env.get("HERMES_HOME", str(home / ".hermes")))
    gemini_root = Path(env.get("GEMINI_CLI_HOME", str(home))) / ".gemini"
    pi_root = Path(env.get("PI_CODING_AGENT_DIR", str(home / ".pi/agent")))
    opencode_root = Path(env.get("XDG_CONFIG_HOME", str(home / ".config"))) / "opencode"
    paths = {
        "claude": claude_root / "CLAUDE.md",
        "codex": codex_root
        / (
            "AGENTS.override.md"
            if (codex_root / "AGENTS.override.md").exists()
            else "AGENTS.md"
        ),
        "gemini": gemini_root / "GEMINI.md",
        "pi": pi_root / "AGENTS.md",
        "opencode": opencode_root / "AGENTS.md",
    }
    from .clients import connection, manage_json_entry, NAME

    configs = {
        "gemini": (gemini_root / "settings.json", ["mcpServers", NAME]),
        "pi": (pi_root / "mcp.json", ["mcpServers", NAME]),
        "opencode": (opencode_root / "opencode.json", ["mcp", NAME]),
    }
    pending_connections = {}
    if native:
        for client in clients:
            if client not in configs:
                continue
            path, keys = configs[client]
            if client == "opencode" and (
                (opencode_root / "opencode.jsonc").exists()
                or (
                    home == Path.home().resolve()
                    and any(
                        env.get(key)
                        for key in (
                            "OPENCODE_CONFIG",
                            "OPENCODE_CONFIG_CONTENT",
                            "OPENCODE_CONFIG_DIR",
                        )
                    )
                )
            ):
                raise InstallError("opencode_config_precedence_use_connect_recipe")
            config = connection(client, str(launcher))["configuration"]
            entry = config[keys[0]][keys[1]]
            owned = previous.get("connections", {}).get(client)
            pending_connections[client] = manage_json_entry(
                path, keys, entry, previous=owned, dry_run=True
            )
            if client == "gemini":
                manage_claude_hook(path, launcher, client="gemini", dry_run=True)
    instructions = (
        "# Shared project context\n"
        + GUIDANCE
        + "\nLocal fallback: "
        + str(launcher)
        + ' call context \'{"project":"PROJECT_ID_OR_PATH"}\'\n'
    )
    # Validate all managed blocks before changing any of them.
    for client in clients:
        if client in paths and paths[client].exists():
            text = paths[client].read_text()
            matches = re.findall(
                r"<!-- shared-project-context:begin sha256=([a-f0-9]{64}) -->\n(.*?)\n"
                + re.escape(END),
                text,
                re.S,
            )
            if text.count(BEGIN) != len(matches) or len(matches) > 1:
                raise InstallError("managed_block_malformed")
            if any(
                hashlib.sha256(body.encode()).hexdigest() != digest
                for digest, body in matches
            ):
                raise InstallError("managed_block_modified")
    atomic_text(launcher, launcher_text, 0o700)
    manifest = {
        **previous,
        "active": True,
        "launcher": str(launcher),
        "runtime": str(runtime),
        "code_hash": code_hash,
        "launcher_hash": hashlib.sha256(launcher_text.encode()).hexdigest(),
        "clients": sorted(set(previous.get("clients", [])) | set(clients)),
        "native": previous.get("native", []),
        "instructions": previous.get("instructions", {}),
        "connections": previous.get("connections", {}),
    }
    for client in clients:
        if client in paths:
            manage_block(paths[client], instructions)
            manifest["instructions"][client] = str(paths[client])
    atomic_text(manifest_path, json.dumps(manifest, indent=2))
    Store(state).db.close()
    # Explicit user/profile homes. Never fan out across profiles.
    env = native_environment(home)
    if native:
        for client in clients:
            if client in pending_connections:
                receipt = pending_connections[client]
                manifest["connections"][client] = manage_json_entry(
                    receipt["path"],
                    receipt["keys"],
                    receipt["entry"],
                    previous=previous.get("connections", {}).get(client),
                )
            elif client == "hermes":
                # Native plugin exposes the same tools plus per-turn context; no duplicate MCP server.
                plug = hermes_root / "plugins/shared-project-context"
                manifest["plugin_dir"] = str(plug)
                plugin_text = (
                    "import sys\nsys.path.insert(0, "
                    + repr(str(runtime))
                    + ")\n"
                    + "from shared_context.hermes_adapter import register as _register\n"
                    + "def register(ctx):\n    return _register(ctx, state="
                    + repr(str(state))
                    + ")\n"
                )
                old_files = previous.get("plugin_hashes", {})
                for name, text in {
                    "__init__.py": plugin_text,
                    "plugin.yaml": f'name: shared-project-context\nversion: "{__version__}"\ndescription: Local shared project awareness\n',
                }.items():
                    f = plug / name
                    if f.exists() and (
                        name not in old_files
                        or hashlib.sha256(f.read_bytes()).hexdigest() != old_files[name]
                    ):
                        raise InstallError("plugin_modified_or_unowned")
                    atomic_text(f, text)
                manifest["plugin_hashes"] = {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in plug.iterdir()
                    if p.is_file() and p.suffix in {".py", ".yaml"}
                }
                if "hermes" not in previous.get("native", []) or reactivate:
                    run_native(
                        [
                            "hermes",
                            "plugins",
                            "enable",
                            "--no-allow-tool-override",
                            "shared-project-context",
                        ],
                        env,
                    )
                manifest["hermes_state"] = str(state)
            else:
                get_cmd = [client, "mcp", "get", "shared-project-context"] + (
                    ["--json"] if client == "codex" else []
                )
                probe = subprocess.run(
                    get_cmd, capture_output=True, text=True, timeout=45, env=env
                )
                if probe.returncode == 0:
                    if str(launcher) not in probe.stdout:
                        raise InstallError("native_server_name_conflict:" + client)
                    if client not in manifest["native"] and client not in manifest.get(
                        "pending_clients", []
                    ):
                        raise InstallError("native_existing_unowned:" + client)
                else:
                    if client not in manifest.setdefault("pending_clients", []):
                        manifest["pending_clients"].append(client)
                    atomic_text(manifest_path, json.dumps(manifest, indent=2))
                    run_native(native_command(client, launcher), env)
            if client == "claude":
                settings = claude_root / "settings.json"
                manage_claude_hook(settings, launcher)
                manifest["claude_hook"] = str(settings)
            if client == "gemini":
                settings = gemini_root / "settings.json"
                manage_claude_hook(settings, launcher, client="gemini")
                manifest["gemini_hook"] = str(settings)
            if client not in manifest["native"]:
                manifest["native"].append(client)
            manifest["pending_clients"] = [
                c for c in manifest.get("pending_clients", []) if c != client
            ]
            atomic_text(manifest_path, json.dumps(manifest, indent=2))
    return manifest


def uninstall(home=None, state=None, native=True):
    from .core import default_home

    home = Path(home or Path.home()).resolve()
    state = Path(state or default_home()).resolve()
    f = state / "installation.json"
    manifest = json.loads(f.read_text())
    if not manifest.get("active", True):
        return {"active": False, "data_retained": True, "runtime_retained": True}
    env = native_environment(home)
    # Fail closed before removing instructions if an owned component was changed.
    for path in manifest.get("instructions", {}).values():
        manage_block(Path(path), None, dry_run=True)
    if native:
        from .clients import manage_json_entry

        for owned in manifest.get("connections", {}).values():
            manage_json_entry(
                owned["path"], owned["keys"], None, previous=owned, dry_run=True
            )
        for client in ("claude", "gemini"):
            if manifest.get(client + "_hook"):
                manage_claude_hook(
                    manifest[client + "_hook"],
                    manifest["launcher"],
                    remove=True,
                    client=client,
                    dry_run=True,
                )
    for client, path in manifest.get("instructions", {}).items():
        manage_block(Path(path), None)
    if native:
        if manifest.get("gemini_hook"):
            manage_claude_hook(
                manifest["gemini_hook"],
                manifest["launcher"],
                remove=True,
                client="gemini",
            )
        if manifest.get("claude_hook"):
            manage_claude_hook(
                manifest["claude_hook"], manifest["launcher"], remove=True
            )
        for client in manifest.get("native", []):
            if client in manifest.get("connections", {}):
                from .clients import manage_json_entry

                owned = manifest["connections"][client]
                manage_json_entry(owned["path"], owned["keys"], None, previous=owned)
            elif client == "hermes":
                run_native(
                    ["hermes", "plugins", "disable", "shared-project-context"], env
                )
            else:
                probe = subprocess.run(
                    [client, "mcp", "get", "shared-project-context"],
                    capture_output=True,
                    text=True,
                    timeout=45,
                    env=env,
                )
                if probe.returncode == 0:
                    if manifest["launcher"] not in probe.stdout:
                        raise InstallError("native_configuration_modified:" + client)
                    run_native(
                        native_command(client, manifest["launcher"], remove=True), env
                    )
    manifest["active"] = False
    atomic_text(f, json.dumps(manifest, indent=2))
    return {"active": False, "data_retained": True, "runtime_retained": True}
