import tempfile
import unittest
from pathlib import Path
from shared_context.core import Store, ContextError


class KnowledgeTest(unittest.TestCase):
    def test_reference_directory_pagination_has_no_omissions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            notes = root / "notes"
            notes.mkdir()
            for i in range(105):
                (notes / f"note-{i:03}.md").write_text("synthetic")
            store = Store(root / "state")
            store.register("demo", d)
            store.reference("demo", label="notes", path=str(notes), kind="context")
            first = store.read_reference("demo", label="notes")
            second = store.read_reference(
                "demo", label="notes", offset=first["next_offset"]
            )
            collected = first["entries"] + second["entries"]
            self.assertEqual(len(collected), 105)
            self.assertEqual(len(set(collected)), 105)
            self.assertTrue(first["has_more"])
            self.assertFalse(second["has_more"])
            self.assertFalse(second["scan_truncated"])

    def test_reference_reader_is_bounded_and_cannot_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            notes = root / "notes"
            notes.mkdir()
            (notes / "current.md").write_text("Current decision: alpha")
            (root / "private.md").write_text("do not read")
            (notes / "escape.md").symlink_to(root / "private.md")
            (notes / ".env.md").write_text("sensitive")
            s = Store(root / "state")
            s.register("demo", d)
            s.reference("demo", label="Notes", path=str(notes), kind="context")
            self.assertEqual(
                s.read_reference("demo", label="Notes", relative="current.md")[
                    "content"
                ],
                "Current decision: alpha",
            )
            for name in ("../private.md", "escape.md", ".env.md"):
                with self.assertRaises(ContextError):
                    s.read_reference("demo", label="Notes", relative=name)
            self.assertIn(
                "current.md", s.read_reference("demo", label="Notes")["entries"]
            )

    def test_canonical_references_and_explicit_export(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            note = root / "decision.md"
            note.write_text("private fixture decision")
            s = Store(root / "state")
            s.register("demo", d)
            s.reference("demo", label="Project notes", path=str(note), kind="context")
            packet = s.context("demo")
            self.assertEqual(packet["references"][0]["path"], str(note.resolve()))
            self.assertNotIn("private fixture decision", str(packet))
            out = s.export("demo")
            self.assertEqual(out["schema"], 1)
            self.assertEqual(out["references"], packet["references"])
            with self.assertRaisesRegex(ContextError, "sensitive_reference"):
                s.reference(
                    "demo", label="secret", path=str(root / ".env"), kind="context"
                )
