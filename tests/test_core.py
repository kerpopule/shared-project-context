import tempfile
import unittest
from pathlib import Path


class ContinuityTest(unittest.TestCase):
    def test_cross_actor_decision_round_trip(self):
        from shared_context.core import Store

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            project = root / "project"
            project.mkdir()
            store = Store(root / "state")
            store.register("demo", str(project), aliases=["Demo App"])
            packet = store.context("Demo App")
            self.assertEqual(packet["revision"], 0)
            event = store.checkpoint(
                "demo",
                actor="hermes",
                expected_revision=0,
                key="first",
                summary="Use CSV imports",
                status="proposed",
                decisions=[{"id": "import", "text": "CSV first"}],
            )
            self.assertEqual(event["revision"], 1)
            resumed = Store(root / "state").context(str(project))
            self.assertEqual(resumed["decisions"][0]["text"], "CSV first")
            self.assertEqual(resumed["events"][0]["actor"], "hermes")

    def test_retry_conflict_validation_and_supersession(self):
        from shared_context.core import Store, ContextError

        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "state")
            s.register("demo", d)
            args = dict(
                actor="claude",
                expected_revision=0,
                key="one",
                summary="first",
                status="tested",
                decisions=[{"id": "a", "text": "old"}],
                evidence=["unittest: PASS"],
                next_action="implement",
            )
            first = s.checkpoint("demo", **args)
            self.assertEqual(s.checkpoint("demo", **args), first)
            with self.assertRaisesRegex(ContextError, "idempotency_conflict"):
                s.checkpoint("demo", **{**args, "summary": "different"})
            with self.assertRaisesRegex(ContextError, "revision_conflict"):
                s.checkpoint("demo", **{**args, "key": "two"})
            with self.assertRaisesRegex(ContextError, "explicit_supersession_required"):
                s.checkpoint(
                    "demo",
                    **{
                        **args,
                        "key": "two",
                        "expected_revision": 1,
                        "decisions": [{"id": "a", "text": "new"}],
                    },
                )
            second = s.checkpoint(
                "demo",
                **{
                    **args,
                    "key": "two",
                    "expected_revision": 1,
                    "decisions": [{"id": "b", "text": "new", "supersedes": "a"}],
                },
            )
            self.assertEqual(second["revision"], 2)
            self.assertEqual([x["id"] for x in s.context("demo")["decisions"]], ["b"])
            for bad in ("deployed", "nonsense"):
                with self.assertRaisesRegex(ContextError, "invalid_status"):
                    s.checkpoint("demo", **{**args, "key": bad, "status": bad})
            with self.assertRaisesRegex(ContextError, "evidence_required"):
                s.checkpoint(
                    "demo",
                    **{**args, "key": "bad", "expected_revision": 2, "evidence": []},
                )


if __name__ == "__main__":
    unittest.main()
