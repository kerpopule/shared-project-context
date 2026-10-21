import tempfile
import unittest
from pathlib import Path


class InstallTest(unittest.TestCase):
    def test_install_is_portable_and_data_survives_reinstall_and_uninstall(self):
        from shared_context.install import setup, uninstall
        from shared_context.core import Store
        import subprocess
        import json

        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / "home"
            home.mkdir()
            state = home / "state"
            target = home / ".codex/AGENTS.md"
            target.parent.mkdir()
            target.write_text("keep this\n")
            result = setup(home=home, state=state, clients=["codex"], native=False)
            launcher = Path(result["launcher"])
            self.assertTrue(launcher.is_file())
            s = Store(state)
            s.register("business", str(home))
            s.checkpoint(
                "business",
                actor="hermes",
                expected_revision=0,
                key="one",
                summary="saved",
                status="proposed",
            )
            setup(home=home, state=state, clients=["codex"], native=False)
            self.assertEqual(
                target.read_text().count("shared-project-context:begin"), 1
            )
            p = subprocess.run(
                [str(launcher), "call", "context", '{"project":"business"}'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=home,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout)["revision"], 1)
            uninstall(home=home, state=state, native=False)
            self.assertEqual(target.read_text(), "keep this\n")
            self.assertEqual(Store(state).context("business")["revision"], 1)

    def test_upgrade_changes_runtime_without_losing_context(self):
        from shared_context.install import setup, InstallError
        from shared_context.core import Store
        from unittest.mock import patch
        import shared_context.install as installer
        import shutil

        with tempfile.TemporaryDirectory() as d:
            home = Path(d).resolve() / "home"
            home.mkdir()
            state = home / "state"
            first = setup(home=home, state=state, clients=["codex"], native=False)
            s = Store(state)
            s.register("demo", str(home))
            s.checkpoint(
                "demo",
                actor="tool",
                expected_revision=0,
                key="before",
                summary="keep",
                status="proposed",
            )
            source = Path(d) / "updated-source"
            source.mkdir()
            for f in Path(installer.__file__).parent.glob("*.py"):
                shutil.copyfile(f, source / f.name)
            (source / "__init__.py").write_text('__version__ = "0.1.1"\n')
            with patch.object(installer, "__file__", str(source / "install.py")):
                second = setup(home=home, state=state, clients=["codex"], native=False)
            self.assertNotEqual(first["runtime"], second["runtime"])
            self.assertTrue(Path(first["runtime"]).exists())
            self.assertEqual(Store(state).context("demo")["revision"], 1)
            launcher = Path(second["launcher"])
            launcher.write_text("user modified launcher")
            with self.assertRaisesRegex(InstallError, "launcher_modified"):
                setup(home=home, state=state, clients=["codex"], native=False)

    def test_claude_hook_preserves_unrelated_hooks(self):
        from shared_context.install import manage_claude_hook
        import json

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            original = {
                "permissions": {"allow": ["Read"]},
                "hooks": {
                    "UserPromptSubmit": [
                        {"hooks": [{"type": "command", "command": "echo keep"}]}
                    ]
                },
            }
            p.write_text(json.dumps(original))
            manage_claude_hook(p, "/safe/shared-context")
            manage_claude_hook(p, "/safe/shared-context")
            result = json.loads(p.read_text())
            self.assertEqual(result["permissions"], original["permissions"])
            self.assertEqual(len(result["hooks"]["UserPromptSubmit"]), 2)
            manage_claude_hook(p, "/safe/shared-context", remove=True)
            self.assertEqual(json.loads(p.read_text()), original)

    def test_managed_block_reinstall_uninstall_and_user_edits(self):
        from shared_context.install import manage_block, InstallError

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "AGENTS.md"
            original = "# My settings\n<!-- other-tool -->\nKeep this\n"
            f.write_text(original)
            manage_block(f, "first rule")
            first = f.read_text()
            manage_block(f, "first rule")
            self.assertEqual(f.read_text(), first)
            manage_block(f, "second rule")
            self.assertIn("second rule", f.read_text())
            self.assertIn(original, f.read_text())
            f.write_text(f.read_text().replace("second rule", "my edit"))
            with self.assertRaisesRegex(InstallError, "managed_block_modified"):
                manage_block(f, "third rule")
            with self.assertRaisesRegex(InstallError, "managed_block_modified"):
                manage_block(f, None)
            f.write_text(first)
            manage_block(f, None)
            self.assertEqual(f.read_text(), original)
