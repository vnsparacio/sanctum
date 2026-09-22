import copy
import unittest

from sanctum_agents.work_linear import (
    ATTACH_PULL_REQUEST,
    CREATE_COMMENT,
    UPDATE_COMMENT,
    WorkIssueScope,
    WorkLinearError,
    WorkLinearOperations,
)

ISSUE_ID = "39256548-ce7a-4289-8af6-dedbd6b9e67a"
PROJECT_ID = "82dc74d8-21e6-4d09-92f5-3f9d12b0948a"
BODY = "## Codex Workpad\n\n### Plan\n- Keep scope fixed.\n\n### Review checkpoint\n- none\n\n### Validation\n- pending"


class FakeLinear:
    def __init__(self):
        self.calls = []
        self.fail_after = None
        self.issue = {
            "id": ISSUE_ID,
            "identifier": "TTE-76",
            "title": "Synthetic task",
            "url": "https://linear.example/TTE-76",
            "description": "Acceptance: bounded evidence.",
            "state": {"id": "state", "name": "In Progress", "type": "started"},
            "project": {"id": PROJECT_ID, "name": "Sanctum V1.3"},
            "parent": None,
            "children": {"nodes": []},
            "relations": {"nodes": []},
            "inverseRelations": {"nodes": []},
            "comments": {
                "nodes": [],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
            "attachments": {"nodes": []},
        }

    def query(self, query, variables=None, timeout=15):
        variables = variables or {}
        self.calls.append((query, copy.deepcopy(variables)))
        if query == CREATE_COMMENT:
            self.issue["comments"]["nodes"].append(
                {"id": "comment-1", "body": variables["body"]}
            )
            result = {"commentCreate": {"success": True}}
        elif query == UPDATE_COMMENT:
            self.issue["comments"]["nodes"][0]["body"] = variables["body"]
            result = {"commentUpdate": {"success": True}}
        elif query == ATTACH_PULL_REQUEST:
            self.issue["attachments"]["nodes"].append(
                {
                    "id": "attachment-1",
                    "title": variables["title"],
                    "url": variables["url"],
                    "sourceType": "github",
                }
            )
            result = {"attachmentLinkGitHubPR": {"success": True}}
        else:
            result = {"issue": copy.deepcopy(self.issue)}
        if self.fail_after == query:
            self.fail_after = None
            raise TimeoutError("synthetic unknown outcome")
        return result


class WorkLinearTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeLinear()
        self.scope = WorkIssueScope(
            issue_id=ISSUE_ID,
            identifier="TTE-76",
            project_id=PROJECT_ID,
            repository="vnsparacio/sanctum",
        )
        self.operations = WorkLinearOperations(self.client, self.scope)

    def test_fetch_is_fixed_to_internal_issue_and_project(self):
        issue = self.operations.fetch_issue()
        self.assertEqual("TTE-76", issue["identifier"])
        self.assertEqual({"id": ISSUE_ID}, self.client.calls[0][1])
        self.client.issue["identifier"] = "TTE-77"
        with self.assertRaisesRegex(WorkLinearError, "fixed task scope"):
            self.operations.fetch_issue()

    def test_fetch_refuses_unbounded_comment_pagination(self):
        self.client.issue["comments"]["pageInfo"]["hasNextPage"] = True
        with self.assertRaisesRegex(WorkLinearError, "requires pagination"):
            self.operations.fetch_issue()

    def test_fetch_returns_a_copy_of_relation_and_acceptance_data(self):
        self.client.issue["children"]["nodes"].append(
            {"id": "child", "identifier": "TTE-77", "title": "Next slice"}
        )
        issue = self.operations.fetch_issue()
        issue["children"]["nodes"].clear()
        issue["description"] = "changed"
        self.assertEqual(1, len(self.client.issue["children"]["nodes"]))
        self.assertEqual(
            "Acceptance: bounded evidence.", self.client.issue["description"]
        )

    def test_workpad_create_update_and_exact_replay_use_one_comment(self):
        created = self.operations.upsert_workpad(BODY)
        replay = self.operations.upsert_workpad(BODY)
        updated = self.operations.upsert_workpad(BODY + "\n- passed")
        self.assertEqual("created", created["status"])
        self.assertEqual("unchanged", replay["status"])
        self.assertEqual("updated", updated["status"])
        self.assertEqual(1, len(self.client.issue["comments"]["nodes"]))
        mutations = [
            call for call in self.client.calls if call[0] != self.client.calls[0][0]
        ]
        self.assertEqual(1, sum(query == CREATE_COMMENT for query, _ in mutations))
        self.assertEqual(1, sum(query == UPDATE_COMMENT for query, _ in mutations))

    def test_workpad_requires_exact_heading_and_refuses_duplicates(self):
        with self.assertRaisesRegex(WorkLinearError, "must begin"):
            self.operations.upsert_workpad("### Plan\n- no heading")
        self.client.issue["comments"]["nodes"] = [
            {"id": "a", "body": BODY},
            {"id": "b", "body": BODY},
        ]
        with self.assertRaisesRegex(WorkLinearError, "multiple active"):
            self.operations.upsert_workpad(BODY)

    def test_unknown_workpad_create_is_reconciled_without_duplicate(self):
        self.client.fail_after = CREATE_COMMENT
        result = self.operations.upsert_workpad(BODY)
        self.assertEqual("reconciled", result["status"])
        self.assertEqual(1, len(self.client.issue["comments"]["nodes"]))

    def test_pr_attachment_create_and_replay_use_one_attachment(self):
        url = "https://github.com/vnsparacio/sanctum/pull/76"
        created = self.operations.attach_pull_request(url, "Bounded Linear evidence")
        replay = self.operations.attach_pull_request(url, "Ignored replay title")
        self.assertEqual("created", created["status"])
        self.assertEqual("unchanged", replay["status"])
        self.assertEqual(1, len(self.client.issue["attachments"]["nodes"]))
        self.assertEqual(
            1, sum(query == ATTACH_PULL_REQUEST for query, _ in self.client.calls)
        )

    def test_unknown_pr_attachment_is_reconciled_without_duplicate(self):
        self.client.fail_after = ATTACH_PULL_REQUEST
        result = self.operations.attach_pull_request(
            "https://github.com/vnsparacio/sanctum/pull/76", "Synthetic PR"
        )
        self.assertEqual("reconciled", result["status"])
        self.assertEqual(1, len(self.client.issue["attachments"]["nodes"]))

    def test_pr_attachment_rejects_scope_widening_and_second_pr(self):
        with self.assertRaisesRegex(WorkLinearError, "scoped repository"):
            self.operations.attach_pull_request(
                "https://github.com/attacker/other/pull/1", "Wrong repository"
            )
        self.operations.attach_pull_request(
            "https://github.com/vnsparacio/sanctum/pull/76", "First PR"
        )
        with self.assertRaisesRegex(WorkLinearError, "another pull request"):
            self.operations.attach_pull_request(
                "https://github.com/vnsparacio/sanctum/pull/77", "Second PR"
            )

    def test_surface_has_no_issue_creation_state_or_label_mutation(self):
        public = {name for name in dir(self.operations) if not name.startswith("_")}
        self.assertEqual(
            {"attach_pull_request", "fetch_issue", "scope", "upsert_workpad"},
            public,
        )
        mutation_text = CREATE_COMMENT + UPDATE_COMMENT + ATTACH_PULL_REQUEST
        for forbidden in ("issueCreate", "issueUpdate", "label", "stateId"):
            self.assertNotIn(forbidden, mutation_text)


if __name__ == "__main__":
    unittest.main()
