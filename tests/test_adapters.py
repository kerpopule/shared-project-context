import json
import tempfile
import unittest
from pathlib import Path


class AdapterTest(unittest.TestCase):
    def test_hermes_tools_and_per_turn_context_use_current_state(self):
        from shared_context.core import Store
        from shared_context.hermes_adapter import register

        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / "state"
            s = Store(state)
            s.register("demo", d)

            class Context:
                tools = {}
                hooks = {}

                def register_tool(self, **kwargs):
                    self.tools[kwargs["name"]] = kwargs

                def register_hook(self, name, fn):
                    self.hooks[name] = fn

            ctx = Context()
            register(ctx, state=state)
            self.assertEqual(len(ctx.tools), 8)
            hook = ctx.hooks["pre_llm_call"]
            before = hook(session_id="s", user_message="continue demo")
            self.assertIn("Shared project continuity", before["context"])
            tool = ctx.tools["project_checkpoint"]["handler"]
            result = json.loads(
                tool(
                    {
                        "project": "demo",
                        "actor": "codex",
                        "expected_revision": 0,
                        "key": "one",
                        "summary": "new decision",
                        "status": "proposed",
                        "decisions": [{"id": "x", "text": "CSV first"}],
                    }
                )
            )
            self.assertEqual(result["revision"], 1)
            after = hook(session_id="s", user_message="continue demo")
            self.assertIn("CSV first", after["context"])
            self.assertIn('"revision": 1', after["context"])
