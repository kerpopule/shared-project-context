"""Install a wheel away from the checkout and exercise setup/state/hook/uninstall.

Requires uv on PATH. The fixture does not change real client configuration.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    with tempfile.TemporaryDirectory(prefix="spc-wheel-") as directory:
        root = Path(directory)
        home = root / "home"
        home.mkdir()
        venv = root / "venv"
        subprocess.run(["uv", "venv", "--python", "3.11", str(venv)], check=True)
        python = venv / "bin/python"
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheel)], check=True
        )
        env = {
            "HOME": str(home),
            "PATH": str(venv / "bin") + os.pathsep + os.environ["PATH"],
            "TMPDIR": os.environ.get("TMPDIR", directory),
            "SHARED_CONTEXT_HOME": str(home / "context"),
        }

        def call(*argv, input=None):
            result = subprocess.run(
                [str(venv / "bin/shared-context"), *argv],
                cwd=root,
                env=env,
                input=input,
                text=True,
                capture_output=True,
                timeout=20,
            )
            assert result.returncode == 0, result.stderr + result.stdout
            return json.loads(result.stdout)

        call("setup", "--clients", "gemini,pi,opencode")
        call(
            "call", "register", json.dumps({"project": "demo", "workspace": str(home)})
        )
        call(
            "call",
            "checkpoint",
            json.dumps(
                {
                    "project": "demo",
                    "actor": "wheel",
                    "expected_revision": 0,
                    "key": "canary",
                    "summary": "Wheel shared context works",
                    "status": "proposed",
                }
            ),
        )
        assert call("call", "context", '{"project":"demo"}')["revision"] == 1
        hook = call("hook", "--client", "gemini", input=json.dumps({"cwd": str(home)}))
        assert (
            "Wheel shared context works"
            in hook["hookSpecificOutput"]["additionalContext"]
        )
        assert call("doctor")["ok"]
        assert (
            call("connect", "--client", "dots", "--project", "demo", "--read-only")[
                "client"
            ]
            == "dots"
        )
        assert call("uninstall")["data_retained"]
        assert (home / "context/context.sqlite3").is_file()
    print(
        json.dumps(
            {
                "wheel_installed_outside_checkout": True,
                "core_round_trip": True,
                "gemini_hook": True,
                "doctor": True,
                "uninstall_keeps_data": True,
                "pass": True,
            }
        )
    )


if __name__ == "__main__":
    main()
