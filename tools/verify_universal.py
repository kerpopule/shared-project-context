"""Real Gemini/Pi/OpenCode config and transport checks in disposable homes.

Does not make model calls or change the user's client configuration.
Pass absolute executables with --gemini/--pi/--opencode when not on PATH.
"""

import argparse
import json

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared_context.core import Store
from shared_context.health import doctor
from shared_context.install import native_environment, setup, uninstall


def run(command, env, cwd, timeout=45):
    result = subprocess.run(
        command, env=env, cwd=cwd, text=True, capture_output=True, timeout=timeout
    )
    if result.returncode:
        raise RuntimeError(
            f"{Path(command[0]).name} failed ({result.returncode}): {result.stderr[-2000:]} {result.stdout[-2000:]}"
        )
    return result.stdout or result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for client in ("gemini", "pi", "opencode"):
        parser.add_argument("--" + client, default=shutil.which(client))
    args = parser.parse_args()
    executables = {
        client: getattr(args, client) for client in ("gemini", "pi", "opencode")
    }
    if not all(executables.values()):
        parser.error(
            "all three actual client executables required; do not count missing clients as passes"
        )
    with tempfile.TemporaryDirectory(prefix="shared-context-universal-") as directory:
        home = Path(directory).resolve()
        workspace = home / "demo"
        workspace.mkdir()
        state = home / "state"
        env = native_environment(home)
        # Keep all native client data inside this fixture, including inherited custom paths.
        for name in (
            "OPENCODE_CONFIG",
            "OPENCODE_CONFIG_CONTENT",
            "GOOGLE_APPLICATION_CREDENTIALS",
        ):
            env.pop(name, None)
        env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"
        env["OPENCODE_DISABLE_DEFAULT_PLUGINS"] = "1"
        first = setup(home=home, state=state, clients=list(executables))
        store = Store(state)
        store.register("demo", str(workspace))
        store.checkpoint(
            "demo",
            actor="hermes-fixture",
            expected_revision=0,
            key="decision",
            summary="Synthetic shared decision",
            status="proposed",
            decisions=[{"id": "export-policy", "text": "Manual exports only"}],
        )
        store.db.close()
        result = {
            "scope": "native CLI config and transport, not autonomous model behavior",
            "clients": {},
        }
        for client, executable in executables.items():
            version = run([executable, "--version"], env, workspace).strip()
            command = [executable, "mcp", "list"] + (
                ["--json"] if client == "pi" else []
            )
            listing = run(command, env, workspace)
            if "shared-project-context" not in listing or (
                "connected" not in listing.lower() and "✓" not in listing
            ):
                raise RuntimeError(
                    client
                    + " did not report an actual connected MCP server: "
                    + listing
                )
            result["clients"][client] = {
                "version": version,
                "native_connection_reported": True,
            }
        env["SHARED_CONTEXT_HOME"] = str(state)
        pi_root = next(
            (
                parent
                for parent in Path(executables["pi"]).resolve().parents
                if (parent / "package.json").is_file()
                and json.loads((parent / "package.json").read_text()).get("name")
                == "@earendil-works/pi-coding-agent"
            ),
            None,
        )
        if pi_root is None:
            raise RuntimeError("Pi package root for native runtime probe not found")
        probe = run(
            [
                "node",
                str(Path(__file__).with_name("probe_pi.mjs")),
                str(pi_root),
                first["launcher"],
                "demo",
            ],
            env,
            workspace,
        )
        result["pi_runtime_round_trip"] = json.loads(probe.strip().splitlines()[-1])
        result["doctor"] = doctor(state, native=False)["ok"]
        store = Store(state)
        result["hermes_core_recalls_pi_event"] = (
            store.context("demo")["events"][-1]["actor"] == "pi-native"
        )
        store.db.close()
        second = setup(home=home, state=state, clients=list(executables))
        result["idempotent_upgrade"] = first["code_hash"] == second["code_hash"]
        uninstall(home=home, state=state)
        result["uninstall_keeps_shared_data"] = (state / "context.sqlite3").is_file()
        result["pass"] = all(
            result[key]
            for key in (
                "doctor",
                "hermes_core_recalls_pi_event",
                "idempotent_upgrade",
                "uninstall_keeps_shared_data",
            )
        )
        print(json.dumps(result, indent=2))
        return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
