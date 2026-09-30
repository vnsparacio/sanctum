from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from sanctum_agents.work_projects import parse_project_profiles
from sanctum_agents.work_validation import ValidationReceipt
from sanctum_agents.work_workspaces import WorkWorkspaceError, WorkWorkspaceManager


class WorkWorkspaceManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.repository = self.root / "widget-source"
        self.workspaces = self.root / "workspaces"
        self.state = self.root / "private-state"
        self.repository.mkdir()
        self.workspaces.mkdir()
        self.state.mkdir()
        self._run("init", "-b", "main", str(self.repository), cwd=self.root)
        (self.repository / "widget.txt").write_text("synthetic widget\n")
        self._run("add", "widget.txt")
        self._run(
            "-c",
            "user.name=Synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-m",
            "Synthetic base",
        )
        self.commit = self._run("rev-parse", "HEAD").stdout.strip()
        self._run("remote", "add", "origin", "https://github.com/synthetic/widget.git")
        self._run("update-ref", "refs/remotes/origin/main", self.commit)
        self.profiles = parse_project_profiles(
            {
                "schema": "sanctum-work-mode-project-profiles/v1",
                "profiles": [
                    {
                        "project_id": "widget",
                        "repository": "synthetic/widget",
                        "base_branch": "main",
                        "validation_operations": ["test"],
                        "private_config_refs": {
                            "repository": "widget-repository",
                            "validation": "widget-validation",
                        },
                    }
                ],
            }
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, *arguments: str, cwd: Path | None = None):
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd or self.repository,
            text=True,
            capture_output=True,
            check=True,
        )

    def manager(self, **values) -> WorkWorkspaceManager:
        return WorkWorkspaceManager(
            self.profiles,
            {"widget-repository": self.repository},
            self.workspaces,
            self.state,
            **values,
        )

    @staticmethod
    def validation_receipts() -> list[ValidationReceipt]:
        return [
            ValidationReceipt(
                project_id="widget",
                profile="widget-validation",
                command="test",
                result=MappingProxyType(
                    {
                        "ok": True,
                        "code": "OK",
                        "executionState": "COMPLETED",
                        "exit_code": 0,
                        "stdout": "42 tests passed\n",
                        "stderr": "",
                    }
                ),
            )
        ]

    def test_non_sanctum_profile_creates_isolated_task_workspace(self):
        workspace = self.manager().create("widget", "TASK-1")

        self.assertEqual(self.workspaces / "TASK-1", workspace.root)
        self.assertEqual(self.commit, workspace.base_commit)
        self.assertFalse(workspace.resumed)
        self.assertEqual(
            "synthetic widget\n", (workspace.root / "widget.txt").read_text()
        )
        (workspace.root / "widget.txt").write_text("task change\n")
        self.assertEqual(
            "synthetic widget\n", (self.repository / "widget.txt").read_text()
        )
        self.assertEqual(
            "HEAD",
            self._run("branch", "--show-current", cwd=workspace.root).stdout.strip()
            or "HEAD",
        )

    def test_wrong_repository_base_and_paths_fail_closed(self):
        self._run("remote", "set-url", "origin", "https://github.com/other/widget.git")
        with self.assertRaisesRegex(WorkWorkspaceError, "identity mismatch"):
            self.manager().create("widget", "TASK-2")

        self._run(
            "remote", "set-url", "origin", "https://github.com/synthetic/widget.git"
        )
        self._run("update-ref", "-d", "refs/remotes/origin/main")
        with self.assertRaisesRegex(WorkWorkspaceError, "base branch is unavailable"):
            self.manager().create("widget", "TASK-2")

        self._run("update-ref", "refs/remotes/origin/main", self.commit)
        for task_id in ("../escape", "/tmp/escape", "bad/task"):
            with self.subTest(task_id=task_id):
                with self.assertRaisesRegex(WorkWorkspaceError, "unsafe"):
                    self.manager().create("widget", task_id)
        (self.workspaces / "TASK-2").symlink_to(self.repository)
        with self.assertRaisesRegex(WorkWorkspaceError, "absolute directory"):
            self.manager().create("widget", "TASK-2")

    def test_restart_resumes_exact_workspace_and_rejects_tampered_state(self):
        first = self.manager().create("widget", "TASK-3")
        (first.root / "task.txt").write_text("bounded task change\n")
        self._run("add", "task.txt", cwd=first.root)
        self._run(
            "-c",
            "user.name=Synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-m",
            "Task checkpoint",
            cwd=first.root,
        )
        (self.repository / "widget.txt").write_text("new accepted base\n")
        self._run("add", "widget.txt")
        self._run(
            "-c",
            "user.name=Synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-m",
            "Advance approved base",
        )
        self._run("update-ref", "refs/remotes/origin/main", "HEAD")
        second = self.manager().create("widget", "TASK-3")
        self.assertTrue(second.resumed)
        self.assertEqual(first.root, second.root)
        self.assertEqual(first.base_commit, second.base_commit)
        self.assertEqual("synthetic widget\n", (second.root / "widget.txt").read_text())

        receipt = self.state / "workspaces" / "TASK-3.json"
        value = json.loads(receipt.read_text())
        value["workspace_path"] = str(self.workspaces / "OTHER")
        receipt.write_text(json.dumps(value))
        receipt.chmod(0o600)
        with self.assertRaisesRegex(WorkWorkspaceError, "state mismatch"):
            self.manager().create("widget", "TASK-3")

    def test_cleanup_survives_manager_restart_and_allows_recreation(self):
        created = self.manager().create("widget", "TASK-4")
        self.assertTrue(created.root.exists())

        restarted = self.manager()
        self.assertTrue(restarted.cleanup("widget", "TASK-4"))
        self.assertFalse(created.root.exists())
        self.assertFalse((self.state / "workspaces" / "TASK-4.json").exists())
        self.assertFalse(restarted.cleanup("widget", "TASK-4"))
        recreated = restarted.create("widget", "TASK-4")
        self.assertFalse(recreated.resumed)
        self.assertTrue(recreated.root.exists())

    def test_issue_branch_commit_selects_paths_and_reconciles_replay(self):
        manager = self.manager()
        workspace = manager.create("widget", "TASK-5")
        protected_head = self._run("rev-parse", "refs/heads/main").stdout.strip()
        branch = manager.establish_branch(workspace, "TTE-73")

        self.assertEqual("symphony/tte-73", branch["branch"])
        self.assertEqual(self.commit, branch["base_commit"])
        self.assertEqual(
            protected_head,
            self._run("rev-parse", "refs/heads/main").stdout.strip(),
        )
        (workspace.root / "widget.txt").write_text("selected task change\n")
        (workspace.root / "unselected.txt").write_text("leave for later\n")

        committed = manager.commit(
            workspace,
            "Commit selected Work Mode path",
            ["widget.txt"],
            "stable-task-commit",
        )
        replay = self.manager().commit(
            workspace,
            "Commit selected Work Mode path",
            ["widget.txt"],
            "stable-task-commit",
        )

        self.assertEqual("applied", committed["status"])
        self.assertEqual("already_applied", replay["status"])
        self.assertEqual(committed["commit"], replay["commit"])
        self.assertEqual(["widget.txt"], committed["paths"])
        self.assertEqual(
            "symphony/tte-73",
            self._run("branch", "--show-current", cwd=workspace.root).stdout.strip(),
        )
        self.assertEqual(
            protected_head,
            self._run("rev-parse", "refs/heads/main").stdout.strip(),
        )
        self.assertEqual(
            "synthetic widget\n", (self.repository / "widget.txt").read_text()
        )
        self.assertEqual(
            "?? unselected.txt",
            self._run("status", "--short", cwd=workspace.root).stdout.strip(),
        )

    def test_unknown_commit_result_reconciles_without_duplicate_commit(self):
        workspace = self.manager().create("widget", "TASK-6")
        self.manager().establish_branch(workspace, "TTE-73")
        (workspace.root / "widget.txt").write_text("ambiguous task change\n")

        def lose_reply(phase: str) -> None:
            if phase == "after_commit":
                raise RuntimeError("synthetic lost response")

        with self.assertRaisesRegex(RuntimeError, "synthetic lost response"):
            self.manager(fault_injector=lose_reply).commit(
                workspace,
                "Commit ambiguous Work Mode path",
                ["widget.txt"],
                "ambiguous-task-commit",
            )
        head = self._run("rev-parse", "HEAD", cwd=workspace.root).stdout.strip()
        reconciled = self.manager().commit(
            workspace,
            "Commit ambiguous Work Mode path",
            ["widget.txt"],
            "ambiguous-task-commit",
        )

        self.assertEqual("reconciled", reconciled["status"])
        self.assertEqual(head, reconciled["commit"])
        self.assertEqual(
            "1",
            self._run(
                "rev-list", "--count", f"{self.commit}..HEAD", cwd=workspace.root
            ).stdout.strip(),
        )

    def test_pull_request_creation_reconciles_to_one_validated_pr(self):
        lost = True

        def lose_first_reply(phase: str) -> None:
            nonlocal lost
            if phase == "after_pull_request_create" and lost:
                lost = False
                raise RuntimeError("synthetic lost PR response")

        manager = self.manager(fault_injector=lose_first_reply)
        workspace = manager.create("widget", "TASK-7")
        manager.establish_branch(workspace, "TTE-75")
        (workspace.root / "widget.txt").write_text("validated PR change\n")
        committed = manager.commit(
            workspace,
            "Commit validated Work Mode change",
            ["widget.txt"],
            "pr-task-commit",
        )
        current: dict[str, object] = {}
        calls: list[tuple[str, ...]] = []

        def github(
            *arguments: str, **_values: object
        ) -> subprocess.CompletedProcess[str]:
            calls.append(arguments)
            if arguments[0] == "api":
                return subprocess.CompletedProcess(
                    arguments,
                    0,
                    json.dumps({"object": {"sha": committed["commit"]}}),
                    "",
                )
            if arguments[:2] == ("pr", "list"):
                return subprocess.CompletedProcess(
                    arguments, 0, json.dumps([current] if current else []), ""
                )
            if arguments[:2] == ("pr", "create"):
                title = arguments[arguments.index("--title") + 1]
                body = arguments[arguments.index("--body") + 1]
                current.update(
                    {
                        "number": 75,
                        "url": "https://github.example/synthetic/widget/pull/75",
                        "baseRefName": "main",
                        "headRefName": "symphony/tte-75",
                        "headRefOid": committed["commit"],
                        "headRepository": {"nameWithOwner": "synthetic/widget"},
                        "headRepositoryOwner": {"login": "synthetic"},
                        "isDraft": False,
                        "title": title,
                        "body": body,
                    }
                )
                return subprocess.CompletedProcess(arguments, 0, current["url"], "")
            raise AssertionError(arguments)

        with patch.object(manager, "_gh", side_effect=github):
            with self.assertRaisesRegex(RuntimeError, "lost PR response"):
                manager.ensure_pull_request(
                    workspace,
                    "Deliver validated Work Mode change",
                    "Implements the bounded task outcome for owner review.",
                    self.validation_receipts(),
                    "stable-pr-operation",
                )
            replay = manager.ensure_pull_request(
                workspace,
                "Deliver validated Work Mode change",
                "Implements the bounded task outcome for owner review.",
                self.validation_receipts(),
                "stable-pr-operation",
            )
            with self.assertRaisesRegex(WorkWorkspaceError, "different PR request"):
                manager.ensure_pull_request(
                    workspace,
                    "Redirect validated Work Mode change",
                    "Implements the bounded task outcome for owner review.",
                    self.validation_receipts(),
                    "stable-pr-operation",
                )

        self.assertEqual("already_applied", replay["status"])
        self.assertEqual(75, replay["number"])
        self.assertEqual(
            1, len([call for call in calls if call[:2] == ("pr", "create")])
        )
        create = next(call for call in calls if call[:2] == ("pr", "create"))
        self.assertEqual("synthetic/widget", create[create.index("--repo") + 1])
        self.assertEqual("main", create[create.index("--base") + 1])
        self.assertEqual("symphony/tte-75", create[create.index("--head") + 1])
        self.assertNotIn("merge", create)
        body = str(current["body"])
        self.assertIn("Issue: `TTE-75`", body)
        self.assertIn("Task: `TASK-7`", body)
        self.assertIn('"command": "test"', body)
        self.assertIn('"stdout_sha256"', body)
        self.assertNotIn("42 tests passed", body)

    def test_pull_request_updates_existing_exact_task_handoff(self):
        manager = self.manager()
        workspace = manager.create("widget", "TASK-8")
        manager.establish_branch(workspace, "TTE-75")
        (workspace.root / "widget.txt").write_text("updated PR change\n")
        head = manager.commit(
            workspace,
            "Commit updated Work Mode change",
            ["widget.txt"],
            "update-pr-commit",
        )["commit"]
        current: dict[str, object] = {
            "number": 76,
            "url": "https://github.example/synthetic/widget/pull/76",
            "baseRefName": "main",
            "headRefName": "symphony/tte-75",
            "headRefOid": head,
            "headRepository": {"nameWithOwner": "synthetic/widget"},
            "headRepositoryOwner": {"login": "synthetic"},
            "isDraft": False,
            "title": "Old title",
            "body": "Old body",
        }

        def github(
            *arguments: str, **_values: object
        ) -> subprocess.CompletedProcess[str]:
            if arguments[0] == "api":
                return subprocess.CompletedProcess(
                    arguments, 0, json.dumps({"object": {"sha": head}}), ""
                )
            if arguments[:2] == ("pr", "list"):
                return subprocess.CompletedProcess(
                    arguments, 0, json.dumps([current]), ""
                )
            if arguments[:2] == ("pr", "edit"):
                current["title"] = arguments[arguments.index("--title") + 1]
                current["body"] = arguments[arguments.index("--body") + 1]
                return subprocess.CompletedProcess(arguments, 0, "", "")
            raise AssertionError(arguments)

        with patch.object(manager, "_gh", side_effect=github):
            result = manager.ensure_pull_request(
                workspace,
                "Update validated Work Mode change",
                "Updates the bounded task outcome for owner review.",
                self.validation_receipts(),
                "update-pr-operation",
            )

        self.assertEqual("updated", result["status"])
        self.assertEqual("Update validated Work Mode change", current["title"])

    def test_pull_request_rejects_missing_validation_wrong_base_or_repository(self):
        manager = self.manager()
        workspace = manager.create("widget", "TASK-9")
        manager.establish_branch(workspace, "TTE-75")
        (workspace.root / "widget.txt").write_text("rejected PR change\n")
        head = manager.commit(
            workspace,
            "Commit rejected Work Mode change",
            ["widget.txt"],
            "reject-pr-commit",
        )["commit"]

        with self.assertRaisesRegex(WorkWorkspaceError, "validation receipts"):
            manager.ensure_pull_request(
                workspace,
                "Reject incomplete Work Mode handoff",
                "This request intentionally lacks validation evidence.",
                [],
                "missing-validation",
            )

        def response(base: str, repository: str) -> Mapping[str, object]:
            return {
                "number": 77,
                "url": "https://github.example/pull/77",
                "baseRefName": base,
                "headRefName": "symphony/tte-75",
                "headRefOid": head,
                "headRepository": {"nameWithOwner": repository},
                "headRepositoryOwner": {"login": repository.split("/", 1)[0]},
                "isDraft": False,
                "title": "Existing PR",
                "body": "Existing PR body",
            }

        for operation, existing in (
            ("wrong-base", response("release", "synthetic/widget")),
            ("wrong-repository", response("main", "attacker/widget")),
        ):
            with self.subTest(operation=operation):

                def github(
                    *arguments: str,
                    _existing: Mapping[str, object] = existing,
                    **_values: object,
                ) -> subprocess.CompletedProcess[str]:
                    if arguments[0] == "api":
                        return subprocess.CompletedProcess(
                            arguments,
                            0,
                            json.dumps({"object": {"sha": head}}),
                            "",
                        )
                    if arguments[:2] == ("pr", "list"):
                        return subprocess.CompletedProcess(
                            arguments, 0, json.dumps([_existing]), ""
                        )
                    raise AssertionError(arguments)

                with patch.object(manager, "_gh", side_effect=github):
                    with self.assertRaisesRegex(
                        WorkWorkspaceError,
                        "approved repository, base, and task head",
                    ):
                        manager.ensure_pull_request(
                            workspace,
                            "Reject redirected Work Mode handoff",
                            "This request encounters an unapproved open PR.",
                            self.validation_receipts(),
                            operation,
                        )


if __name__ == "__main__":
    unittest.main()
