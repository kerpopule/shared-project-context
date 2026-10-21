"""Install for the current local account and verify unrelated config semantics stay unchanged.
Run with a Python that has PyYAML and tomllib. This is a maintainer receipt tool, not a runtime dependency.
"""

import hashlib
import json
from pathlib import Path
import sys
import tomllib
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared_context.install import setup, atomic_text
from shared_context.health import doctor

NAME = "shared-project-context"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def preserved():
    home = Path.home()
    result = {}
    file = home / ".codex/config.toml"
    data = tomllib.loads(file.read_text()) if file.exists() else {}
    data.get("mcp_servers", {}).pop(NAME, None)
    if data.get("mcp_servers") == {}:
        data.pop("mcp_servers")
    result["codex"] = digest(data)
    file = home / ".claude.json"
    data = json.loads(file.read_text()) if file.exists() else {}
    # CLI-owned transient caches/counters may change. Existing server definitions must not.
    result["claude_existing_servers"] = digest(
        {k: v for k, v in data.get("mcpServers", {}).items() if k != NAME}
    )
    file = home / ".claude/settings.json"
    data = json.loads(file.read_text()) if file.exists() else {}
    for event, groups in data.get("hooks", {}).items():
        data["hooks"][event] = [
            g
            for g in groups
            if not any(NAME in h.get("command", "") for h in g.get("hooks", []))
        ]
    if data.get("hooks", {}).get("UserPromptSubmit") == []:
        data["hooks"].pop("UserPromptSubmit")
    if data.get("hooks") == {}:
        data.pop("hooks")
    result["claude_settings"] = digest(data)
    file = home / ".hermes/config.yaml"
    data = yaml.safe_load(file.read_text()) if file.exists() else {}
    plugins = data.get("plugins", {})
    enabled = plugins.get("enabled", [])
    if isinstance(enabled, list):
        plugins["enabled"] = [p for p in enabled if p != NAME]
    plugins.get("entries", {}).pop(NAME, None)
    if plugins.get("entries") == {}:
        plugins.pop("entries")
    result["hermes_config"] = digest(data)
    for client, file in {
        "claude_instructions": home / ".claude/CLAUDE.md",
        "codex_instructions": home / ".codex/AGENTS.md",
    }.items():
        import re

        text = file.read_text() if file.exists() else ""
        text = re.sub(
            r"<!-- shared-project-context:begin sha256=[a-f0-9]{64} -->\n.*?\n<!-- shared-project-context:end -->\n?",
            "",
            text,
            flags=re.S,
        )
        result[client] = digest(text)
    return result


def main():
    before = preserved()
    installation = setup(clients=["claude", "codex", "hermes"])
    after = preserved()
    comparison = {key: before[key] == after[key] for key in before}
    result = {
        "preservation": comparison,
        "native_clients": installation["native"],
        "doctor": doctor(),
    }
    receipt = Path(installation["launcher"]).parents[1] / "local-install-receipt.json"
    atomic_text(receipt, json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not all(comparison.values()) or not result["doctor"]["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
