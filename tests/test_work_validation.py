from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sanctum_agents.work_projects import parse_project_profiles
from sanctum_agents.work_validation import WorkValidationError, WorkValidationRunner
from sanctum_agents.work_workspaces import TaskWorkspace


def project(
    project_id: str, repository: str, operations: list[str]
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "repository": repository,
        "base_branch": "main",
        "validation_operations": operations,
        "private_config_refs": {
            "repository": f"{project_id}-repository",
            "validation": f"{project_id}-validation",
        },
    }


class WorkValidationRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.profiles = parse_project_profiles(
            {
                "schema": "sanctum-work-mode-project-profiles/v1",
                "profiles": [
                    project("widget", "synthetic/widget", ["test"]),
                    project("service", "synthetic/service", ["lint", "build"]),
                ],
            }
        )
        self.calls: list[tuple[str, Path, str]] = []

        def backend(profile: str, workspace: Path, command: str):
            self.calls.append((profile, workspace, command))
            return {
                "ok": True,
                "code": "OK",
                "executionState": "COMPLETED",
                "output_digest": "0" * 64,
            }

        self.runner = WorkValidationRunner(self.profiles, backend)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def workspace(self, project_id: str, repository: str) -> TaskWorkspace:
        root = self.root / project_id
        root.mkdir(exist_ok=True)
        return TaskWorkspace(
            project_id=project_id,
            task_id=f"TASK-{project_id}",
            root=root,
            repository=repository,
            base_branch="main",
            base_commit="a" * 40,
            resumed=False,
        )

    def test_projects_select_distinct_validation_profiles_and_commands(self):
        widget = self.runner.run(self.workspace("widget", "synthetic/widget"), "test")
        service = self.runner.run(
            self.workspace("service", "synthetic/service"), "lint"
        )

        self.assertEqual(
            [
                ("widget-validation", self.root / "widget", "test"),
                ("service-validation", self.root / "service", "lint"),
            ],
            self.calls,
        )
        self.assertEqual("widget-validation", widget.profile)
        self.assertEqual("test", widget.command)
        self.assertEqual("service-validation", service.profile)
        self.assertEqual("lint", service.command)

    def test_receipt_identifies_project_profile_command_and_result(self):
        receipt = self.runner.run(
            self.workspace("service", "synthetic/service"), "build"
        ).as_dict()

        self.assertEqual("sanctum-work-mode-validation-receipt/v1", receipt["schema"])
        self.assertEqual("service", receipt["project_id"])
        self.assertEqual("service-validation", receipt["profile"])
        self.assertEqual("build", receipt["command"])
        self.assertEqual("OK", receipt["result"]["code"])
        self.assertTrue(receipt["result"]["ok"])

    def test_unsupported_or_mismatched_requests_never_reach_backend(self):
        widget = self.workspace("widget", "synthetic/widget")
        for operation in ("lint", "shell", ["test"], None):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(WorkValidationError, "not allowed"):
                    self.runner.run(widget, operation)

        mismatched = self.workspace("service", "synthetic/other")
        with self.assertRaisesRegex(WorkValidationError, "does not match"):
            self.runner.run(mismatched, "lint")
        self.assertEqual([], self.calls)

    def test_invalid_backend_result_fails_closed(self):
        runner = WorkValidationRunner(self.profiles, lambda *_: {"ok": True})
        with self.assertRaisesRegex(WorkValidationError, "invalid result"):
            runner.run(self.workspace("widget", "synthetic/widget"), "test")


if __name__ == "__main__":
    unittest.main()
