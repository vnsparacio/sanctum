"""Contracts for content-free, fail-open Symphony/Codex AO correlation."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sanctum_agents.ao_correlation import (
    AttemptObserver,
    BestEffortAOEmitter,
    CorrelationEvent,
    otlp_trace_payload,
    outcome_event,
    persist_active_bindings,
    read_active_binding,
)

ISSUE_UUID = "3191634c-5e1c-445b-a6c3-3821db2611ad"
SESSION = "01a0f012-920d-7c30-958e-f022e5bfcdc3-" "01a0f012-9513-7120-bfb3-bca3745fee72"


def running(started_at="2026-09-30T02:09:00Z", session_id=None):
    return {
        "issue_identifier": "TTE-98",
        "issue_id": ISSUE_UUID,
        "started_at": started_at,
        "session_id": session_id,
        "tokens": {
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        },
        "last_message": "private prompt and tool output must never be emitted",
    }


class AOCorrelationTests(unittest.TestCase):
    def test_issue_attempt_and_session_join_are_stable_and_content_free(self):
        observer = AttemptObserver(
            "implementation-run-a", "standard", "model-a", "high"
        )
        first = observer.observe(
            {"running": [running()], "retrying": [], "blocked": []}
        )
        self.assertEqual(["sanctum.symphony.attempt_observed"], [e.name for e in first])
        attempt_id = first[0].fields["sanctum.symphony.attempt_id"]
        self.assertEqual("TTE-98", first[0].fields["sanctum.issue.identifier"])
        self.assertEqual("model-a", first[0].fields["sanctum.codex.requested_model"])
        self.assertEqual([], observer.observe({"running": [running()]}))

        bound = observer.observe({"running": [running(session_id=SESSION)]})
        self.assertEqual(
            ["sanctum.symphony.codex_session_observed"], [e.name for e in bound]
        )
        self.assertEqual(attempt_id, bound[0].fields["sanctum.symphony.attempt_id"])
        self.assertEqual(SESSION[:36], bound[0].fields["sanctum.codex.thread_id"])
        self.assertNotIn("private prompt", json.dumps(first + bound, default=vars))

        # The same structured source facts reproduce the same attempt ID.
        replay = AttemptObserver("implementation-run-a", "standard", "model-b", "low")
        self.assertEqual(
            attempt_id,
            replay.observe({"running": [running()]})[0].fields[
                "sanctum.symphony.attempt_id"
            ],
        )
        self.assertEqual(
            "model-b",
            replay.observe({"running": [running("2026-09-30T02:10:00Z")]})[0].fields[
                "sanctum.codex.requested_model"
            ],
        )

    def test_retry_and_disappearance_do_not_guess_final_outcome(self):
        observer = AttemptObserver(
            "implementation-run-a", "standard", "model-a", "high"
        )
        start = observer.observe({"running": [running(session_id=SESSION)]})
        retry = observer.observe(
            {
                "running": [],
                "retrying": [{"issue_identifier": "TTE-98", "attempt": 1}],
            }
        )
        self.assertEqual(
            {
                "sanctum.symphony.retry_scheduled",
                "sanctum.symphony.attempt_no_longer_active",
            },
            {event.name for event in retry},
        )
        self.assertEqual(
            1,
            next(
                event.fields["sanctum.symphony.retry_number"]
                for event in retry
                if event.name == "sanctum.symphony.retry_scheduled"
            ),
        )
        self.assertEqual(
            [],
            observer.observe(
                {"retrying": [{"issue_identifier": "TTE-98", "attempt": 1}]}
            ),
        )
        resumed = observer.observe({"running": [running("2026-09-30T02:11:00Z")]})
        self.assertNotEqual(
            start[0].fields["sanctum.symphony.attempt_id"],
            resumed[0].fields["sanctum.symphony.attempt_id"],
        )
        self.assertNotIn("sanctum.workflow.outcome", json.dumps(retry, default=vars))

    def test_blocked_is_observed_but_unstructured_content_is_ignored(self):
        observer = AttemptObserver("run", "standard", "model-a", "medium")
        events = observer.observe(
            {
                "running": [running("not a timestamp", "malformed session")],
                "blocked": [
                    {"issue_identifier": "TTE-98", "error": "private tool body"}
                ],
            }
        )
        self.assertEqual(
            ["sanctum.symphony.blocked_observed"], [e.name for e in events]
        )
        self.assertNotIn("private tool body", json.dumps(events, default=vars))

    def test_otlp_payload_uses_trace_attributes_without_metric_dimensions(self):
        event = CorrelationEvent(
            "sanctum.symphony.attempt_observed",
            {"sanctum.issue.identifier": "TTE-98", "sanctum.symphony.retry_number": 1},
        )
        payload = otlp_trace_payload(event, at_ns=123456789)
        span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(32, len(span["traceId"]))
        self.assertEqual(16, len(span["spanId"]))
        self.assertEqual("123456789", span["startTimeUnixNano"])
        self.assertEqual(
            {"intValue": "1"},
            next(
                item["value"]
                for item in span["attributes"]
                if item["key"] == "sanctum.symphony.retry_number"
            ),
        )
        self.assertNotIn("metrics", json.dumps(payload).lower())

    def test_collector_failure_never_breaks_supervision(self):
        event = CorrelationEvent(
            "sanctum.symphony.attempt_observed", {"sanctum.issue.identifier": "TTE-98"}
        )
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "private" / "evidence.jsonl"
            emitter = BestEffortAOEmitter(journal)
            with patch(
                "sanctum_agents.ao_correlation.request.urlopen",
                side_effect=OSError("collector down"),
            ):
                emitter.emit(event)
            self.assertEqual(0o600, journal.stat().st_mode & 0o777)
            recorded = json.loads(journal.read_text().strip())
            self.assertEqual("TTE-98", recorded["fields"]["sanctum.issue.identifier"])

    def test_git_binding_requires_a_fresh_exact_observed_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace_root = root / "workspaces"
            workspace = workspace_root / "TTE-98"
            workspace.mkdir(parents=True)
            state = root / "state"
            broker_state = state / "git-control-plane"
            broker_state.mkdir(parents=True)
            observer = AttemptObserver(
                "implementation-20260930T020838Z-da1429c96768",
                "standard",
                "model-a",
                "medium",
            )
            entry = running()
            entry["workspace_path"] = str(workspace)
            expected = observer.observe({"running": [entry]})[0].fields[
                "sanctum.symphony.attempt_id"
            ]
            persist_active_bindings(observer, state, workspace_root)
            binding = read_active_binding(broker_state, "TTE-98", workspace)
            self.assertEqual(expected, binding["ao_attempt_id"])
            self.assertIsNone(
                read_active_binding(broker_state, "TTE-98", workspace_root / "other")
            )
            path = state / "ao-correlation" / "active" / "TTE-98.json"
            value = json.loads(path.read_text())
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            self.assertIsNone(
                read_active_binding(
                    broker_state,
                    "TTE-98",
                    workspace,
                    now=value["updated_at"] + 16,
                )
            )
            observer.observe({"running": []})
            persist_active_bindings(observer, state, workspace_root)
            self.assertFalse(path.exists())

    def test_later_outcome_uses_only_matching_structured_facts(self):
        receipt = {
            "kind": "pull-request",
            "number": 163,
            "head": "a" * 40,
            "ao_attempt_id": "b" * 24,
            "ao_run_id": "implementation-20260930T020838Z-da1429c96768",
        }
        pr = {
            "number": 163,
            "baseRefName": "v1.3-dev",
            "headRefName": "symphony/tte-98",
            "headRefOid": "a" * 40,
            "state": "OPEN",
            "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
        }
        validation = {
            "issue_id": "TTE-98",
            "state": "completed",
            "passed": True,
            "profile": "normal-code",
            "completed_at": "2026-09-30T02:12:00Z",
        }
        event = outcome_event(
            "TTE-98",
            [receipt],
            validations=[validation],
            linear_issue={
                "id": ISSUE_UUID,
                "identifier": "TTE-98",
                "state": {"name": "Human Review"},
            },
            pull_request=pr,
        )
        self.assertEqual("b" * 24, event.fields["sanctum.symphony.attempt_id"])
        self.assertEqual("passed", event.fields["sanctum.github.ci_result"])
        self.assertEqual("Human Review", event.fields["sanctum.workflow.linear_state"])
        self.assertTrue(event.fields["sanctum.validation.latest_passed"])
        self.assertNotIn("sanctum.workflow.outcome", event.fields)

        pr["statusCheckRollup"][0]["status"] = "IN_PROGRESS"
        pending = outcome_event("TTE-98", [receipt], pull_request=pr)
        self.assertNotIn("sanctum.github.ci_result", pending.fields)
        pr["headRefOid"] = "c" * 40
        different_head = outcome_event("TTE-98", [receipt], pull_request=pr)
        self.assertNotIn("sanctum.symphony.attempt_id", different_head.fields)
        self.assertNotIn("sanctum.github.commit_sha", different_head.fields)
        self.assertIsNone(outcome_event("TTE-98", []))


if __name__ == "__main__":
    unittest.main()
