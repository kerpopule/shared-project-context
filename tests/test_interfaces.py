import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class InterfaceTest(unittest.TestCase):
    def test_cli_and_mcp_share_state_and_errors(self):
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "SHARED_CONTEXT_HOME": str(Path(d) / "state")}

            def call(operation, args):
                p = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "shared_context",
                        "call",
                        operation,
                        json.dumps(args),
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
                return json.loads(p.stdout)

            call("register", {"project": "demo", "workspace": d})
            frames = [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "fixture", "version": "1"},
                    },
                },
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "project_checkpoint",
                        "arguments": {
                            "project": "demo",
                            "actor": "codex",
                            "expected_revision": 0,
                            "key": "codex-1",
                            "summary": "checkpoint from MCP",
                            "status": "implemented",
                        },
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "project_context",
                        "arguments": {"project": "missing"},
                    },
                },
            ]
            p = subprocess.run(
                [sys.executable, "-m", "shared_context", "serve"],
                env=env,
                input="\n".join(json.dumps(x) for x in frames) + "\n",
                text=True,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            out = [json.loads(line) for line in p.stdout.splitlines()]
            self.assertEqual(len(out), 4)
            self.assertIn("instructions", out[0]["result"])
            self.assertEqual(len(out[1]["result"]["tools"]), 8)
            self.assertFalse(out[2]["result"]["isError"])
            self.assertTrue(out[3]["result"]["isError"])
            self.assertEqual(
                call("context", {"project": "demo"})["events"][0]["actor"], "codex"
            )
            unknown = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "shared_context",
                    "call",
                    "delete-everything",
                    "{}",
                ],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(unknown.returncode, 0)
            self.assertEqual(json.loads(unknown.stdout)["error"], "unknown_operation")
