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
