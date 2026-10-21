import tempfile
from pathlib import Path
import unittest

from shared_context.core import Store, ContextError


class RoomBridgeTest(unittest.TestCase):
    def test_stale_room_cursor_is_not_silently_complete_and_failed_work_stays_failed(
        self,
    ):
        from shared_context.rooms import RoomBinding

        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "state")
            store.register("demo", directory)
            for revision in range(12):
                store.checkpoint(
                    "demo",
                    actor="fixture",
                    expected_revision=revision,
                    key=str(revision),
                    summary="fixture update",
                    status="failed",
                )
            binding = RoomBinding("room", "member", "session", "demo")
            packet = binding.packet(store, since_revision=0)
            self.assertTrue(packet["cursor"]["history_gap"])
            self.assertEqual(packet["context"]["events"][-1]["status"], "failed")
            with self.assertRaisesRegex(ContextError, "packet_too_large"):
                binding.packet(store, max_bytes=1024)
            with self.assertRaisesRegex(ContextError, "cursor_ahead"):
                binding.packet(store, since_revision=100)
            store.db.close()

    def test_room_turns_share_project_truth_not_private_transcripts_or_authority(self):
        from shared_context.rooms import RoomBinding

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root / "state")
            store.register("demo", str(root))
            first = RoomBinding(
                "room-one", "member-alpha", "turn-session", "demo", read_only=False
            )
            scope = first.scope()
            begin = scope.call("begin", {"project": "demo"}, store)
            self.assertEqual(begin["project"], "demo")
            scope.call(
                "checkpoint",
                {
                    "project": "demo",
                    "expected_revision": 0,
                    "key": "room-checkpoint",
                    "summary": "Keep manual exports",
                    "status": "proposed",
                    "decisions": [
                        {"id": "export-policy", "text": "Manual exports only"}
                    ],
                },
                store,
            )
            other = RoomBinding("room-two", "member-beta", "session-two", "demo")
            packet = other.packet(store, since_revision=0)
            self.assertEqual(packet["context"]["revision"], 1)
            self.assertEqual(
                packet["context"]["decisions"][0]["text"], "Manual exports only"
            )
            self.assertFalse(packet["authority"]["may_orchestrate"])
            self.assertFalse(packet["authority"]["grants_approval"])
            self.assertEqual(packet["binding"]["room"], "room-two")
            self.assertEqual(packet["binding"]["member"], "member-beta")
            self.assertNotIn("messages", packet)
            self.assertNotIn("transcript", packet)
            with self.assertRaisesRegex(ContextError, "operation_not_available"):
                other.scope().call("begin", {"project": "demo"}, store)
            with self.assertRaisesRegex(ContextError, "identity_binding_mismatch"):
                scope.call(
                    "finish",
                    {"project": "demo", "actor": "forged", "session": "forged"},
                    store,
                )
            with self.assertRaisesRegex(ContextError, "room_cursor_ahead"):
                other.packet(store, since_revision=2)
            store.db.close()
