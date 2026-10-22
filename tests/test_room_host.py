import json
from pathlib import Path
import tempfile
import unittest

from shared_context.core import Store, ContextError


class RoomHostTest(unittest.TestCase):
    def test_explicit_grant_reads_fresh_context_only_for_bound_member(self):
        from shared_context.room_host import room_context

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            store = Store(state)
            store.register("demo", directory)
            config = root / "rooms.json"
            config.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "state": str(state),
                        "rooms": [
                            {
                                "host": "coagent",
                                "room": "room1",
                                "project": "demo",
                                "members": ["member1"],
                            }
                        ],
                    }
                )
            )
            config.chmod(0o600)
            args = (config, "coagent", "room1", "member1", "session1")
            first = room_context(*args)
            self.assertEqual(first["packet"]["context"]["revision"], 0)
            store.checkpoint(
                "demo",
                actor="external-cli",
                expected_revision=0,
                key="external",
                summary="Use manual exports",
                status="tested",
                evidence=["synthetic fixture"],
            )
            second = room_context(*args)
            self.assertEqual(second["packet"]["context"]["revision"], 1)
            self.assertIn("Use manual exports", second["context"])
            self.assertTrue(second["packet"]["authority"]["read_only"])
            self.assertFalse(second["packet"]["authority"]["grants_approval"])
            with self.assertRaisesRegex(ContextError, "room_member_not_granted"):
                room_context(config, "coagent", "room1", "intruder", "session1")
            self.assertFalse(
                room_context(config, "hermes", "room1", "member1", "session1")[
                    "enabled"
                ]
            )
            store.db.close()

    def test_untrusted_config_is_rejected_before_reading_state(self):
        from shared_context.room_host import room_context

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "config.json"
            value = {"version": 1, "state": str(root / "not-created"), "rooms": []}
            file.write_text(json.dumps(value))
            file.chmod(0o644)
            with self.assertRaisesRegex(ContextError, "owner_private"):
                room_context(file, "coagent", "room", "member", "session")
            file.chmod(0o600)
            link = root / "link.json"
            link.symlink_to(file)
            with self.assertRaises(OSError):
                room_context(link, "coagent", "room", "member", "session")
            value["rooms"] = [
                {
                    "host": "coagent",
                    "room": "room",
                    "project": "demo",
                    "members": ["member"],
                }
            ] * 2
            file.write_text(json.dumps(value))
            with self.assertRaisesRegex(ContextError, "duplicate_room_grant"):
                room_context(file, "coagent", "room", "member", "session")
            self.assertFalse((root / "not-created").exists())

    def test_command_is_machine_readable_and_rejects_missing_grant_members(self):
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            store = Store(state)
            store.register("demo", directory)
            store.db.close()
            file = root / "config.json"
            file.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "state": str(state),
                        "rooms": [
                            {
                                "host": "hermes",
                                "room": "room",
                                "project": "demo",
                                "members": ["member"],
                            }
                        ],
                    }
                )
            )
            file.chmod(0o600)
            command = [
                sys.executable,
                "-m",
                "shared_context",
                "room-context",
                "--config",
                str(file),
                "--host",
                "hermes",
                "--room",
                "room",
                "--session",
                "session",
                "--member",
            ]
            result = subprocess.run(
                command + ["member"], capture_output=True, text=True, check=True
            )
            packet = json.loads(result.stdout)
            self.assertTrue(packet["enabled"])
            self.assertEqual(len(packet["scope"]), 64)
            self.assertNotIn("packet", packet)
            denied = subprocess.run(command + ["other"], capture_output=True, text=True)
            self.assertEqual(denied.returncode, 2)
            self.assertEqual(
                json.loads(denied.stdout)["error"], "room_member_not_granted"
            )
