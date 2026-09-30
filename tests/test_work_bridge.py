from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sanctum_agents.work_bridge import (
    MAX_PACKET_BYTES,
    PACKET_SCHEMA,
    WorkModeBridge,
    WorkModeBridgeError,
    WorkModeBudget,
    WorkModeCheckpoint,
)
from sanctum_agents.work_linear import WorkIssueScope, WorkLinearOperations
from sanctum_agents.work_workspaces import TaskWorkspace, WorkWorkspaceManager

ISSUE_ID = "39256548-ce7a-4289-8af6-dedbd6b9e67a"
PROJECT_ID = "82dc74d8-21e6-4d09-92f5-3f9d12b0948a"
PROGRESS_ID = "3c9ab5d9-f1e1-49fd-a2fe-e1f558afce70"
WORKPAD = (
    "## Codex Workpad\n\n### Plan\n- Keep scope fixed.\n\n### Review checkpoint\n- none"
)


class FakeLinearClient:
    def __init__(self):
        self.issue = {
            "id": ISSUE_ID,
            "identifier": "TTE-79",
            "title": "Bounded Qwen bridge",
            "url": "https://linear.example/TTE-79",
            "description": "Acceptance: preserve issue scope and resume.",
            "state": {"id": PROGRESS_ID, "name": "In Progress", "type": "started"},
            "labels": {
                "nodes": [
                    {"id": "s", "name": "symphony"},
                    {"id": "w", "name": "agent-standard"},
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
            "project": {"id": PROJECT_ID, "name": "Sanctum V1.3"},
            "parent": None,
            "children": {"nodes": [], "pageInfo": {"hasNextPage": False}},
            "relations": {"nodes": [], "pageInfo": {"hasNextPage": False}},
            "inverseRelations": {"nodes": [], "pageInfo": {"hasNextPage": False}},
            "comments": {
                "nodes": [{"id": "workpad-79", "body": WORKPAD}],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
            "attachments": {
                "nodes": [],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }

    def query(self, query, variables=None, timeout=15):
        return {"issue": copy.deepcopy(self.issue)}


class FakeLinearOperations(WorkLinearOperations):
    def __init__(self, client, scope):
        super().__init__(client, scope)
        self.begin_calls = 0

    def begin_implementation(self, worker_class):
        self.begin_calls += 1
        return {"status": "unchanged", "state_id": PROGRESS_ID}


class FakeWorkspaceManager(WorkWorkspaceManager):
    def __init__(self, root: Path):
        self.root = root
        self.create_calls = 0
        self.branch_calls = 0

    def create(self, project_id, task_id):
        self.create_calls += 1
        return TaskWorkspace(
            project_id,
            task_id,
            self.root,
            "vnsparacio/sanctum",
            "v1.3-dev",
            "a" * 40,
            False,
        )

    def establish_branch(self, workspace, issue_identifier):
        self.branch_calls += 1
        return {
            "branch": "symphony/tte-79",
            "base_commit": "a" * 40,
            "head": "b" * 40,
        }


class WorkModeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.state = self.root / "state"
        self.workspace = self.root / "workspace"
        self.state.mkdir(mode=0o700)
        self.workspace.mkdir()
        self.client = FakeLinearClient()
        self.linear = FakeLinearOperations(
            self.client,
            WorkIssueScope(ISSUE_ID, "TTE-79", PROJECT_ID, "vnsparacio/sanctum"),
        )
        self.workspaces = FakeWorkspaceManager(self.workspace)
        self.budget = WorkModeBudget(
            "standard", "qwen-private-lead", "medium", 3600, 20, 500_000
        )

    def tearDown(self):
        self.temporary.cleanup()

    def bridge(self, budget=None):
        return WorkModeBridge(
            self.linear,
            self.workspaces,
            self.state,
            "sanctum",
            "TTE-79",
            budget or self.budget,
        )

    def test_packet_preserves_issue_workspace_budget_and_host_authority(self):
        invocation = self.bridge().prepare()
        packet = invocation.packet

        self.assertEqual(PACKET_SCHEMA, packet["schema"])
        self.assertEqual(ISSUE_ID, packet["issue"]["id"])
        self.assertEqual("TTE-79", packet["issue"]["identifier"])
        self.assertEqual("symphony/tte-79", packet["workspace"]["branch"])
        self.assertEqual("a" * 40, packet["workspace"]["base_commit"])
        self.assertEqual(self.budget.max_tokens, packet["budget"]["max_tokens"])
        self.assertEqual("MAC_HOST", packet["authority"]["owner"])
        self.assertFalse(packet["authority"]["may_set_execution_gate"])
        self.assertFalse(packet["authority"]["may_change_worker_class"])
        self.assertFalse(packet["authority"]["may_merge"])
        self.assertFalse(packet["authority"]["may_move_to_done"])
        self.assertTrue(packet["authority"]["human_review_required"])
        self.assertLessEqual(
            len(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()),
            MAX_PACKET_BYTES,
        )

    def test_restart_uses_completed_checkpoint_without_repeating_host_operations(self):
        first = self.bridge().prepare()
        second = self.bridge().prepare()

        self.assertFalse(first.resumed)
        self.assertTrue(second.resumed)
        self.assertEqual(1, self.linear.begin_calls)
        self.assertEqual(1, self.workspaces.create_calls)
        self.assertEqual(1, self.workspaces.branch_calls)
        self.assertEqual(
            ("branch-establish", "linear-begin", "workspace-create"),
            second.completed_operations,
        )
        self.assertTrue(second.packet["resume"]["resumed"])
        self.assertEqual(
            list(second.completed_operations),
            second.packet["resume"]["completed_operations"],
        )

    def test_pending_operation_reuses_identity_and_completed_operation_is_read_only(
        self,
    ):
        checkpoint = WorkModeCheckpoint(self.state, "TTE-80", {"issue": "TTE-80"})
        calls = []

        def interrupted():
            calls.append("interrupted")
            raise TimeoutError("synthetic interruption")

        with self.assertRaises(TimeoutError):
            checkpoint.perform("commit-1", "git_commit", {"paths": ["a"]}, interrupted)
        restarted = WorkModeCheckpoint(self.state, "TTE-80", {"issue": "TTE-80"})
        receipt = restarted.perform(
            "commit-1",
            "git_commit",
            {"paths": ["a"]},
            lambda: calls.append("reconciled") or {"commit": "c" * 40},
        )
        replay = restarted.perform(
            "commit-1",
            "git_commit",
            {"paths": ["a"]},
            lambda: calls.append("repeated") or {"commit": "d" * 40},
        )

        self.assertEqual({"commit": "c" * 40}, receipt)
        self.assertEqual(receipt, replay)
        self.assertEqual(["interrupted", "reconciled"], calls)

    def test_checkpoint_rejects_changed_scope_branch_budget_or_authority(self):
        self.bridge().prepare()
        deep = WorkModeBudget("deep", "qwen-private-lead", "high", 7200, 40, 1_000_000)
        with self.assertRaisesRegex(WorkModeBridgeError, "binding changed"):
            self.bridge(deep)
        value = json.loads(
            (self.state / "work-mode-checkpoints/TTE-79.json").read_text()
        )
        value["binding"]["branch"] = "symphony/other"
        path = self.state / "work-mode-checkpoints/TTE-79.json"
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        with self.assertRaisesRegex(WorkModeBridgeError, "binding changed"):
            self.bridge()

    def test_packet_rejects_wrong_route_missing_workpad_and_oversized_issue(self):
        cases = (
            (
                "route",
                lambda: self.client.issue["labels"]["nodes"].append(
                    {"id": "d", "name": "agent-deep"}
                ),
            ),
            ("workpad", lambda: self.client.issue["comments"].update({"nodes": []})),
            (
                "oversized",
                lambda: self.client.issue.update({"description": "x" * 16_001}),
            ),
        )
        for name, mutate in cases:
            with self.subTest(name=name):
                self.client = FakeLinearClient()
                self.linear = FakeLinearOperations(
                    self.client,
                    WorkIssueScope(
                        ISSUE_ID, "TTE-79", PROJECT_ID, "vnsparacio/sanctum"
                    ),
                )
                isolated = self.root / name
                isolated.mkdir()
                mutate()
                with self.assertRaises(WorkModeBridgeError):
                    WorkModeBridge(
                        self.linear,
                        self.workspaces,
                        isolated,
                        "sanctum",
                        f"TTE-79-{name}",
                        self.budget,
                    ).prepare()

    def test_packet_rejects_malformed_commit_identity_and_unbounded_model(self):
        self.workspaces.establish_branch = lambda workspace, issue_identifier: {
            "branch": "symphony/tte-79",
            "base_commit": "a" * 40,
            "head": "b" * 64,
        }
        with self.assertRaisesRegex(WorkModeBridgeError, "workspace or branch"):
            self.bridge().prepare()
        with self.assertRaisesRegex(WorkModeBridgeError, "invalid Work Mode model"):
            WorkModeBudget("standard", "q" * 129, "medium", 3600, 20, 500_000)

    def test_backend_receives_only_bounded_invocation(self):
        backend = SimpleNamespace(
            invoke=lambda invocation: {
                "status": "BLOCKED",
                "resumed": invocation.resumed,
            }
        )
        result = self.bridge().invoke(backend)
        self.assertEqual({"status": "BLOCKED", "resumed": False}, result)


if __name__ == "__main__":
    unittest.main()
