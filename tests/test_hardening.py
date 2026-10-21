import concurrent.futures
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from shared_context.core import Store, ContextError
from shared_context.workspace import snapshot


class HardeningTest(unittest.TestCase):
    def test_concurrent_receipts_are_serialized(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            state = root / "state"
            Store(state).register("demo", d)

            def write(n):
                s = Store(state)
                try:
                    return s.checkpoint(
                        "demo",
                        actor="tool",
                        expected_revision=0,
                        key=str(n),
                        summary="change",
                        status="proposed",
                    )["revision"]
                except ContextError as e:
                    return str(e)
                finally:
                    s.db.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(write, range(4)))
            self.assertEqual(results.count(1), 1)
            self.assertEqual(results.count("revision_conflict"), 3)

    def test_old_superseded_decision_ids_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "state")
            s.register("demo", d)
            s.checkpoint(
                "demo",
                actor="tool",
                expected_revision=0,
                key="a",
                summary="one",
                status="proposed",
                decisions=[{"id": "a", "text": "old"}],
            )
            s.checkpoint(
                "demo",
                actor="tool",
                expected_revision=1,
                key="b",
                summary="two",
                status="proposed",
                decisions=[{"id": "b", "text": "new", "supersedes": "a"}],
            )
            for n in range(12):
                s.checkpoint(
                    "demo",
                    actor="tool",
                    expected_revision=n + 2,
                    key=str(n),
                    summary="other",
                    status="proposed",
                )
            with self.assertRaisesRegex(ContextError, "explicit_supersession_required"):
                s.checkpoint(
                    "demo",
                    actor="tool",
                    expected_revision=14,
                    key="reuse",
                    summary="reuse",
                    status="proposed",
                    decisions=[{"id": "a", "text": "reused"}],
                )

    def test_unregistered_and_ambiguous_projects(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "state")
            s.register("one", d, aliases=["same"])
            s.register("two", d, aliases=["same"])
            with self.assertRaisesRegex(ContextError, "ambiguous_project"):
                s.context("same")
            with self.assertRaisesRegex(ContextError, "project_not_found"):
                s.context("not-registered")

    def test_malformed_receipts_and_missing_schema_do_not_mutate(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "state")
            s.register("demo", d)
            for updates in (
                {"evidence": [42]},
                {"next_action": {}},
                {"decisions": [{"id": "", "text": ""}]},
                {"decisions": [{"id": "x", "text": "okay", "approval": True}]},
            ):
                with self.assertRaises(ContextError):
                    s.checkpoint(
                        "demo",
                        actor="tool",
                        expected_revision=0,
                        key="a",
                        summary="one",
                        status="proposed",
                        **updates,
                    )
            self.assertEqual(s.context("demo")["revision"], 0)

    def test_future_schema_rejected_without_creating_tables(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "context.sqlite3"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE meta(version INTEGER)")
            conn.execute("INSERT INTO meta VALUES(999)")
            conn.commit()
            conn.close()
            before = db.read_bytes()
            with self.assertRaisesRegex(ContextError, "unsupported_schema"):
                Store(d)
            self.assertEqual(db.read_bytes(), before)

    def test_secret_and_outside_symlink_are_not_hashed(self):
        import subprocess

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            (repo / ".env").write_text("NOT_A_REAL_CREDENTIAL=fixture")
            (root / "outside").mkdir()
            (root / "outside/file").write_text("fixture")
            (repo / "escape").symlink_to(root / "outside", target_is_directory=True)
            snap = snapshot(repo)
            self.assertFalse(snap["complete"])
            self.assertTrue(snap["issues"])
            self.assertNotIn("NOT_A_REAL_CREDENTIAL", json.dumps(snap))
