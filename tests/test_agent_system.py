from __future__ import annotations

import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
