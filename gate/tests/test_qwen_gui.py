"""Offline contracts for the supervised Qwen Code VS Code interface."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "qwen_gui_under_test", ROOT / "scripts/qwen_gui.py"
)
import sys

sys.path.insert(0, str(ROOT / "scripts"))
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)


class QwenGuiContracts(unittest.TestCase):
    def test_extension_must_match_reviewed_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            with patch.object(gui.subprocess, "run") as command:
                command.return_value = MagicMock(
                    returncode=0,
                    stdout=f"{gui.EXTENSION}@{gui.VERSION}\n",
                )
                self.assertTrue(gui.installed_extension("code", profile, profile))
                command.return_value.stdout = f"{gui.EXTENSION}@0.0.1\n"
                with self.assertRaisesRegex(ValueError, "differs"):
                    gui.installed_extension("code", profile, profile)

    def test_gui_inherits_bridge_token_and_closes_hold_on_window_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            project = prefix / "project"
            project.mkdir()
            settings = {
                "python": "/synthetic/python",
                "private_lead": {"alias": "synthetic-model", "local_port": 18002},
            }
            child = MagicMock()
            child.wait.return_value = 0
            child.poll.return_value = 0
            server = MagicMock()
            hold = MagicMock()
            thread = MagicMock()
            with (
                patch.object(gui.bridge, "installed_settings", return_value=settings),
                patch.object(gui, "code_binary", return_value="/synthetic/code"),
                patch.object(gui, "installed_extension", return_value=True),
                patch.object(gui.bridge, "configure_qwen"),
                patch.object(
                    gui.subprocess, "run", return_value=MagicMock(returncode=0)
                ),
                patch.object(gui.subprocess, "Popen", return_value=child) as popen,
                patch.object(gui.bridge, "ModelHold", return_value=hold),
                patch.object(gui.bridge, "ModelServer", return_value=server),
                patch.object(gui.threading, "Thread", return_value=thread),
            ):
                self.assertEqual(gui.run(prefix, project), 0)
            command = popen.call_args.args[0]
            environment = popen.call_args.kwargs["env"]
            self.assertEqual(command[0], "/synthetic/code")
            self.assertIn("--wait", command)
            self.assertIn("--new-window", command)
            self.assertEqual(command[-1], str(project.resolve()))
            self.assertTrue(environment["SANCTUM_QWEN_LOCAL_KEY"])
            self.assertEqual(environment["QWEN_CODE_DISABLE_TELEMETRY"], "1")
            hold.ensure_ready.assert_not_called()
            hold.close.assert_called_once()
            server.shutdown.assert_called_once()

    def test_installer_disables_extension_updates_in_private_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / "receipt.json").write_text(json.dumps({"source": str(ROOT)}))
            with (
                patch.object(
                    gui.bridge,
                    "installed_settings",
                    return_value={"python": "/synthetic/python"},
                ),
                patch.object(gui, "code_binary", return_value="/synthetic/code"),
                patch.object(gui, "installed_extension", return_value=True),
                patch.object(gui.Path, "home", return_value=prefix),
            ):
                launcher = gui.install(prefix)
            settings = json.loads(
                (prefix / "qwen-gui/user-data/User/settings.json").read_text()
            )
            self.assertIs(settings["extensions.autoUpdate"], False)
            self.assertIs(settings["extensions.autoCheckUpdates"], False)
            self.assertEqual(launcher.name, "qwen-gui")


if __name__ == "__main__":
    unittest.main()
