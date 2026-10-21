import json
from pathlib import Path
import tempfile
import unittest


class UniversalClientTest(unittest.TestCase):
    def test_custom_opencode_precedence_is_refused_without_writing_config(self):
        from unittest.mock import patch
        from shared_context.install import setup, InstallError

        for key in (
            "OPENCODE_CONFIG",
            "OPENCODE_CONFIG_CONTENT",
            "OPENCODE_CONFIG_DIR",
        ):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                with (
                    patch("pathlib.Path.home", return_value=home),
                    patch.dict("os.environ", {key: "custom-value"}, clear=True),
                ):
                    with self.assertRaisesRegex(InstallError, "config_precedence"):
                        setup(home=home, state=home / "state", clients=["opencode"])
                self.assertFalse((home / ".config/opencode/opencode.json").exists())
                self.assertFalse((home / "state/bin/shared-context").exists())

    def test_private_ssh_recipe_quotes_remote_command_and_never_forwards_credentials(
        self,
    ):
        import shlex
        from shared_context.clients import connection
        from shared_context.install import InstallError

        launcher = "/srv/project context/shared-context"
        result = connection(
            "grok-bot", launcher, project="demo", read_only=True, ssh="context-host"
        )
        server = result["server"]
        self.assertEqual(server["command"], "ssh")
        self.assertIn("ForwardAgent=no", server["args"])
        self.assertIn("StrictHostKeyChecking=yes", server["args"])
        self.assertEqual(
            shlex.split(server["args"][-1]),
            [launcher, "serve", "--project", "demo", "--read-only"],
        )
        for target in ("-oProxyCommand=bad", "host;command", "user host"):
            with self.assertRaises(InstallError):
                connection("generic", launcher, project="demo", ssh=target)
        with self.assertRaises(InstallError):
            connection("generic", launcher, ssh="context-host")

    def test_explicit_reactivation_retains_data_and_reinstalls_owned_connections(self):
        from shared_context.install import setup, uninstall, InstallError
        from shared_context.core import Store

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            state = home / "state"
            setup(home=home, state=state, clients=["pi"])
            store = Store(state)
            store.register("demo", directory)
            store.db.close()
            uninstall(home=home, state=state)
            self.assertFalse(uninstall(home=home, state=state)["active"])
            with self.assertRaisesRegex(InstallError, "disabled"):
                setup(home=home, state=state, clients=["pi"])
            second = setup(home=home, state=state, clients=["pi"], reactivate=True)
            self.assertEqual(second["native"], ["pi"])
            store = Store(state)
            self.assertEqual(store.context("demo")["revision"], 0)
            store.db.close()

    def test_modified_connection_blocks_uninstall_before_removing_instructions(self):
        from shared_context.install import setup, uninstall, InstallError

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            state = home / "state"
            manifest = setup(home=home, state=state, clients=["pi"])
            instructions = Path(manifest["instructions"]["pi"])
            before = instructions.read_text()
            path = Path(manifest["connections"]["pi"]["path"])
            config = json.loads(path.read_text())
            config["mcpServers"]["shared-project-context"]["command"] = "/user/changed"
            path.write_text(json.dumps(config))
            with self.assertRaises(InstallError):
                uninstall(home=home, state=state)
            self.assertEqual(instructions.read_text(), before)

    def test_connection_tampering_is_detected_without_native_processes(self):
        from shared_context.install import setup
        from shared_context.health import doctor

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            state = home / "state"
            manifest = setup(home=home, state=state, clients=["pi"])
            owned = manifest["connections"]["pi"]
            config = json.loads(Path(owned["path"]).read_text())
            config["mcpServers"]["shared-project-context"]["args"] = ["changed"]
            Path(owned["path"]).write_text(json.dumps(config))
            self.assertFalse(doctor(state, native=False)["ok"])

    def test_gemini_hook_refreshes_context(self):
        import subprocess
        from shared_context.core import Store
        from shared_context.install import setup

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            state = home / "context"
            manifest = setup(home=home, state=state, clients=["gemini"])
            store = Store(state)
            store.register("demo", str(home))
            store.checkpoint(
                "demo",
                actor="fixture",
                expected_revision=0,
                key="latest",
                summary="Fresh project decision",
                status="proposed",
            )
            store.db.close()
            result = subprocess.run(
                [manifest["launcher"], "hook", "--client", "gemini"],
                input=json.dumps({"cwd": str(home), "prompt": "continue demo"}),
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)["hookSpecificOutput"]
            self.assertEqual(output["hookEventName"], "BeforeAgent")
            self.assertIn("Fresh project decision", output["additionalContext"])

    def test_cli_connection_is_non_mutating_and_machine_readable(self):
        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "shared_context",
                "connect",
                "--client",
                "opencode",
                "--launcher",
                "/opt/shared-context",
                "--project",
                "demo",
                "--read-only",
            ],
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(
            value["configuration"]["mcp"]["shared-project-context"]["command"],
            ["/opt/shared-context", "serve", "--project", "demo", "--read-only"],
        )

    def test_setup_upgrade_uninstall_new_local_clients(self):
        from shared_context.install import setup, uninstall
        from shared_context.health import doctor
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            state = home / "state"
            clients = ["gemini", "pi", "opencode"]
            with patch.dict("os.environ", {}, clear=True):
                first = setup(home=home, state=state, clients=clients)
                self.assertEqual(set(first["native"]), set(clients))
                for client in clients:
                    receipt = first["connections"][client]
                    self.assertTrue(Path(receipt["path"]).exists())
                    self.assertIn(first["launcher"], Path(receipt["path"]).read_text())
                second = setup(home=home, state=state, clients=clients)
                self.assertEqual(first["code_hash"], second["code_hash"])
                self.assertTrue(doctor(state, native=False)["ok"])
                uninstall(home=home, state=state)
                for client in clients:
                    self.assertNotIn(
                        "shared-project-context",
                        Path(first["connections"][client]["path"]).read_text(),
                    )

    def test_client_recipes_use_real_distinct_config_shapes(self):
        from shared_context.clients import connection

        launcher = "/opt/My Agents/shared-context"
        for client in (
            "gemini",
            "pi",
            "cursor",
            "claude-desktop",
            "generic",
            "opencode",
            "openclaw",
            "vscode",
            "grok-bot",
            "dots",
        ):
            with self.subTest(client=client):
                result = connection(client, launcher, project="example", read_only=True)
                self.assertEqual(result["client"], client)
                self.assertFalse(result["verified_in_vendor_runtime"])
                self.assertIn("--project", result["server"]["args"])
                self.assertIn("--read-only", result["server"]["args"])
                self.assertEqual(result["server"]["command"], launcher)
                if client == "opencode":
                    self.assertEqual(
                        result["configuration"]["mcp"]["shared-project-context"][
                            "command"
                        ][0],
                        launcher,
                    )
                    self.assertEqual(
                        result["configuration"]["mcp"]["shared-project-context"][
                            "type"
                        ],
                        "local",
                    )
                elif client == "openclaw":
                    self.assertIn(
                        "shared-project-context",
                        result["configuration"]["mcp"]["servers"],
                    )
                elif client == "vscode":
                    self.assertEqual(
                        result["configuration"]["servers"]["shared-project-context"][
                            "type"
                        ],
                        "stdio",
                    )
                elif client in {"grok-bot", "dots"}:
                    self.assertIsNone(result["configuration"])
                    self.assertTrue(result["requirements"])
                else:
                    self.assertIn(
                        "shared-project-context", result["configuration"]["mcpServers"]
                    )
        with self.assertRaisesRegex(ValueError, "unknown_client"):
            connection("imaginary", launcher)

    def test_owned_json_entry_preserves_other_settings_and_refuses_tampering(self):
        from shared_context.clients import manage_json_entry

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "settings.json"
            initial = {
                "theme": "my-theme",
                "mcpServers": {"my-tools": {"command": "keep"}},
            }
            target.write_text(json.dumps(initial))
            keys = ["mcpServers", "shared-project-context"]
            entry = {"command": "/opt/shared-context", "args": ["serve"]}
            receipt = manage_json_entry(target, keys, entry)
            manage_json_entry(target, keys, entry, previous=receipt)
            self.assertEqual(json.loads(target.read_text())["theme"], "my-theme")
            self.assertEqual(
                json.loads(target.read_text())["mcpServers"]["my-tools"],
                {"command": "keep"},
            )
            changed = json.loads(target.read_text())
            changed["mcpServers"]["shared-project-context"]["command"] = "user-edit"
            target.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "managed_connection_modified"):
                manage_json_entry(target, keys, entry, previous=receipt)
            target.write_text(
                json.dumps(
                    {
                        **initial,
                        "mcpServers": {
                            **initial["mcpServers"],
                            "shared-project-context": entry,
                        },
                    }
                )
            )
            manage_json_entry(target, keys, None, previous=receipt)
            self.assertEqual(json.loads(target.read_text()), initial)
            target.write_text(
                json.dumps({"mcpServers": {"shared-project-context": entry}})
            )
            with self.assertRaisesRegex(ValueError, "connection_name_unowned"):
                manage_json_entry(target, keys, entry)
