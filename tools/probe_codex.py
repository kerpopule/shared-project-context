"""Qualify the official Codex app-server's MCP transport without a model turn."""

import json
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared_context.install import setup, native_environment
from shared_context.core import Store


def main():
    with tempfile.TemporaryDirectory(prefix="shared-context-codex-") as d:
        home = Path(d).resolve()
        (home / ".codex").mkdir()
        setup(home=home, state=home / "state", clients=["codex"])
        s = Store(home / "state")
        s.register("canary", str(home), aliases=["canary"])
        s.checkpoint(
            "canary",
            actor="fixture-cli",
            expected_revision=0,
            key="one",
            summary="Canary initialized",
            status="proposed",
            decisions=[{"id": "format", "text": "Use CSV for the synthetic canary."}],
        )
        s.db.close()
        env = native_environment(home)
        p = subprocess.Popen(
            ["codex", "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
            bufsize=1,
        )
        selector = selectors.DefaultSelector()
        selector.register(p.stdout, selectors.EVENT_READ)
        counter = 0

        def request(method, params):
            nonlocal counter
            counter += 1
            p.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": counter,
                        "method": method,
                        "params": params,
                    }
                )
                + "\n"
            )
            p.stdin.flush()
            deadline = time.monotonic() + 50
            while time.monotonic() < deadline:
                if not selector.select(max(0.01, deadline - time.monotonic())):
                    break
                line = p.stdout.readline()
                if not line:
                    break
                packet = json.loads(line)
                if packet.get("id") == counter:
                    if "error" in packet:
                        raise RuntimeError(method + ":" + str(packet["error"]))
                    return packet["result"]
            raise RuntimeError("app_server_timeout:" + method)

        try:
            request(
                "initialize",
                {
                    "clientInfo": {"name": "shared-context-canary", "version": "0.1.0"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            p.stdin.write(
                json.dumps({"jsonrpc": "2.0", "method": "initialized"}) + "\n"
            )
            p.stdin.flush()
            inventory = request(
                "mcpServerStatus/list",
                {"serverName": "shared-project-context", "limit": 10},
            )
            server = next(
                row
                for row in inventory["data"]
                if row["name"] == "shared-project-context"
            )
            names = sorted(server["tools"])
            assert (
                "project_context" in names
                and "project_checkpoint" in names
                and len(names) == 8
            ), names
            thread = request(
                "thread/start",
                {"cwd": str(home), "ephemeral": True, "approvalPolicy": "never"},
            )
            thread_id = thread["thread"]["id"]
            request(
                "mcpServer/tool/call",
                {
                    "server": "shared-project-context",
                    "threadId": thread_id,
                    "tool": "project_context",
                    "arguments": {"project": "canary"},
                },
            )
            request(
                "mcpServer/tool/call",
                {
                    "server": "shared-project-context",
                    "threadId": thread_id,
                    "tool": "project_checkpoint",
                    "arguments": {
                        "project": "canary",
                        "actor": "codex-appserver-canary",
                        "expected_revision": 1,
                        "key": "codex-appserver",
                        "summary": "Native Codex MCP consumer recorded a synthetic decision",
                        "status": "proposed",
                        "decisions": [
                            {
                                "id": "format-new",
                                "text": "Use JSON for the synthetic canary.",
                                "supersedes": "format",
                            }
                        ],
                    },
                },
            )
            resumed = Store(home / "state").context("canary")
            assert (
                resumed["revision"] == 2
                and resumed["decisions"][0]["id"] == "format-new"
            ), resumed
            print(
                json.dumps(
                    {
                        "codex_app_server_initialize": True,
                        "mcp_server_discovered": True,
                        "tools_discovered": names,
                        "native_tool_read_and_write": True,
                        "resumed_decision": resumed["decisions"][0]["text"],
                        "model_turn_run": False,
                    },
                    indent=2,
                )
            )
        finally:
            selector.close()
            p.stdin.close()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=5)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
