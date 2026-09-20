from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sanctum_agents.git_control_plane import (
    GitControlError,
    GitControlPlane,
    UnknownGitResult,
)


class GitControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.remote = self.root / "remote.git"
        self.seed = self.root / "seed"
        self.workspaces = self.root / "workspaces"
        self.workspace = self.workspaces / "TTE-9"
        self.state = self.root / "private-state"
        self._run(["git", "init", "--bare", str(self.remote)], cwd=self.root)
        self._run(["git", "init", "-b", "v1.2-dev", str(self.seed)], cwd=self.root)
        (self.seed / "README.md").write_text("accepted base\n")
        self._run(["git", "add", "README.md"], cwd=self.seed)
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
            cwd=self.seed,
        )
        self._run(["git", "remote", "add", "origin", str(self.remote)], cwd=self.seed)
        self._run(["git", "push", "origin", "v1.2-dev"], cwd=self.seed)
        self.workspaces.mkdir()
        self._run(
            [
                "git",
                "clone",
                "--branch",
                "v1.2-dev",
                "--single-branch",
                str(self.remote),
                str(self.workspace),
            ],
            cwd=self.root,
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _run(arguments, *, cwd):
        return subprocess.run(
            arguments, cwd=cwd, text=True, capture_output=True, check=True
        )

    def broker(self, **values):
        return GitControlPlane(
            values.pop("workspace", self.workspace),
            self.workspaces,
            self.state,
            expected_remote=str(self.remote),
            **values,
        )

    def test_authorized_bootstrap_uses_only_accepted_base(self):
        value = self.broker().prepare()
        self.assertEqual("symphony/tte-9", value["branch"])
        self.assertEqual("origin/v1.2-dev", value["base"])
        self.assertEqual(
            "symphony/tte-9",
            self._run(
                ["git", "branch", "--show-current"], cwd=self.workspace
            ).stdout.strip(),
        )
        with self.assertRaisesRegex(GitControlError, "only origin/v1.2-dev"):
            self.broker().prepare("main")

    def test_wrong_branch_and_remote_are_rejected(self):
        self.broker().prepare()
        self._run(["git", "switch", "-c", "symphony/another-issue"], cwd=self.workspace)
        with self.assertRaisesRegex(GitControlError, "deterministic issue branch"):
            self.broker().status()

    def test_existing_lease_rejects_replaced_git_repository(self):
        broker = self.broker()
        broker.prepare()
        replacement = self.root / "replacement"
        self._run(
            [
                "git",
                "clone",
                "--branch",
                "v1.2-dev",
                str(self.remote),
                str(replacement),
            ],
            cwd=self.root,
        )
        self._run(["git", "switch", "-c", "symphony/tte-9"], cwd=replacement)
        shutil.rmtree(self.workspace / ".git")
        shutil.move(str(replacement / ".git"), str(self.workspace / ".git"))
        with self.assertRaisesRegex(GitControlError, "identity no longer matches"):
            self.broker().prepare()
        self._run(["git", "switch", "symphony/tte-9"], cwd=self.workspace)
        self._run(
            ["git", "remote", "set-url", "origin", str(self.root / "other.git")],
            cwd=self.workspace,
        )
        with self.assertRaisesRegex(GitControlError, "reviewed repository remote"):
            self.broker().status()

    def test_workspace_symlink_and_git_pointer_are_rejected(self):
        link = self.root / "TTE-10"
        link.symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaisesRegex(GitControlError, "direct child|symlinks"):
            self.broker(workspace=link).identity()
        pointer_workspace = self.workspaces / "TTE-10"
        self._run(
            [
                "git",
                "clone",
                "--branch",
                "v1.2-dev",
                str(self.remote),
                str(pointer_workspace),
            ],
            cwd=self.root,
        )
        real_git = self.root / "redirected.git"
        (pointer_workspace / ".git").rename(real_git)
        (pointer_workspace / ".git").write_text(f"gitdir: {real_git}\n")
        with self.assertRaisesRegex(GitControlError, "in-place non-symlink"):
            self.broker(workspace=pointer_workspace).identity()

    def test_commit_and_normal_push_happy_path(self):
        broker = self.broker()
        broker.prepare()
        (self.workspace / "docs.md").write_text("bounded change\n")
        committed = broker.commit(
            "Document bounded broker", ["docs.md"], "commit-happy-path"
        )
        self.assertEqual("applied", committed["status"])
        self.assertTrue(broker.status()["clean"])
        pushed = broker.push("push-happy-path")
        self.assertEqual("applied", pushed["status"])
        remote_head = self._run(
            [
                "git",
                "--git-dir",
                str(self.remote),
                "rev-parse",
                "refs/heads/symphony/tte-9",
            ],
            cwd=self.root,
        ).stdout.strip()
        self.assertEqual(committed["commit"], remote_head)

    def test_rejected_directory_scope_leaves_index_clean(self):
        broker = self.broker()
        broker.prepare()
        docs = self.workspace / "docs"
        docs.mkdir()
        (docs / "bounded.md").write_text("bounded change\n")
        with self.assertRaisesRegex(GitControlError, "exactly identify"):
            broker.commit("Reject directory selection", ["docs"], "directory-scope")
        staged = self._run(
            ["git", "diff", "--cached", "--name-only"], cwd=self.workspace
        ).stdout
        self.assertEqual("", staged)
        committed = broker.commit(
            "Accept exact file selection", ["docs/bounded.md"], "exact-scope"
        )
        self.assertEqual("applied", committed["status"])

    def test_partial_staging_failure_restores_index(self):
        broker = self.broker()
        broker.prepare()
        (self.workspace / "docs.md").write_text("partial staging\n")
        original_git = broker._git

        def fail_after_add(*arguments, **values):
            if arguments and arguments[0] == "add":
                original_git(*arguments, **values)
                raise GitControlError("synthetic_add_failure", "synthetic add failure")
            return original_git(*arguments, **values)

        with patch.object(broker, "_git", side_effect=fail_after_add):
            with self.assertRaisesRegex(GitControlError, "synthetic add failure"):
                broker.commit(
                    "Exercise partial staging failure", ["docs.md"], "partial-add"
                )
        staged = self._run(
            ["git", "diff", "--cached", "--name-only"], cwd=self.workspace
        ).stdout
        self.assertEqual("", staged)
        self.assertEqual(
            "applied",
            broker.commit(
                "Recover after staging failure", ["docs.md"], "recovered-add"
            )["status"],
        )

    def test_force_push_and_arbitrary_git_are_not_exposed(self):
        script = (
            Path(__file__).parents[1] / "scripts" / "sanctum_git_broker.py"
        ).read_text()
        self.assertNotIn('"git_force', script)
        self.assertNotIn('"git_command', script)
        self.assertNotIn("--force", script)
        self.assertNotIn("reset --hard", script)

    def test_git_subprocess_environment_does_not_inherit_tokens(self):
        environment = self.broker()._environment()
        self.assertNotIn("LINEAR_API_KEY", environment)
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertNotIn("GH_TOKEN", environment)
        self.assertEqual("/dev/null", environment["GIT_CONFIG_GLOBAL"])

    def test_commit_reconciles_after_ambiguous_result_without_replay(self):
        calls = []

        def fault(phase):
            calls.append(phase)
            if phase == "after_commit":
                from sanctum_agents import git_control_plane

                raise git_control_plane._InjectedAmbiguity("synthetic lost reply")

        broker = self.broker(fault_injector=fault)
        broker.prepare()
        (self.workspace / "docs.md").write_text("ambiguous commit\n")
        value = broker.commit("Reconcile bounded commit", ["docs.md"], "commit-unknown")
        self.assertEqual("reconciled", value["status"])
        replay = self.broker().commit(
            "Reconcile bounded commit", ["docs.md"], "commit-unknown"
        )
        self.assertEqual("already_applied", replay["status"])
        self.assertEqual(["after_commit"], calls)

    def test_commit_operation_id_cannot_be_reused_for_new_intent(self):
        broker = self.broker()
        broker.prepare()
        (self.workspace / "docs.md").write_text("first intent\n")
        broker.commit("Record first bounded intent", ["docs.md"], "stable-operation")
        with self.assertRaisesRegex(GitControlError, "different commit request"):
            broker.commit(
                "Record different bounded intent", ["docs.md"], "stable-operation"
            )

    def test_push_reconciles_after_ambiguous_result_without_force(self):
        def fault(phase):
            if phase == "after_push":
                from sanctum_agents import git_control_plane

                raise git_control_plane._InjectedAmbiguity("synthetic lost reply")

        broker = self.broker(fault_injector=fault)
        broker.prepare()
        (self.workspace / "docs.md").write_text("ambiguous push\n")
        broker.commit("Prepare bounded push", ["docs.md"], "commit-for-push")
        value = broker.push("push-unknown")
        self.assertEqual("reconciled", value["status"])
        replay = self.broker().push("push-unknown")
        self.assertEqual("already_applied", replay["status"])

    def test_unreconciled_pending_push_is_unknown_and_not_replayed(self):
        broker = self.broker()
        broker.prepare()
        receipt = {
            "schema_version": 1,
            "kind": "push",
            "state": "pending",
            "operation_id": "lost-push",
            "issue_identifier": "TTE-9",
            "branch": "symphony/tte-9",
            "local_head": broker._head(),
            "remote_head_before": None,
        }
        identity = broker.identity()
        path = broker._receipt_path(identity, "push", "lost-push")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(UnknownGitResult, "not replayed"):
            broker.push("lost-push")

    def test_private_paths_symlinks_and_unexpected_local_config_are_rejected(self):
        broker = self.broker()
        broker.prepare()
        (self.workspace / ".env").write_text("SECRET=synthetic\n")
        with self.assertRaisesRegex(GitControlError, "private or credential"):
            broker.commit("Reject private state", [".env"], "private-path")
        target = self.root / "outside.txt"
        target.write_text("outside\n")
        (self.workspace / "escape.txt").symlink_to(target)
        with self.assertRaisesRegex(GitControlError, "symlink"):
            broker.commit("Reject symlink escape", ["escape.txt"], "symlink-path")
        self._run(
            ["git", "config", "credential.helper", "malicious-helper"],
            cwd=self.workspace,
        )
        with self.assertRaisesRegex(GitControlError, "unreviewed local Git config"):
            broker.status()

    def test_private_state_must_remain_outside_workspace_root(self):
        with self.assertRaisesRegex(GitControlError, "outside issue workspaces"):
            GitControlPlane(
                self.workspace,
                self.workspaces,
                self.workspaces / "state",
                expected_remote=str(self.remote),
            )
        state_target = self.root / "state-target"
        state_target.mkdir()
        state_link = self.root / "state-link"
        state_link.symlink_to(state_target, target_is_directory=True)
        with self.assertRaisesRegex(GitControlError, "non-symlink"):
            GitControlPlane(
                self.workspace,
                self.workspaces,
                state_link,
                expected_remote=str(self.remote),
            )

    def test_pull_request_tool_has_fixed_repository_base_and_head(self):
        broker = self.broker()
        broker.prepare()
        (self.workspace / "docs.md").write_text("PR handoff\n")
        broker.commit("Prepare pull request handoff", ["docs.md"], "pr-commit")
        broker.push("pr-push")
        github_config = self.root / "github-config"
        github_config.mkdir(mode=0o700)
        gh_dir = self.root / "bin"
        gh_dir.mkdir()
        gh = gh_dir / "gh"
        gh.write_text("#!/bin/sh\nexit 1\n")
        gh.chmod(0o700)
        broker = self.broker(
            credential_helper=str(gh), github_config_dir=str(github_config)
        )
        response = {
            "number": 41,
            "url": "https://github.example/pr/41",
            "baseRefName": "v1.2-dev",
            "headRefName": "symphony/tte-9",
            "headRefOid": broker._head(),
            "headRepository": {"nameWithOwner": "vnsparacio/sanctum"},
            "headRepositoryOwner": {"login": "vnsparacio"},
            "isDraft": False,
            "title": "Complete bounded Git handoff",
            "body": "Implements TTE-9 with bounded validation evidence.",
        }
        calls = []

        def fake_gh(*arguments, **_values):
            calls.append(arguments)
            if arguments[:2] == ("pr", "list"):
                payload = [] if len(calls) == 1 else [response]
                return subprocess.CompletedProcess(
                    arguments, 0, json.dumps(payload), ""
                )
            return subprocess.CompletedProcess(arguments, 0, "", "")

        with patch.object(broker, "_gh", side_effect=fake_gh):
            value = broker.ensure_pull_request(response["title"], response["body"])
        self.assertEqual("created", value["status"])
        lookup = next(call for call in calls if call[:2] == ("pr", "list"))
        self.assertEqual("symphony/tte-9", lookup[lookup.index("--head") + 1])
        create = next(call for call in calls if call[:2] == ("pr", "create"))
        self.assertIn("vnsparacio/sanctum", create)
        self.assertIn("v1.2-dev", create)
        self.assertIn("symphony/tte-9", create)
        self.assertNotIn("merge", create)
        self.assertNotIn("--force", create)

    def test_fork_pull_request_with_same_branch_name_is_rejected(self):
        broker = self.broker()
        broker.prepare()
        identity = broker.identity()
        response = [
            {
                "number": 42,
                "url": "https://github.example/pr/42",
                "baseRefName": "v1.2-dev",
                "headRefName": "symphony/tte-9",
                "headRefOid": broker._head(),
                "headRepository": {"nameWithOwner": "attacker/sanctum"},
                "headRepositoryOwner": {"login": "attacker"},
                "isDraft": False,
                "title": "Spoofed issue branch",
                "body": "Spoofed TTE-9 pull request body.",
            }
        ]
        completed = subprocess.CompletedProcess((), 0, json.dumps(response), "")
        with patch.object(broker, "_gh", return_value=completed):
            self.assertIsNone(broker._open_pull_request(identity))


if __name__ == "__main__":
    unittest.main()
