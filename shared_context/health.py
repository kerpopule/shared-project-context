"""Explicit configuration and protocol checks, never a claim of model behavior."""

import hashlib
import json
import subprocess
import sqlite3
from pathlib import Path
from .core import Store, default_home


def protocol_probe(launcher):
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "shared-context-doctor", "version": "0.1.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "project_list", "arguments": {}},
        },
    ]
    p = subprocess.run(
        [str(launcher), "serve"],
        input="\n".join(json.dumps(m) for m in messages) + "\n",
        capture_output=True,
        text=True,
        timeout=15,
    )
    replies = [json.loads(line) for line in p.stdout.splitlines()]
    return bool(
        p.returncode == 0
        and len(replies) == 3
        and {tool["name"] for tool in replies[1]["result"]["tools"]}
        == {
            "project_register",
            "project_reference",
            "project_read_reference",
            "project_context",
            "project_begin",
            "project_checkpoint",
            "project_finish",
            "project_list",
        }
        and not replies[2]["result"].get("isError")
    )


def doctor(state=None, native=True):
    state = Path(state or default_home())
    checks = {}
    try:
        manifest = json.loads((state / "installation.json").read_text())
        store = Store(state)
        checks["sqlite_integrity"] = (
            store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        )
        store.db.close()
        checks["installation_active"] = bool(manifest["active"])
        launcher = Path(manifest["launcher"])
        checks["launcher_hash"] = (
            hashlib.sha256(launcher.read_bytes()).hexdigest()
            == manifest["launcher_hash"]
        )
        runtime = state / "runtime" / manifest["code_hash"][:16] / "shared_context"
        files = {p.name: p.read_text() for p in runtime.glob("*.py")}
        checks["runtime_hash"] = (
            hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
            == manifest["code_hash"]
        )
        checks["mcp_handshake_and_call"] = protocol_probe(launcher)
        for client, path in manifest.get("instructions", {}).items():
            import re
            from .install import END

            text = Path(path).read_text()
            found = re.findall(
                r"<!-- shared-project-context:begin sha256=([a-f0-9]{64}) -->\n(.*?)\n"
                + re.escape(END),
                text,
                re.S,
            )
            checks[client + "_instructions"] = (
                len(found) == 1
                and hashlib.sha256(found[0][1].encode()).hexdigest() == found[0][0]
            )
        if manifest.get("claude_hook"):
            import shlex

            config = json.loads(Path(manifest["claude_hook"]).read_text())
            command = shlex.quote(str(launcher)) + " hook"
            checks["claude_prompt_hook"] = any(
                h.get("command") == command
                for g in config.get("hooks", {}).get("UserPromptSubmit", [])
                for h in g.get("hooks", [])
            )
        if "hermes" in manifest.get("native", []):
            plug = Path(manifest["plugin_dir"])
            checks["hermes_plugin_files"] = all(
                (plug / name).is_file()
                and hashlib.sha256((plug / name).read_bytes()).hexdigest() == digest
                for name, digest in manifest["plugin_hashes"].items()
            )
        if native:
            for client in manifest.get("native", []):
                if client == "hermes":
                    p = subprocess.run(
                        ["hermes", "plugins", "list", "--user", "--json"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    rows = json.loads(p.stdout) if p.returncode == 0 else []
                    checks["hermes_enabled"] = any(
                        r.get("name") == "shared-project-context"
                        and r.get("status") == "enabled"
                        for r in rows
                    )
                    continue
                cmd = [client, "mcp", "get", "shared-project-context"] + (
                    ["--json"] if client == "codex" else []
                )
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                checks[client + "_native_config"] = (
                    p.returncode == 0 and str(launcher) in p.stdout
                )
                if client == "codex" and p.returncode == 0:
                    record = json.loads(p.stdout)
                    checks["codex_enabled"] = record.get("enabled", True) is not False
        return {
            "ok": all(checks.values()),
            "checks": checks,
            "scope": "local configuration, integrity and MCP transport only; not model behavior or desktop/remote coverage",
        }
    except (ValueError, OSError, KeyError, sqlite3.Error, subprocess.TimeoutExpired):
        return {
            "ok": False,
            "checks": checks,
            "error": "installation_unavailable_or_changed",
        }
