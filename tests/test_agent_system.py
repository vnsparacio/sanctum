from __future__ import annotations

import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sanctum_agents.authority import (
    Action,
    AuthorityError,
    Role,
    assert_repository_unchanged,
    implementation_eligible,
    validate_action,
    validate_issue_mutation,
)
from sanctum_agents.config import ConfigError, load_config, validate_model_catalog
from sanctum_agents.integrations import LinearGraphQLClient, MissingAuth
from sanctum_agents.management import (
    Evidence,
    MalformedModelOutput,
    parse_findings,
    suppress_duplicates,
)
from sanctum_agents.reasoner import CodexReasoner
from sanctum_agents.repo_steward import collect_evidence, run_repo_steward
from sanctum_agents.runtime import (
    Budget,
    BudgetExceeded,
    ExclusiveRoleLock,
    JsonlRunLog,
    RunMode,
    ensure_private_prefix,
    new_run_id,
)
from sanctum_agents.supervisor import BoundedProcess


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "agents.json"


def catalog() -> list[dict[str, object]]:
    return [
        {
            "id": model,
            "supportedReasoningEfforts": [
                {"reasoningEffort": effort}
                for effort in ("low", "medium", "high", "xhigh", "max", "ultra")
            ],
        }
        for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
    ]


class ConfigurationTests(unittest.TestCase):
    def test_central_config_and_exact_gate(self):
        config = load_config(CONFIG)
        self.assertEqual("gpt-5.6-terra", config.model_for("repo_steward").model)
        self.assertEqual("gpt-5.6-luna", config.model_for("triage").model)
        self.assertEqual(1, config.symphony["max_concurrency"])
        validate_model_catalog(config, catalog())

    def test_unavailable_model_has_no_fallback(self):
        with self.assertRaisesRegex(ConfigError, "configured model unavailable"):
            validate_model_catalog(load_config(CONFIG), catalog()[1:])

    def test_runtime_prefix_must_stay_outside_source(self):
        config = load_config(CONFIG)
        with self.assertRaisesRegex(ConfigError, "outside the source repository"):
            config.runtime_prefix({"SANCTUM_AGENT_PREFIX": str(ROOT / "state" / "agents")})

    def test_changed_execution_gate_fails_closed(self):
        raw = json.loads(CONFIG.read_text())
        raw["project"]["implementation_gate"]["status"] = "Backlog"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agents.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ConfigError, "implementation gate"):
                load_config(path)


class AuthorityTests(unittest.TestCase):
    def test_eligibility_requires_both_gate_conditions(self):
        self.assertTrue(implementation_eligible("Ready for Agent", ["symphony", "security"]))
        self.assertFalse(implementation_eligible("Backlog", ["symphony"]))
        self.assertFalse(implementation_eligible("Ready for Agent", ["security"]))

    def test_management_agents_cannot_authorize_or_modify_code(self):
        for role in (Role.REPO_STEWARD, Role.PRODUCT_SCOUT, Role.TRIAGE):
            with self.subTest(role=role):
                with self.assertRaises(AuthorityError):
                    validate_action(role, Action.MODIFY_CODE)
                with self.assertRaises(AuthorityError):
                    validate_issue_mutation(role, {"state": "Ready for Agent"})
                with self.assertRaises(AuthorityError):
                    validate_issue_mutation(role, {"add_labels": ["symphony"]})

    def test_role_specific_transitions(self):
        validate_issue_mutation(Role.REPO_STEWARD, {"state": "Triage"})
        validate_issue_mutation(Role.TRIAGE, {"state": "Backlog"})
        validate_issue_mutation(Role.IMPLEMENTATION, {"state": "Human Review"})
        with self.assertRaises(AuthorityError):
            validate_issue_mutation(Role.IMPLEMENTATION, {"state": "Done"})
        with self.assertRaises(AuthorityError):
            validate_issue_mutation(Role.REVIEWER, {"state": "Rework"})

    def test_management_and_review_repository_changes_fail_closed(self):
        for role in (Role.REPO_STEWARD, Role.PRODUCT_SCOUT, Role.TRIAGE, Role.REVIEWER):
            with self.assertRaises(AuthorityError):
                assert_repository_unchanged("", " M source.py\n", role)


