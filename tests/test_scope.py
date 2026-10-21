import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from shared_context.core import Store

ROOT = Path(__file__).resolve().parents[1]


class ScopedTransportTest(unittest.TestCase):
    def test_empty_scope_and_spoofed_identity_fail_closed(self):
        from shared_context.scope import Scope
        from shared_context.core import ContextError
        from unittest.mock import patch

        for value in ("", 7, True, "contains\ncontrol"):
            with self.assertRaises(ContextError):
                Scope(value)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            store = Store(state)
            store.register("alpha", directory)
            with patch.dict(os.environ, {"SHARED_CONTEXT_HOME": str(state)}):
                scope = Scope("alpha", actor="trusted-host", session="turn-1")
                for actor, session in [
                    ("spoofed", "turn-1"),
                    ("trusted-host", "spoofed"),
                ]:
                    with self.assertRaisesRegex(
                        ContextError, "identity_binding_mismatch"
                    ):
                        scope.call(
                            "begin",
                            {"project": "alpha", "actor": actor, "session": session},
                        )
                scope.call("begin", {"project": "alpha"})
                scope.call("finish", {"project": "alpha"})
            store.db.close()

    def test_standard_resources_prompts_and_current_protocol_obey_scope(self):
        from shared_context.mcp import respond
        from shared_context.scope import Scope

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            store = Store(state)
            store.register("alpha", str(root))
            store.db.close()
            from unittest.mock import patch

            with patch.dict(os.environ, {"SHARED_CONTEXT_HOME": str(state)}):
                scope = Scope("alpha", True)

                def request(method, params=None):
                    return respond(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": method,
                            "params": params or {},
                        },
                        scope,
                    )

                init = request("initialize", {"protocolVersion": "2025-11-25"})[
                    "result"
                ]
                self.assertEqual(init["protocolVersion"], "2025-11-25")
                self.assertIn("resources", init["capabilities"])
                self.assertIn("prompts", init["capabilities"])
                self.assertEqual(
                    len(request("resources/list")["result"]["resources"]), 1
                )
                value = request(
                    "resources/read", {"uri": "shared-context://projects/alpha"}
                )
                self.assertEqual(
                    json.loads(value["result"]["contents"][0]["text"])["project"],
                    "alpha",
                )
                denied = request(
                    "resources/read", {"uri": "shared-context://projects/private"}
                )
                self.assertEqual(denied["error"]["message"], "project_not_available")
                prompt = request(
                    "prompts/get",
                    {"name": "resume-project", "arguments": {"project": "alpha"}},
                )
                self.assertIn(
                    "alpha", prompt["result"]["messages"][0]["content"]["text"]
                )

    def test_scoped_stdio_never_discovers_or_reads_other_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root / "state")
            for name in ("alpha", "private-other"):
                (root / name).mkdir()
                store.register(name, str(root / name))
            store.db.close()
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "project_list", "arguments": {}},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "project_context",
                        "arguments": {"project": "private-other"},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "project_context",
                        "arguments": {"project": "alpha"},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "project_begin",
                        "arguments": {"project": "alpha", "actor": "x", "session": "y"},
                    },
                },
            ]
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "shared_context",
                    "serve",
                    "--project",
                    "alpha",
                    "--read-only",
                ],
                input="".join(json.dumps(r) + "\n" for r in requests),
                text=True,
                capture_output=True,
                timeout=15,
                cwd=ROOT,
                env={**os.environ, "SHARED_CONTEXT_HOME": str(root / "state")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(rows), 5)
            names = {t["name"] for t in rows[0]["result"]["tools"]}
            self.assertEqual(
                names, {"project_list", "project_context", "project_read_reference"}
            )
            listing = json.loads(rows[1]["result"]["content"][0]["text"])
            self.assertEqual([p["id"] for p in listing["projects"]], ["alpha"])
            self.assertTrue(rows[2]["result"]["isError"])
            self.assertEqual(
                json.loads(rows[2]["result"]["content"][0]["text"]),
                {"error": "project_not_available"},
            )
            self.assertFalse(rows[3]["result"]["isError"])
            self.assertTrue(rows[4]["result"]["isError"])
