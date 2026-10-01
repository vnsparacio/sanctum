from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sanctum_agents.git_control_plane import GitControlPlane
from sanctum_agents.validation import (
    VALIDATION_PROFILES,
    HostValidationRunner,
    ValidationError,
)


class HostValidationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.remote = self.root / "remote.git"
        self.seed = self.root / "seed"
        self.workspaces = self.root / "workspaces"
        self.workspace = self.workspaces / "TTE-14"
        self.git_state = self.root / "git-state"
        self.validation_state = self.root / "validation-state"
        self._run(["git", "init", "--bare", str(self.remote)], self.root)
        self._run(["git", "init", "-b", "v1.3-dev", str(self.seed)], self.root)
        (self.seed / "README.md").write_text("accepted base\n")
        self._run(["git", "add", "README.md"], self.seed)
        self._run(
            [
                "git",
                "-c",
                "user.name=Synthetic",
                "-c",
                "user.email=synthetic@example.invalid",
                "commit",
                "-m",
                "Accepted base",
            ],
            self.seed,
        )
        self._run(["git", "remote", "add", "origin", str(self.remote)], self.seed)
        self._run(["git", "push", "origin", "v1.3-dev"], self.seed)
        self.workspaces.mkdir()
        self._run(
            [
                "git",
                "clone",
                "--branch",
                "v1.3-dev",
                "--single-branch",
                str(self.remote),
                str(self.workspace),
            ],
            self.root,
        )
        GitControlPlane(
            self.workspace,
            self.workspaces,
            self.git_state,
            expected_remote=str(self.remote),
        ).prepare()
        self.runner = HostValidationRunner(
            self.workspace,
            self.workspaces,
            self.git_state,
            self.validation_state,
            expected_remote=str(self.remote),
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _run(arguments, cwd):
        return subprocess.run(
            arguments, cwd=cwd, text=True, capture_output=True, check=True
        )

    def test_profile_is_bounded_receipted_and_idempotent(self):
        calls = []

        def completed(command, _environment):
            calls.append(command.name)
            return {
                "name": command.name,
                "arguments": list(command.arguments),
                "exit_code": 0,
                "timed_out": False,
                "duration_ms": 1,
                "stdout": "",
                "stderr": "",
                "output_truncated": False,
            }

        with patch.object(self.runner, "_run_command", side_effect=completed):
            first = self.runner.run(
                "TTE-14", "TTE-14", "architecture-security", "validation-v1"
            )
            second = self.runner.run(
                "TTE-14", "TTE-14", "architecture-security", "validation-v1"
            )
        self.assertTrue(first["passed"])
        self.assertEqual("already_completed", second["status"])
        self.assertEqual(
            ["process_inspection_preflight"]
            + [item.name for item in VALIDATION_PROFILES["architecture-security"]],
            calls,
        )
        receipt = next((self.validation_state / "receipts").rglob("*.json"))
        self.assertEqual(0o600, receipt.stat().st_mode & 0o777)
        self.assertNotIn("LINEAR_API_KEY", self.runner._environment("TTE-14"))
        self.assertNotIn("GH_TOKEN", self.runner._environment("TTE-14"))

    def test_dependency_caches_are_shared_without_sharing_issue_home(self):
        first = self.runner._environment("TTE-14")
        second = self.runner._environment("TTE-15")

        self.assertNotEqual(first["HOME"], second["HOME"])
        self.assertNotEqual(first["XDG_CACHE_HOME"], second["XDG_CACHE_HOME"])
        shared_cache = self.validation_state / "cache"
        expected = {
            "NPM_CONFIG_CACHE": shared_cache / "npm",
            "UV_CACHE_DIR": shared_cache / "uv",
            "UV_PYTHON_INSTALL_DIR": shared_cache / "uv-python",
        }
        for name, path in expected.items():
            self.assertEqual(str(path), first[name])
            self.assertEqual(first[name], second[name])
            self.assertTrue(path.is_dir())
            self.assertEqual(0o700, path.stat().st_mode & 0o777)

        for environment in (first, second):
            home = Path(environment["HOME"])
            self.assertTrue(home.is_relative_to(self.validation_state / "runtime"))
            self.assertFalse(shared_cache.is_relative_to(home))

    def test_dependency_preflight_creates_missing_environment_with_private_cache(self):
        observed = []

        def setup(command, environment):
            observed.append((command, environment))
            (self.workspace / ".venv").mkdir()
            (self.workspace / "node_modules").mkdir()
            return {"exit_code": 0, "timed_out": False}

        with (
            patch.object(self.runner, "_dependencies_ready", side_effect=[False, True]),
            patch.object(self.runner, "_run_command", side_effect=setup),
        ):
            result = self.runner.preflight_dependencies()
        self.assertTrue(result["passed"])
        self.assertEqual("created", result["state"])
        command, environment = observed[0]
        self.assertEqual(("/usr/bin/make", "deps"), command.arguments)
        self.assertEqual(1500, command.timeout_seconds)
        self.assertEqual(
            str(self.validation_state / "cache" / "uv"), environment["UV_CACHE_DIR"]
        )
        self.assertNotIn("LINEAR_API_KEY", environment)
        receipt_path = next(
            (self.validation_state / "dependency-preflight").rglob("*.json")
        )
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(0o600, receipt_path.stat().st_mode & 0o777)
        self.assertEqual("shared-private-validation", receipt["cache_class"])
        self.assertNotIn(str(self.root), receipt_path.read_text())
        self.assertTrue(self.runner.git.status()["clean"])

    def test_dependency_preflight_retains_existing_environment_on_resume(self):
        (self.workspace / ".venv").mkdir()
        with (
            patch.object(self.runner, "_dependencies_ready", return_value=True),
            patch.object(self.runner, "_run_command") as setup,
        ):
            first = self.runner.preflight_dependencies()
            second = self.runner.preflight_dependencies()
        self.assertEqual("existing", first["state"])
        self.assertEqual("existing", second["state"])
        setup.assert_not_called()
        self.assertTrue((self.workspace / ".venv").exists())

    def test_dependency_preflight_ignores_unwritable_default_cache(self):
        with (
            patch.dict("os.environ", {"UV_CACHE_DIR": "/unwritable/default"}),
            patch.object(self.runner, "_dependencies_ready", side_effect=[False, True]),
            patch.object(
                self.runner,
                "_run_command",
                return_value={"exit_code": 0, "timed_out": False},
            ) as setup,
        ):
            self.assertTrue(self.runner.preflight_dependencies()["passed"])
        self.assertEqual(
            str(self.validation_state / "cache" / "uv"),
            setup.call_args.args[1]["UV_CACHE_DIR"],
        )

    def test_dependency_readiness_checks_pins_and_existing_artifacts(self):
        venv = self.workspace / ".venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin" / "python").write_text("synthetic interpreter placeholder\n")
        (venv / "pyvenv.cfg").write_text("version_info = 3.12\n")
        (self.workspace / "gate" / "runtime").mkdir(parents=True)
        (self.workspace / "gate" / "runtime" / "requirements.txt").write_text(
            "Pillow==12.3.0\n"
        )
        (self.workspace / "requirements-dev.txt").write_text("black==26.5.1\n")
        (self.workspace / "node_modules").mkdir()

        def completed(output):
            return subprocess.CompletedProcess([], 0, output, "")

        responses = [
            completed(
                '[{"name":"Pillow","version":"12.3.0"},{"name":"black","version":"26.5.1"}]'
            ),
            completed("All installed packages are compatible"),
            completed('{"dependencies":{}}'),
        ]
        with patch("sanctum_agents.validation.subprocess.run", side_effect=responses):
            self.assertTrue(
                self.runner._dependencies_ready(self.runner._environment("TTE-14"))
            )
        (venv / "pyvenv.cfg").write_text("version = 3.12.4\n")
        with patch("sanctum_agents.validation.subprocess.run", side_effect=responses):
            self.assertTrue(
                self.runner._dependencies_ready(self.runner._environment("TTE-14"))
            )
        (venv / "pyvenv.cfg").write_text("version_info = 3.13\n")
        with patch("sanctum_agents.validation.subprocess.run") as inspect:
            self.assertFalse(
                self.runner._dependencies_ready(self.runner._environment("TTE-14"))
            )
        inspect.assert_not_called()
        (venv / "pyvenv.cfg").write_text("version_info = 3.12\n")
        responses[0] = completed('[{"name":"Pillow","version":"12.3.0"}]')
        with patch("sanctum_agents.validation.subprocess.run", side_effect=responses):
            self.assertFalse(
                self.runner._dependencies_ready(self.runner._environment("TTE-14"))
            )

    def test_dependency_preflight_rejects_modified_make_contract(self):
        (self.workspace / "Makefile").write_text("deps:\n\t@echo unreviewed\n")
        with patch.object(self.runner, "_run_command") as setup:
            result = self.runner.preflight_dependencies()
        self.assertFalse(result["passed"])
        setup.assert_not_called()

    def test_dependency_preflight_fails_closed_for_failed_timeout_and_partial_setup(
        self,
    ):
        for command_result, ready_after in (
            ({"exit_code": 1, "timed_out": False}, False),
            ({"exit_code": -15, "timed_out": True}, False),
            ({"exit_code": 0, "timed_out": False}, False),
        ):
            with self.subTest(command_result=command_result, ready_after=ready_after):
                with (
                    patch.object(
                        self.runner,
                        "_dependencies_ready",
                        side_effect=[False, ready_after],
                    ),
                    patch.object(
                        self.runner, "_run_command", return_value=command_result
                    ),
                ):
                    result = self.runner.preflight_dependencies()
                self.assertFalse(result["passed"])
                self.assertEqual("failed", result["state"])

    def test_dependency_preflight_rejects_source_mutation_and_symlink_artifacts(self):
        def mutating_setup(_command, _environment):
            (self.workspace / "README.md").write_text("changed\n")
            return {"exit_code": 0, "timed_out": False}

        with (
            patch.object(self.runner, "_dependencies_ready", side_effect=[False, True]),
            patch.object(self.runner, "_run_command", side_effect=mutating_setup),
        ):
            self.assertFalse(self.runner.preflight_dependencies()["passed"])
        (self.workspace / "README.md").write_text("accepted base\n")
        (self.workspace / ".venv").symlink_to(
            self.validation_state, target_is_directory=True
        )
        with patch.object(self.runner, "_run_command") as setup:
            self.assertFalse(self.runner.preflight_dependencies()["passed"])
        setup.assert_not_called()

    def test_failed_process_inspection_preflight_stops_before_expensive_validation(
        self,
    ):
        calls = []

        def blocked(command, _environment):
            calls.append(command.name)
            return {
                "name": command.name,
                "arguments": list(command.arguments),
                "exit_code": 1,
                "timed_out": False,
                "duration_ms": 1,
                "stdout": "",
                "stderr": "ps: Operation not permitted",
                "output_truncated": False,
            }

        with patch.object(self.runner, "_run_command", side_effect=blocked):
            result = self.runner.run(
                "TTE-14", "TTE-14", "normal-code", "sandbox-preflight"
            )
        self.assertFalse(result["passed"])
        self.assertEqual(["process_inspection_preflight"], calls)
        receipt = json.loads(
            next((self.validation_state / "receipts").rglob("*.json")).read_text()
        )
        self.assertIn("environment_preflight_failed", receipt["events"])

    def test_workspace_mismatch_and_arbitrary_profile_fail_closed(self):
        with self.assertRaisesRegex(ValidationError, "workspace_id"):
            self.runner.run("TTE-14", "TTE-9", "architecture-security", "validation-v1")
        with self.assertRaisesRegex(ValidationError, "not approved"):
            self.runner.run("TTE-14", "TTE-14", "shell", "validation-v1")

    def test_operator_blocker_is_bounded_private_and_replayable(self):
        first = self.runner.report_operator_blocker(
            "TTE-14",
            "TTE-14",
            "owner_prerequisite_missing",
            "owner-prerequisite-v1",
        )
        receipt_path = next((self.validation_state / "blockers").rglob("*.json"))
        first_receipt = json.loads(receipt_path.read_text())
        second = self.runner.report_operator_blocker(
            "TTE-14",
            "TTE-14",
            "owner_prerequisite_missing",
            "owner-prerequisite-v1",
        )
        second_receipt = json.loads(receipt_path.read_text())
        self.assertEqual("reported", first["status"])
        self.assertEqual(first["receipt_id"], second["receipt_id"])
        self.assertEqual("operator_action_required", second_receipt["event"])
        self.assertGreaterEqual(
            second_receipt["reported_at"], first_receipt["reported_at"]
        )
        self.assertEqual(0o600, receipt_path.stat().st_mode & 0o777)
        self.assertNotIn("details", second_receipt)
        with self.assertRaisesRegex(ValidationError, "not approved"):
            self.runner.report_operator_blocker(
                "TTE-14", "TTE-14", "arbitrary", "different-operation"
            )

    def test_operation_id_cannot_be_reused_after_workspace_changes(self):
        with patch.object(
            self.runner,
            "_run_command",
            return_value={
                "name": "synthetic",
                "arguments": ["/usr/bin/true"],
                "exit_code": 0,
                "timed_out": False,
                "duration_ms": 1,
                "stdout": "",
                "stderr": "",
                "output_truncated": False,
            },
        ):
            self.runner.run("TTE-14", "TTE-14", "docs-config", "stable-operation")
            (self.workspace / "README.md").write_text("changed\n")
            with self.assertRaisesRegex(ValidationError, "different validation intent"):
                self.runner.run("TTE-14", "TTE-14", "docs-config", "stable-operation")

    def test_untracked_file_contents_are_bound_to_operation(self):
        (self.workspace / "new.md").write_text("first\n")
        with patch.object(
            self.runner,
            "_run_command",
            return_value={
                "name": "synthetic",
                "arguments": ["/usr/bin/true"],
                "exit_code": 0,
                "timed_out": False,
                "duration_ms": 1,
                "stdout": "",
                "stderr": "",
                "output_truncated": False,
            },
        ):
            self.runner.run("TTE-14", "TTE-14", "docs-config", "untracked-state")
            (self.workspace / "new.md").write_text("second\n")
            with self.assertRaisesRegex(ValidationError, "different validation intent"):
                self.runner.run("TTE-14", "TTE-14", "docs-config", "untracked-state")

    def test_workspace_change_during_validation_fails_receipt(self):
        calls = 0

        def mutating_result(command, _environment):
            nonlocal calls
            calls += 1
            if calls == 1:
                (self.workspace / "README.md").write_text("changed during run\n")
            return {
                "name": command.name,
                "arguments": list(command.arguments),
                "exit_code": 0,
                "timed_out": False,
                "duration_ms": 1,
                "stdout": "",
                "stderr": "",
                "output_truncated": False,
            }

        with patch.object(self.runner, "_run_command", side_effect=mutating_result):
            result = self.runner.run(
                "TTE-14", "TTE-14", "docs-config", "workspace-race"
            )
        self.assertFalse(result["passed"])
        self.assertFalse(result["workspace_stable"])
        receipt = json.loads(
            next((self.validation_state / "receipts").rglob("*.json")).read_text()
        )
        self.assertIn("workspace_changed_during_validation", receipt["events"])


if __name__ == "__main__":
    unittest.main()
