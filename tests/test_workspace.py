import subprocess
import tempfile
import unittest
from pathlib import Path
from shared_context.core import Store, ContextError


class WorkspaceTest(unittest.TestCase):
    def test_dirty_edit_crash_lease_and_linked_worktree(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo = root / "repo"
            repo.mkdir()

            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", str(repo), *args], text=True
                ).strip()

            git("init", "-b", "main")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            (repo / "a.txt").write_text("one")
            git("add", ".")
            git("commit", "-m", "fixture")
            wt = root / "worktree"
            git("worktree", "add", "-b", "second", str(wt))
            s = Store(root / "state")
            s.register("demo", str(repo))
            self.assertEqual(s.context(str(wt))["project"], "demo")
            before = s.context("demo")["snapshot"]["fingerprint"]
            begin = s.begin("demo", actor="claude", session="s1", ttl=60)
            self.assertFalse(begin["drift"])
            with self.assertRaisesRegex(ContextError, "workspace_busy"):
                s.begin("demo", actor="codex", session="s2")
            (repo / "a.txt").write_text("two")
            packet = s.context("demo")
            dirty_first = packet["snapshot"]["fingerprint"]
            self.assertNotEqual(dirty_first, before)
            self.assertTrue(packet["unexplained_drift"])
            (repo / "a.txt").write_text("three")
            self.assertNotEqual(
                s.context("demo")["snapshot"]["fingerprint"], dirty_first
            )
            self.assertEqual(s.context("demo")["leases"][0]["actor"], "claude")
            with self.assertRaisesRegex(ContextError, "lease_not_owned"):
                s.finish("demo", actor="codex", session="s2")
            s.finish("demo", actor="claude", session="s1")
            self.assertEqual(s.context("demo")["leases"], [])
            second = s.begin(str(wt), actor="codex", session="s2")
            self.assertEqual(second["workspace"], str(wt.resolve()))
            s.finish(str(wt), actor="codex", session="s2")

    def test_checkpoint_captures_snapshot_and_rejects_foreign_owner(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init", "-b", "main", str(repo)],
                check=True,
                capture_output=True,
            )
            (repo / "edit.txt").write_text("one")
            s = Store(root / "state")
            s.register("demo", str(repo))
            s.begin("demo", actor="claude", session="owner")
            args = dict(
                actor="codex",
                expected_revision=0,
                key="c",
                summary="changed",
                status="implemented",
            )
            with self.assertRaisesRegex(ContextError, "workspace_busy"):
                s.checkpoint("demo", **args)
            (repo / "edit.txt").write_text("two")
            e = s.checkpoint("demo", **{**args, "actor": "claude", "session": "owner"})
            self.assertIn("snapshot", e)
            self.assertFalse(s.context("demo")["unexplained_drift"])
            (repo / "edit.txt").write_text("three")
            self.assertTrue(s.context("demo")["unexplained_drift"])
            with s.db:
                s.db.execute("UPDATE leases SET expires=0")
            p = s.begin("demo", actor="codex", session="new")
            self.assertTrue(p["expired_previous_owner"])
            self.assertTrue(p["drift"])

    def test_bounds_and_no_git(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "state")
            s.register("business", d, aliases=["business alias"])
            self.assertEqual(s.context("business")["snapshot"]["kind"], "non_git")
            with self.assertRaisesRegex(ContextError, "invalid_ttl"):
                s.begin("business", actor="a", session="s", ttl=999999)
            s.register("other", str(Path(d) / "state"), aliases=["business alias"])
            with self.assertRaisesRegex(ContextError, "ambiguous_project"):
                s.context("business alias")
