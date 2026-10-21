"""Exercise installed client configuration commands in disposable homes, without model calls."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared_context.install import setup, uninstall, native_environment
from shared_context.health import protocol_probe


def main():
    with tempfile.TemporaryDirectory(prefix="shared-context-native-") as d:
        home = Path(d).resolve()
        (home / ".hermes").mkdir()
        (home / ".hermes/config.yaml").write_text("plugins:\n  enabled: []\n")
        (home / ".claude").mkdir()
        (home / ".claude/settings.json").write_text(
            json.dumps({"env": {"CONTEXT_FIXTURE": "keep"}, "hooks": {}})
        )
        (home / ".codex").mkdir()
        (home / ".codex/config.toml").write_text('model = "fixture-model"\n')
        state = home / "context"
        first = setup(home=home, state=state, clients=["claude", "codex", "hermes"])
        env = native_environment(home)
        results = {
            "clients_configured": first["native"],
            "mcp_protocol": protocol_probe(first["launcher"]),
        }
        for client in ("claude", "codex"):
            p = subprocess.run(
                [client, "mcp", "get", "shared-project-context"],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            results[client + "_readback"] = (
                p.returncode == 0 and first["launcher"] in p.stdout
            )
        second = setup(home=home, state=state, clients=["claude", "codex", "hermes"])
        results["idempotent_runtime"] = second["code_hash"] == first["code_hash"]
        settings = json.loads((home / ".claude/settings.json").read_text())
        results["settings_preserved"] = settings["env"] == {"CONTEXT_FIXTURE": "keep"}
        results["codex_unrelated_preserved"] = (
            'model = "fixture-model"' in (home / ".codex/config.toml").read_text()
        )
        # Fresh real Hermes PluginManager and registry. No real inference or gateway restart.
        script = """import json
from hermes_cli.plugins import PluginManager
from tools.registry import registry
m=PluginManager()
m.discover_and_load()
result=m.invoke_hook('pre_llm_call', session_id='fixture', user_message='hello', conversation_history=[], is_first_turn=True, model='fixture')
print(json.dumps({'hook': any('Shared project continuity' in str(x) for x in result), 'tools': sorted(m._plugin_tool_names)}))
"""
        root = (
            Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
            / "hermes-agent"
        )
        # The fixture HOME is passed to the subprocess, not used to resolve the installed runtime.
        runtime_python = root / "venv/bin/python"
        env["PYTHONPATH"] = str(root)
        p = subprocess.run(
            [str(runtime_python), "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if p.returncode:
            print(p.stderr[-6000:], file=sys.stderr)
            raise SystemExit("native Hermes adapter test failed")
        parsed = json.loads(p.stdout.splitlines()[-1])
        results["hermes_real_hook"] = parsed["hook"]
        results["hermes_real_tools"] = (
            len([t for t in parsed["tools"] if t.startswith("project_")]) == 8
        )
        uninstall(home=home, state=state)
        results["data_retained_after_uninstall"] = (state / "context.sqlite3").exists()
        results["codex_model_retained_after_uninstall"] = (
            "fixture-model" in (home / ".codex/config.toml").read_text()
        )
        results["pass"] = all(
            v is True for k, v in results.items() if k != "clients_configured"
        )
        print(json.dumps(results, indent=2))
        return 0 if results["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