class RuntimeTests(unittest.TestCase):
    def test_budget_counters_and_time(self):
        now = [10.0]
        budget = Budget(5, 1, 1, 1, 1, 5, clock=lambda: now[0])
        budget.consume("items")
        with self.assertRaises(BudgetExceeded) as caught:
            budget.consume("items")
        self.assertEqual("items", caught.exception.reason)
        now[0] = 16.0
        with self.assertRaises(BudgetExceeded) as caught:
            budget.check_time()
        self.assertEqual("wall_clock_seconds", caught.exception.reason)

    def test_lock_prevents_overlap_and_recovers_dead_stale_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "repo_steward.lock"
            first = ExclusiveRoleLock(path, stale_seconds=10, clock=lambda: 100)
            with first.acquired_for("one"):
                with self.assertRaisesRegex(RuntimeError, "already running"):
                    ExclusiveRoleLock(path, stale_seconds=10, clock=lambda: 100).acquire("two")
            path.write_text(json.dumps({"pid": 99999999, "run_id": "old", "created_at": 1}))
            second = ExclusiveRoleLock(path, stale_seconds=10, clock=lambda: 100)
            with second.acquired_for("new"):
                self.assertEqual("new", json.loads(path.read_text())["run_id"])
            self.assertFalse(path.exists())

    def test_private_prefix_and_structured_log_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "private"
            ensure_private_prefix(prefix)
            run_id = new_run_id("triage", now=0)
            log = JsonlRunLog(prefix / "logs" / "run.jsonl", run_id, "triage", RunMode.SHADOW)
            log.emit("completed", count=2)
            record = json.loads(log.path.read_text())
            self.assertEqual(run_id, record["run_id"])
            self.assertEqual("shadow", record["mode"])
            self.assertEqual(0o600, stat.S_IMODE(log.path.stat().st_mode))
            self.assertEqual(0o700, stat.S_IMODE(prefix.stat().st_mode))

    def test_log_identity_fields_cannot_be_overridden(self):
        with tempfile.TemporaryDirectory() as directory:
            log = JsonlRunLog(Path(directory) / "run.jsonl", "real", "triage", RunMode.DRY_RUN)
            log.emit("complete", run_id="forged", role="implementation", mode="live")
            record = json.loads(log.path.read_text())
            self.assertEqual("real", record["run_id"])
            self.assertEqual("triage", record["role"])
            self.assertEqual("dry-run", record["mode"])

    def test_missing_linear_auth_is_explicit(self):
        with self.assertRaises(MissingAuth):
            LinearGraphQLClient(environ={}).query("query { viewer { id } }")


