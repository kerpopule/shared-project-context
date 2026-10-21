"""Probe the actual OpenClaw native MCP CLI in a disposable, uncredentialed home.

Run under a bounded process lease on shared maintainer machines.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared_context.clients import connection
from shared_context.core import Store
from shared_context.install import setup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openclaw", required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="spc-openclaw-") as directory:
        home = Path(directory)
        state = home / "context"
        manifest = setup(home=home, state=state, clients=[], native=False)
        store = Store(state)
        store.register("demo", str(home))
        store.db.close()
        config = home / "openclaw.json"
        config.write_text(
            json.dumps(
                connection(
                    "openclaw", manifest["launcher"], project="demo", read_only=True
                )["configuration"]
            )
        )
        env = {
            "HOME": str(home),
            "PATH": os.environ["PATH"],
            "TMPDIR": os.environ["TMPDIR"],
            "OPENCLAW_STATE_DIR": str(home / "oc-state"),
            "OPENCLAW_CONFIG_PATH": str(config),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_DATA_HOME": str(home / ".local/share"),
        }
        result = subprocess.run(
            [args.openclaw, "mcp", "probe", "shared-project-context", "--json"],
            cwd=home,
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode:
            raise RuntimeError(result.stderr[-2000:] + result.stdout[-2000:])
        packet = json.loads(result.stdout)
        server = packet["servers"]["shared-project-context"]
        expected = {
            "shared-project-context__project_context",
            "shared-project-context__project_list",
            "shared-project-context__project_read_reference",
        }
        assert server["tools"] == 3 and expected <= set(packet["tools"])
        assert server["resources"] and server["prompts"] and not packet["diagnostics"]
        version = subprocess.run(
            [args.openclaw, "--version"],
            env=env,
            cwd=home,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout.strip()
        print(
            json.dumps(
                {
                    "runtime": version,
                    "native_mcp_discovery": True,
                    "scoped_read_only_tools": True,
                    "resources_and_prompts": True,
                    "model_inference_calls": 0,
                    "live_gateway_changed": False,
                    "pass": True,
                },
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
