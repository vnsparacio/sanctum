from __future__ import annotations

import copy
import json
import unittest

from sanctum_agents.work_linear import WorkIssueScope, WorkLinearOperations
from sanctum_agents.work_review import (
    MAX_PACKET_BYTES,
    PACKET_SCHEMA,
    AdvisoryReviewBudget,
    AdvisoryReviewError,
    CandidatePullRequest,
    QwenCandidateAdvisoryReview,
)

ISSUE_ID = "d929e9ee-2cc7-4798-ad25-3bcf029b51b0"
PROJECT_ID = "82dc74d8-21e6-4d09-92f5-3f9d12b0948a"
WORKPAD = "## Codex Workpad\n\n### Validation evidence\n- focused tests: PASS"


class FakeLinearOperations(WorkLinearOperations):
    def __init__(self):
        class UnusedClient:
            def query(self, query, variables=None, timeout=15):
                raise AssertionError("direct Linear query was not expected")

        super().__init__(
            UnusedClient(),
            WorkIssueScope(ISSUE_ID, "TTE-80", PROJECT_ID, "vnsparacio/sanctum"),
        )
        self.issue = {
            "id": ISSUE_ID,
            "identifier": "TTE-80",
            "title": "Review a Qwen candidate",
            "description": "Acceptance: findings are advisory and review failure is visible.",
            "state": {"id": "human-review", "name": "Human Review"},
            "comments": {"nodes": [{"id": "workpad", "body": WORKPAD}]},
        }
        self.updates = []

    def fetch_issue(self):
        return copy.deepcopy(self.issue)

    def upsert_workpad(self, body):
        self.updates.append(body)
        self.issue["comments"]["nodes"][0]["body"] = body
        return {"status": "updated", "comment_id": "workpad"}


class Backend:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def invoke(self, packet, *, timeout_seconds):
        self.calls.append((packet, timeout_seconds))
        if self.error:
            raise self.error
        return copy.deepcopy(self.response)


class AdvisoryReviewTests(unittest.TestCase):
    def setUp(self):
        self.linear = FakeLinearOperations()
        self.candidate = CandidatePullRequest(
            70,
            "https://github.com/vnsparacio/sanctum/pull/70",
            "v1.3-dev",
            "symphony/tte-80",
            "a" * 40,
            True,
            False,
            ("sanctum_agents/work_review.py", "tests/test_work_review.py"),
            "diff --git a/a b/a\n+bounded change",
            ({"name": "ci", "status": "success"},),
            ({"command": "make test", "status": "passed"},),
        )
        self.budget = AdvisoryReviewBudget("codex", "gpt-6", "high", 120, 2)

    def review(self, run_id="review-1", candidate=None):
        return QwenCandidateAdvisoryReview(
            self.linear, candidate or self.candidate, run_id, self.budget
        )

    @staticmethod
    def approval():
        return {
            "verdict": "Approve",
            "summary": "The supplied candidate satisfies the bounded acceptance and authority contracts.",
            "findings": [
                {
                    "title": "Retain explicit advisory wording",
                    "category": "authority",
                    "blocking": False,
                    "evidence": "The packet explicitly denies merge, gate, Done, and completion authority.",
                    "recommendation": "Keep those denials in every durable review record and packet.",
                }
            ],
        }

    def test_success_uses_bounded_packet_and_records_untrusted_advisory_result(self):
        backend = Backend(self.approval())
        result = self.review().run(backend)

        self.assertEqual("completed", result["status"])
        self.assertFalse(result["completion_evidence"])
        packet, timeout = backend.calls[0]
        self.assertEqual(PACKET_SCHEMA, packet["schema"])
        self.assertEqual(120, timeout)
        self.assertTrue(packet["review"]["authority"]["advisory_only"])
        for field in (
            "may_modify_repository",
            "may_merge",
            "may_set_execution_gate",
            "may_move_to_done",
            "validates_completion_evidence",
        ):
            self.assertFalse(packet["review"]["authority"][field])
        self.assertLessEqual(
            len(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()),
            MAX_PACKET_BYTES,
        )
        recorded = self.linear.updates[-1]
        self.assertIn("Status: `COMPLETED`", recorded)
        self.assertIn("Verdict: `Approve`", recorded)
        self.assertIn("advisory data only", recorded)

    def test_failure_is_attempt_bounded_visible_and_never_completion_evidence(self):
        backend = Backend(error=TimeoutError("synthetic bounded timeout"))
        result = self.review().run(backend)

        self.assertEqual("failed", result["status"])
        self.assertEqual(2, result["attempts"])
        self.assertFalse(result["completion_evidence"])
        self.assertEqual(2, len(backend.calls))
        recorded = self.linear.updates[-1]
        self.assertIn("Status: `FAILED`", recorded)
        self.assertIn("Attempts: `2/2`", recorded)
        self.assertIn("no approval or completion claim", recorded)

    def test_malformed_review_is_a_recorded_bounded_failure(self):
        invalid = self.approval()
        invalid["findings"][0]["blocking"] = True
        result = self.review().run(Backend(invalid))

        self.assertEqual("failed", result["status"])
        self.assertIn(
            "approval cannot contain blocking findings", self.linear.updates[-1]
        )

    def test_replay_does_not_request_or_record_the_same_review_twice(self):
        first = Backend(self.approval())
        self.review("stable-review").run(first)
        replay = Backend(self.approval())
        result = self.review("stable-review").run(replay)

        self.assertEqual("already_recorded", result["status"])
        self.assertEqual([], replay.calls)
        self.assertEqual(1, len(self.linear.updates))

    def test_evidence_write_failure_does_not_repeat_the_reviewer(self):
        backend = Backend(self.approval())

        def unavailable(_body):
            raise TimeoutError("synthetic Linear evidence failure")

        self.linear.upsert_workpad = unavailable
        with self.assertRaisesRegex(TimeoutError, "Linear evidence failure"):
            self.review().run(backend)
        self.assertEqual(1, len(backend.calls))

    def test_candidate_scope_and_human_review_state_fail_closed(self):
        self.linear.issue["state"]["name"] = "In Progress"
        with self.assertRaisesRegex(AdvisoryReviewError, "Human Review"):
            self.review().run(Backend(self.approval()))
        self.linear.issue["state"]["name"] = "Human Review"
        stale = CandidatePullRequest(**{**self.candidate.__dict__, "merged": True})
        with self.assertRaisesRegex(
            AdvisoryReviewError, "outside the fixed issue scope"
        ):
            self.review(candidate=stale).run(Backend(self.approval()))


if __name__ == "__main__":
    unittest.main()