class SupervisorTests(unittest.TestCase):
    def run_child(self, code: str, budget: Budget, **kwargs):
        return BoundedProcess(grace_seconds=0.1).run(
            [sys.executable, "-u", "-c", code], ROOT, budget, **kwargs
        )

    def test_hard_wall_clock_stops_active_output(self):
        code = "import time\nwhile True:\n print('active', flush=True); time.sleep(.02)"
        result = self.run_child(code, Budget(.15, 1, 1, 1, 10, 100))
        self.assertEqual("wall_clock_budget", result.reason)
        self.assertIsNotNone(result.returncode)

    def test_stall_and_output_limits(self):
        stalled = self.run_child(
            "import time; time.sleep(2)",
            Budget(2, 1, 1, 1, 10, 100),
            stall_seconds=.1,
        )
        self.assertEqual("stall_budget", stalled.reason)
        noisy = self.run_child(
            "print('x' * 10000)",
            Budget(2, 1, 1, 1, 10, 100),
            output_limit_bytes=100,
        )
        self.assertEqual("output_budget", noisy.reason)
        self.assertLessEqual(len(noisy.output.encode()), 100)

    def test_turn_and_token_limits_use_protocol_events(self):
        events = [
            {"method": "turn/started"},
            {"method": "thread/tokenUsage/updated", "params": {"tokenUsage": {"total": {"totalTokens": 8}}}},
        ]
        code = "import json,time\nfor x in " + repr(events) + ":\n print(json.dumps(x),flush=True); time.sleep(.03)\ntime.sleep(2)"
        token_result = self.run_child(code, Budget(2, 1, 1, 1, 3, 5))
        self.assertEqual("tokens_budget", token_result.reason)
        turn_result = self.run_child(
            "import json,time\nprint(json.dumps({'method':'turn/started'}),flush=True); print(json.dumps({'method':'turn/started'}),flush=True); time.sleep(2)",
            Budget(2, 1, 1, 1, 1, 50),
        )
        self.assertEqual("turns_budget", turn_result.reason)

    def test_turn_and_token_limits_use_codex_exec_events(self):
        events = [
            {"type": "turn.started"},
            {"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 2}},
        ]
        code = "import json,time\nfor x in " + repr(events) + ":\n print(json.dumps(x),flush=True); time.sleep(.03)\ntime.sleep(2)"
        result = self.run_child(code, Budget(2, 1, 1, 1, 3, 8))
        self.assertEqual("tokens_budget", result.reason)


class ManagementFindingTests(unittest.TestCase):
    def setUp(self):
        self.evidence = [Evidence("e-1", "reliability", "A concrete observed condition.", "WORKFLOW.md")]
        self.valid = {
            "findings": [{
                "title": "Add a bounded execution watchdog",
                "summary": "The supplied evidence shows that total execution time is not independently bounded.",
                "severity": "high",
                "recommendation": "Investigate",
                "evidence_ids": ["e-1"],
                "labels": ["reliability", "agent-quality"],
            }]
        }

    def test_malformed_and_unsubstantiated_model_output_fails_closed(self):
        with self.assertRaises(MalformedModelOutput):
            parse_findings({"findings": [], "extra": True}, self.evidence, source="test", max_items=1)
        unknown = json.loads(json.dumps(self.valid))
        unknown["findings"][0]["evidence_ids"] = ["invented"]
        with self.assertRaisesRegex(MalformedModelOutput, "unknown"):
            parse_findings(unknown, self.evidence, source="test", max_items=1)
        forbidden = json.loads(json.dumps(self.valid))
        forbidden["findings"][0]["labels"] = ["symphony"]
        with self.assertRaisesRegex(MalformedModelOutput, "labels"):
            parse_findings(forbidden, self.evidence, source="test", max_items=1)

    def test_duplicate_suppression_is_deterministic(self):
        finding = parse_findings(self.valid, self.evidence, source="test", max_items=1)[0]
        accepted, suppressed = suppress_duplicates([finding, finding], [])
        self.assertEqual([finding], accepted)
        self.assertEqual([finding.fingerprint()], suppressed)
        accepted, suppressed = suppress_duplicates([finding], [finding.fingerprint()])
        self.assertEqual([], accepted)
        self.assertEqual([finding.fingerprint()], suppressed)

    def test_reasoner_extracts_only_final_agent_message(self):
        output = "\n".join([
            json.dumps({"type": "item.completed", "item": {"type": "command_execution", "text": "ignored"}}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(self.valid)}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}),
        ])
        self.assertEqual(self.valid, CodexReasoner._final_message(output))


class RepoStewardTests(unittest.TestCase):
    def test_evidence_scan_is_scoped_and_bounded(self):
        commit, evidence = collect_evidence(
            ROOT,
            ("WORKFLOW.md", "sanctum_agents", "tests"),
            None,
            deep=True,
            max_files=2,
            max_markers=1,
        )
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        scan = next(item for item in evidence if item.id == "scan-range")
        self.assertIn("Inspected 2 scoped tracked files", scan.summary)
        self.assertLessEqual(len([item for item in evidence if item.kind == "debt_marker"]), 1)

    def test_shadow_run_is_read_only_and_suppresses_repeat(self):
        config = load_config(CONFIG)
        before = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"SANCTUM_AGENT_PREFIX": str(Path(directory) / "agents")}
        ):
            first = run_repo_steward(config, ROOT, RunMode.SHADOW, use_model=False)
            second = run_repo_steward(config, ROOT, RunMode.SHADOW, use_model=False)
            self.assertEqual("shadow", first["mode"])
            self.assertEqual(0, first["linear_writes"])
            self.assertTrue(Path(first["artifact_path"]).is_file())
            self.assertGreaterEqual(second["duplicates_suppressed"], 1)
            self.assertEqual([], second["findings"])
        after = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
