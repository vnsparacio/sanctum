from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import error

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
from sanctum_agents.implementation import (
    ImplementationBackendDispatch,
    LifecycleError,
    PullRequestHandoff,
    implementation_backend_dispatch,
    issue_branch,
    validate_dispatch,
    validate_handoff,
    validation_profile,
    worker_class_eligible,
)
from sanctum_agents.integrations import (
    ExternalCallError,
    LinearGraphQLClient,
    MissingAuth,
)
from sanctum_agents.linear_integration import (
    LinearMetadataError,
    LinearWriter,
    capture_qualified_metadata,
    engineering_finding_proposal,
    load_qualified_metadata,
    product_discovery_proposal,
    triage_update_variables,
)
from sanctum_agents.management import (
    Evidence,
    Finding,
    MalformedModelOutput,
    parse_findings,
    suppress_duplicates,
)
from sanctum_agents.product_scout import (
    ProductDiscovery,
    ResearchSource,
    parse_research,
    run_product_scout,
)
from sanctum_agents.reasoner import CodexReasoner
from sanctum_agents.repo_steward import (
    _hard_runtime_control_gaps,
    collect_evidence,
    run_repo_steward,
)
from sanctum_agents.reviewer import load_packet, parse_review, run_reviewer
from sanctum_agents.runtime import (
    Budget,
    BudgetExceeded,
    ExclusiveRoleLock,
    JsonlRunLog,
    RunMode,
    ensure_private_prefix,
    new_run_id,
)
from sanctum_agents.scheduler import ScheduleError, load_schedule_plan
from sanctum_agents.supervisor import BoundedProcess
from sanctum_agents.symphony_recovery import (
    _candidate,
    _grant,
    _notify,
    _report,
    run_with_recovery,
)
from sanctum_agents.symphony_supervisor import (
    TerminationClass,
    _ledger_epoch_sha256,
    _ledger_totals,
    _sanitized_supervisor_environment,
    _state_api_grace_seconds,
    classify_termination,
    evaluate_snapshot,
    load_continuations,
    preflight,
    resume_from_incident,
    supervise,
    validation_environment_violations,
)
from sanctum_agents.triage import (
    capture_live_snapshot,
    load_snapshot,
    parse_decisions,
    run_triage,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "agents.json"
TRIAGE_FIXTURE = ROOT / "tests" / "fixtures" / "linear-triage-snapshot.json"
REVIEW_FIXTURE = ROOT / "tests" / "fixtures" / "reviewer-packet.json"
LINEAR_METADATA_FIXTURE = ROOT / "tests" / "fixtures" / "linear-metadata.json"
SCHEDULES = ROOT / "config" / "schedules.json"
PROTECTED_BRANCH_RULESET = ROOT / ".github" / "rulesets" / "protected-branches.json"


def catalog() -> list[dict[str, object]]:
    return [
        {
            "id": model,
            "supportedReasoningEfforts": [
                {"reasoningEffort": effort}
                for effort in ("low", "medium", "high", "xhigh", "max", "ultra")
            ],
        }
        for model in (
            "gpt-6-astra",
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
        )
    ]


class ConfigurationTests(unittest.TestCase):
    def test_protected_branch_ruleset_preserves_pr_flow_and_admin_only_bypass(self):
        ruleset = json.loads(PROTECTED_BRANCH_RULESET.read_text())

        self.assertEqual("branch", ruleset["target"])
        self.assertEqual("active", ruleset["enforcement"])
        self.assertEqual(
            ["refs/heads/main", "refs/heads/v1.3-dev"],
            ruleset["conditions"]["ref_name"]["include"],
        )
        self.assertEqual([], ruleset["conditions"]["ref_name"]["exclude"])

        rules = {rule["type"]: rule for rule in ruleset["rules"]}
        self.assertEqual({"deletion", "non_fast_forward", "pull_request"}, set(rules))
        pull_requests = rules["pull_request"]["parameters"]
        self.assertEqual(0, pull_requests["required_approving_review_count"])
        self.assertTrue(pull_requests["required_review_thread_resolution"])
        self.assertEqual(
            ["merge", "squash", "rebase"],
            pull_requests["allowed_merge_methods"],
        )

        self.assertEqual(
            [
                {
                    "actor_id": 5,
                    "actor_type": "RepositoryRole",
                    "bypass_mode": "always",
                }
            ],
            ruleset["bypass_actors"],
        )

    def write_timeout_config(self, directory: str, value: object) -> Path:
        raw = json.loads(CONFIG.read_text())
        raw["roles"]["implementation"]["wall_clock_seconds"] = value
        path = Path(directory) / "agents.json"
        path.write_text(json.dumps(raw))
        return path

    def test_central_config_and_exact_gate(self):
        config = load_config(CONFIG)
        self.assertEqual("gpt-5.6-terra", config.model_for("repo_steward").model)
        self.assertEqual("gpt-5.6-luna", config.model_for("triage").model)
        self.assertEqual("gpt-5.6-terra", config.model_for("triage_escalation").model)
        self.assertEqual("gpt-6-astra", config.model_for("implementation_deep").model)
        self.assertEqual(5, config.symphony["max_concurrency"])
        self.assertEqual(120, config.symphony["state_startup_grace_seconds"])
        self.assertEqual(30, config.symphony["state_stall_grace_seconds"])
        self.assertEqual("codex", config.symphony["implementation_backend"])
        validate_model_catalog(config, catalog())

    def test_state_api_startup_and_runtime_grace_are_separate(self):
        config = load_config(CONFIG)

        self.assertEqual(120, _state_api_grace_seconds(config, False))
        self.assertEqual(30, _state_api_grace_seconds(config, True))

    def test_unknown_implementation_backend_is_rejected(self):
        raw = json.loads(CONFIG.read_text())
        raw["symphony"]["implementation_backend"] = "issue-selected"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agents.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(
                ConfigError, "implementation backend must be codex or work-mode"
            ):
                load_config(path)

    def test_unavailable_model_has_no_fallback(self):
        with self.assertRaisesRegex(ConfigError, "configured model unavailable"):
            validate_model_catalog(load_config(CONFIG), catalog()[1:])

    def test_runtime_prefix_must_stay_outside_source(self):
        config = load_config(CONFIG)
        with self.assertRaisesRegex(ConfigError, "outside the source repository"):
            config.runtime_prefix(
                {"SANCTUM_AGENT_PREFIX": str(ROOT / "state" / "agents")}
            )

    def test_changed_execution_gate_fails_closed(self):
        raw = json.loads(CONFIG.read_text())
        raw["project"]["implementation_gate"]["status"] = "Backlog"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agents.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ConfigError, "implementation gate"):
                load_config(path)

    def test_implementation_wall_clock_timeout_default(self):
        config = load_config(CONFIG)
        self.assertEqual(21600, config.roles["implementation"].wall_clock_seconds)

    def test_implementation_wall_clock_timeout_valid_override_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = self.write_timeout_config(directory, 1800)
            raw = json.loads(config_path.read_text())
            binary = root / "symphony"
            binary.write_text("#!/bin/sh\n")
            binary.chmod(0o700)
            raw["symphony"]["default_binary"] = str(binary)
            config_path.write_text(json.dumps(raw))
            config = load_config(config_path)
            github_config = root / "github-config"
            github_config.mkdir(mode=0o700)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            gh = bin_dir / "gh"
            gh.write_text("#!/bin/sh\nexit 0\n")
            gh.chmod(0o700)

            status = preflight(
                config,
                ROOT,
                {
                    "LINEAR_API_KEY": "synthetic-test-token",
                    "SYMPHONY_WORKSPACE_ROOT": str(root / "workspaces"),
                    "SANCTUM_GIT_GH_CONFIG_DIR": str(github_config),
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                },
            )

            self.assertEqual(1800, config.roles["implementation"].wall_clock_seconds)
            self.assertEqual(1800, status["wall_clock_timeout_seconds"])
            self.assertEqual("standard", status["worker_class"])
            self.assertEqual("codex", status["implementation_backend"])
            self.assertEqual(str(ROOT / "WORKFLOW.md"), status["workflow"])

    def test_implementation_wall_clock_timeout_rejects_malformed_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_timeout_config(directory, "one hour")
            with self.assertRaisesRegex(
                ConfigError,
                "roles.implementation.wall_clock_seconds must be a positive integer",
            ):
                load_config(path)

    def test_implementation_wall_clock_timeout_rejects_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_timeout_config(directory, 0)
            with self.assertRaisesRegex(
                ConfigError,
                "roles.implementation.wall_clock_seconds must be a positive integer",
            ):
                load_config(path)

    def test_implementation_wall_clock_timeout_rejects_negative_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_timeout_config(directory, -1)
            with self.assertRaisesRegex(
                ConfigError,
                "roles.implementation.wall_clock_seconds must be a positive integer",
            ):
                load_config(path)


class AuthorityTests(unittest.TestCase):
    def test_eligibility_requires_both_gate_conditions(self):
        self.assertTrue(
            implementation_eligible("Ready for Agent", ["symphony", "security"])
        )
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
                    ExclusiveRoleLock(
                        path, stale_seconds=10, clock=lambda: 100
                    ).acquire("two")
            path.write_text(
                json.dumps({"pid": 99999999, "run_id": "old", "created_at": 1})
            )
            second = ExclusiveRoleLock(path, stale_seconds=10, clock=lambda: 100)
            with second.acquired_for("new"):
                self.assertEqual("new", json.loads(path.read_text())["run_id"])
            self.assertFalse(path.exists())

    def test_private_prefix_and_structured_log_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "private"
            ensure_private_prefix(prefix)
            run_id = new_run_id("triage", now=0)
            log = JsonlRunLog(
                prefix / "logs" / "run.jsonl", run_id, "triage", RunMode.SHADOW
            )
            log.emit("completed", count=2)
            record = json.loads(log.path.read_text())
            self.assertEqual(run_id, record["run_id"])
            self.assertEqual("shadow", record["mode"])
            self.assertEqual(0o600, stat.S_IMODE(log.path.stat().st_mode))
            self.assertEqual(0o700, stat.S_IMODE(prefix.stat().st_mode))

    def test_log_identity_fields_cannot_be_overridden(self):
        with tempfile.TemporaryDirectory() as directory:
            log = JsonlRunLog(
                Path(directory) / "run.jsonl", "real", "triage", RunMode.DRY_RUN
            )
            log.emit("complete", run_id="forged", role="implementation", mode="live")
            record = json.loads(log.path.read_text())
            self.assertEqual("real", record["run_id"])
            self.assertEqual("triage", record["role"])
            self.assertEqual("dry-run", record["mode"])

    def test_missing_linear_auth_is_explicit(self):
        with self.assertRaises(MissingAuth):
            LinearGraphQLClient(environ={}).query("query { viewer { id } }")

    def test_failed_linear_transport_is_explicit_and_not_retried(self):
        with patch(
            "sanctum_agents.integrations.request.urlopen",
            side_effect=error.URLError("offline"),
        ) as opened:
            with self.assertRaisesRegex(ExternalCallError, "Linear request failed"):
                LinearGraphQLClient(environ={"LINEAR_API_KEY": "synthetic"}).query(
                    "query { viewer { id } }"
                )
        opened.assert_called_once()


class SupervisorTests(unittest.TestCase):
    def run_child(self, code: str, budget: Budget, **kwargs):
        return BoundedProcess(grace_seconds=0.1).run(
            [sys.executable, "-u", "-c", code], ROOT, budget, **kwargs
        )

    def test_hard_wall_clock_stops_active_output(self):
        code = "import time\nwhile True:\n print('active', flush=True); time.sleep(.02)"
        result = self.run_child(code, Budget(0.15, 1, 1, 1, 10, 100))
        self.assertEqual("wall_clock_budget", result.reason)
        self.assertIsNotNone(result.returncode)

    def test_stall_and_output_limits(self):
        stalled = self.run_child(
            "import time; time.sleep(2)",
            Budget(2, 1, 1, 1, 10, 100),
            stall_seconds=0.1,
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
            {
                "method": "thread/tokenUsage/updated",
                "params": {"tokenUsage": {"total": {"totalTokens": 8}}},
            },
        ]
        code = (
            "import json,time\nfor x in "
            + repr(events)
            + ":\n print(json.dumps(x),flush=True); time.sleep(.03)\ntime.sleep(2)"
        )
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
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 7, "output_tokens": 2},
            },
        ]
        code = (
            "import json,time\nfor x in "
            + repr(events)
            + ":\n print(json.dumps(x),flush=True); time.sleep(.03)\ntime.sleep(2)"
        )
        result = self.run_child(code, Budget(2, 1, 1, 1, 3, 8))
        self.assertEqual("tokens_budget", result.reason)


class ManagementFindingTests(unittest.TestCase):
    def setUp(self):
        self.evidence = [
            Evidence(
                "e-1", "reliability", "A concrete observed condition.", "WORKFLOW.md"
            )
        ]
        self.valid = {
            "findings": [
                {
                    "title": "Add a bounded execution watchdog",
                    "summary": "The supplied evidence shows that total execution time is not independently bounded.",
                    "severity": "high",
                    "recommendation": "Investigate",
                    "evidence_ids": ["e-1"],
                    "labels": ["reliability", "agent-quality"],
                }
            ]
        }

    def test_malformed_and_unsubstantiated_model_output_fails_closed(self):
        with self.assertRaises(MalformedModelOutput):
            parse_findings(
                {"findings": [], "extra": True},
                self.evidence,
                source="test",
                max_items=1,
            )
        unknown = json.loads(json.dumps(self.valid))
        unknown["findings"][0]["evidence_ids"] = ["invented"]
        with self.assertRaisesRegex(MalformedModelOutput, "unknown"):
            parse_findings(unknown, self.evidence, source="test", max_items=1)
        forbidden = json.loads(json.dumps(self.valid))
        forbidden["findings"][0]["labels"] = ["symphony"]
        with self.assertRaisesRegex(MalformedModelOutput, "labels"):
            parse_findings(forbidden, self.evidence, source="test", max_items=1)

    def test_duplicate_suppression_is_deterministic(self):
        finding = parse_findings(self.valid, self.evidence, source="test", max_items=1)[
            0
        ]
        accepted, suppressed = suppress_duplicates([finding, finding], [])
        self.assertEqual([finding], accepted)
        self.assertEqual([finding.fingerprint()], suppressed)
        accepted, suppressed = suppress_duplicates([finding], [finding.fingerprint()])
        self.assertEqual([], accepted)
        self.assertEqual([finding.fingerprint()], suppressed)

    def test_reasoner_extracts_only_final_agent_message(self):
        output = "\n".join(
            [
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "command_execution", "text": "ignored"},
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": json.dumps(self.valid),
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    }
                ),
            ]
        )
        self.assertEqual(self.valid, CodexReasoner._final_message(output))


class RepoStewardTests(unittest.TestCase):
    def test_hard_runtime_control_is_verified_across_effective_sources(self):
        self.assertEqual([], _hard_runtime_control_gaps(ROOT))

    def test_hard_runtime_control_fails_closed_without_retry_enforcement(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "config").mkdir()
            (repository / "sanctum_agents").mkdir()
            (repository / "WORKFLOW.md").write_text(
                "The outer Sanctum supervisor provides the hard total-runtime "
                "wall-clock boundary.\n"
            )
            (repository / "config" / "agents.json").write_text(
                json.dumps({"roles": {"implementation": {"wall_clock_seconds": 3600}}})
            )
            (repository / "sanctum_agents" / "symphony_supervisor.py").write_text(
                'ledger_path = prefix / "state" / "symphony-ledger.json"\n'
                "ledger_path.read_text()\n"
                "_save_json(ledger_path, ledger)\n"
                'elapsed = now - record["first_seen"]\n'
                "if elapsed > wall_clock_seconds:\n"
                "    stop_running_work()\n"
            )
            gaps = _hard_runtime_control_gaps(repository)
        self.assertEqual(
            [
                (
                    "sanctum_agents/symphony_supervisor.py",
                    "the supervisor does not enforce the wall-clock limit for both running and retrying work",
                )
            ],
            gaps,
        )

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
        self.assertLessEqual(
            len([item for item in evidence if item.kind == "debt_marker"]), 1
        )

    def test_python_marker_scan_ignores_literals_but_keeps_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Sanctum Test"],
                cwd=repository,
                check=True,
            )
            source = repository / "tests"
            source.mkdir()
            (source / "test_one.py").write_text(
                'fixture = "# TODO fixture data\\n"\n# TODO actual debt\n'
            )
            subprocess.run(
                ["git", "add", "tests/test_one.py"], cwd=repository, check=True
            )
            subprocess.run(
                ["git", "commit", "-qm", "fixture"], cwd=repository, check=True
            )
            _, evidence = collect_evidence(
                repository, ("tests",), None, deep=True, max_markers=5
            )
        markers = [item for item in evidence if item.kind == "debt_marker"]
        self.assertEqual(["tests/test_one.py:2"], [item.location for item in markers])

    def test_first_or_shallow_commit_falls_back_to_bounded_tracked_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Sanctum Test"],
                cwd=repository,
                check=True,
            )
            source = repository / "tests"
            source.mkdir()
            (source / "test_one.py").write_text("# TODO bounded fixture\n")
            subprocess.run(
                ["git", "add", "tests/test_one.py"], cwd=repository, check=True
            )
            subprocess.run(
                ["git", "commit", "-qm", "fixture"], cwd=repository, check=True
            )
            _, evidence = collect_evidence(
                repository, ("tests",), None, max_files=1, max_markers=1
            )
        scan = next(item for item in evidence if item.id == "scan-range")
        self.assertIn("Inspected 1 scoped tracked files from full tree", scan.summary)

    def test_shadow_run_is_read_only_and_suppresses_repeat(self):
        config = load_config(CONFIG)
        before = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                "os.environ", {"SANCTUM_AGENT_PREFIX": str(Path(directory) / "agents")}
            ),
        ):
            first = run_repo_steward(config, ROOT, RunMode.SHADOW, use_model=False)
            second = run_repo_steward(config, ROOT, RunMode.SHADOW, use_model=False)
            self.assertEqual("shadow", first["mode"])
            self.assertEqual(0, first["linear_writes"])
            self.assertTrue(Path(first["artifact_path"]).is_file())
            self.assertEqual(0, second["duplicates_suppressed"])
            self.assertEqual([], second["findings"])
        after = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(before, after)


class ProductScoutTests(unittest.TestCase):
    def fixture(self) -> dict[str, object]:
        return {
            "sources": [
                {
                    "id": "primary-1",
                    "url": "https://github.com/example/private-agent/releases/tag/v1.2.3",
                    "title": "Private agent runtime 1.2.3",
                    "published_at": "2026-09-18",
                    "kind": "release_notes",
                    "summary": "The release adds bounded worker leases and deterministic cleanup receipts.",
                },
                {
                    "id": "community-1",
                    "url": "https://news.ycombinator.com/item?id=123456",
                    "title": "Operator discussion of runaway agents",
                    "published_at": "2026-09-18",
                    "kind": "community",
                    "summary": "Operators describe repeated failures caused by workers without total runtime caps.",
                },
            ],
            "findings": [
                {
                    "title": "Compare bounded worker lease receipts",
                    "summary": "The release provides a concrete implementation of bounded leases with cleanup evidence.",
                    "sanctum_connection": "Sanctum can compare the receipt design with its implementation-worker watchdog without changing authority boundaries.",
                    "recommendation": "Investigate",
                    "source_ids": ["primary-1", "community-1"],
                    "labels": ["product-discovery", "research", "agent-quality"],
                }
            ],
        }

    def test_research_requires_public_sources_and_credible_evidence(self):
        sources, findings = parse_research(self.fixture(), max_sources=3, max_items=2)
        self.assertEqual(2, len(sources))
        self.assertEqual("Investigate", findings[0].recommendation)
        private = json.loads(json.dumps(self.fixture()))
        private["sources"][0]["url"] = "https://127.0.0.1/private"
        with self.assertRaisesRegex(MalformedModelOutput, "public HTTPS"):
            parse_research(private, max_sources=3, max_items=2)
        community_only = json.loads(json.dumps(self.fixture()))
        community_only["findings"][0]["source_ids"] = ["community-1"]
        with self.assertRaisesRegex(MalformedModelOutput, "credible"):
            parse_research(community_only, max_sources=3, max_items=2)

    def test_research_caps_and_authority_labels_fail_closed(self):
        payload = self.fixture()
        with self.assertRaisesRegex(MalformedModelOutput, "source limit"):
            parse_research(payload, max_sources=1, max_items=2)
        forbidden = json.loads(json.dumps(payload))
        forbidden["findings"][0]["labels"] = ["product-discovery", "symphony"]
        with self.assertRaisesRegex(MalformedModelOutput, "labels"):
            parse_research(forbidden, max_sources=3, max_items=2)

    def test_shadow_fixture_is_read_only_and_deduplicated(self):
        config = load_config(CONFIG)
        before = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                "os.environ", {"SANCTUM_AGENT_PREFIX": str(Path(directory) / "agents")}
            ),
        ):
            first = run_product_scout(
                config, ROOT, RunMode.SHADOW, fixture_payload=self.fixture()
            )
            second = run_product_scout(
                config, ROOT, RunMode.SHADOW, fixture_payload=self.fixture()
            )
            self.assertEqual(0, first["linear_writes"])
            self.assertEqual(1, len(first["findings"]))
            self.assertEqual(1, second["duplicates_suppressed"])
            self.assertEqual([], second["findings"])
        after = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(before, after)

    def test_dry_run_is_labeled_and_never_writes_linear(self):
        config = load_config(CONFIG)
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                "os.environ", {"SANCTUM_AGENT_PREFIX": str(Path(directory) / "agents")}
            ),
        ):
            result = run_product_scout(
                config, ROOT, RunMode.DRY_RUN, fixture_payload=self.fixture()
            )
        self.assertEqual("dry-run", result["mode"])
        self.assertEqual(0, result["linear_writes"])


class TriageTests(unittest.TestCase):
    def fixture(self) -> dict[str, object]:
        return {
            "decisions": [
                {
                    "issue_id": "issue-a",
                    "action": "Duplicate",
                    "reason": "The existing backlog issue has the same hard runtime watchdog scope and evidence.",
                    "duplicate_of": "issue-c",
                    "related_ids": ["issue-b", "issue-c"],
                },
                {
                    "issue_id": "issue-b",
                    "action": "Leave",
                    "reason": "A human should confirm whether this is also fully covered by the backlog item.",
                    "duplicate_of": None,
                    "related_ids": ["issue-a", "issue-c"],
                },
            ],
            "owner_briefing": "One concrete duplicate can be canceled and linked; one uncertain overlap remains for owner review.",
        }

    def test_duplicate_maps_to_canceled_and_never_execution_gate(self):
        issues = load_snapshot(TRIAGE_FIXTURE, max_items=20)
        decisions, briefing = parse_decisions(self.fixture(), issues, max_items=20)
        self.assertEqual(
            {"state": "Canceled", "duplicate_of": "issue-c"}, decisions[0].mutation
        )
        self.assertIsNone(decisions[1].mutation)
        self.assertNotIn(
            "Ready for Agent", json.dumps([item.mutation for item in decisions])
        )
        self.assertNotIn("symphony", json.dumps([item.mutation for item in decisions]))
        self.assertIn("owner review", briefing)

    def test_live_snapshot_is_bounded_private_and_source_labeled(self):
        class FakeClient:
            def query(self, query, variables):
                self.query_text = query
                self.variables = variables
                return {
                    "project": {
                        "issues": {
                            "pageInfo": {"hasNextPage": False},
                            "nodes": [
                                {
                                    "id": "issue-live",
                                    "identifier": "SAN-7",
                                    "title": "Review bounded finding",
                                    "description": "Evidence: https://example.com/source",
                                    "url": "https://linear.example/SAN-7",
                                    "state": {"name": "Triage"},
                                    "labels": {
                                        "nodes": [
                                            {"name": "reliability"},
                                            {"name": "Repo Steward"},
                                        ]
                                    },
                                },
                                {
                                    "id": "issue-ignored",
                                    "identifier": "SAN-8",
                                    "title": "Implementation item",
                                    "description": "Not a management queue item.",
                                    "url": "https://linear.example/SAN-8",
                                    "state": {"name": "In Progress"},
                                    "labels": {"nodes": [{"name": "symphony"}]},
                                },
                            ],
                        }
                    }
                }

        metadata = load_qualified_metadata(
            LINEAR_METADATA_FIXTURE, "sanctum-v13-aafdb6e2bb76"
        )
        client = FakeClient()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "linear-triage-snapshot.json"
            payload = capture_live_snapshot(client, metadata, path, max_items=20)
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            self.assertEqual(
                payload["issues"],
                [
                    {
                        "id": "issue-live",
                        "identifier": "SAN-7",
                        "title": "Review bounded finding",
                        "description": "Evidence: https://example.com/source",
                        "state": "Triage",
                        "labels": ["reliability", "Repo Steward"],
                        "source": "Repo Steward",
                        "evidence_urls": [
                            "https://linear.example/SAN-7",
                            "https://example.com/source",
                        ],
                    }
                ],
            )
            loaded = load_snapshot(path, max_items=20)
            self.assertEqual(1, len(loaded))
            self.assertEqual("issue-live", loaded[0].id)
            self.assertEqual("Repo Steward", loaded[0].source)
            self.assertEqual(
                (
                    "https://linear.example/SAN-7",
                    "https://example.com/source",
                ),
                loaded[0].evidence_urls,
            )
        self.assertIn("SanctumTriageSnapshot", client.query_text)
        self.assertEqual(metadata.project_id, client.variables["projectId"])

    def test_live_snapshot_fails_closed_if_linear_requires_pagination(self):
        class PaginatedClient:
            def query(self, query, variables):
                return {
                    "project": {
                        "issues": {
                            "pageInfo": {"hasNextPage": True},
                            "nodes": [],
                        }
                    }
                }

        metadata = load_qualified_metadata(
            LINEAR_METADATA_FIXTURE, "sanctum-v13-aafdb6e2bb76"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "linear-triage-snapshot.json"
            with self.assertRaisesRegex(MalformedModelOutput, "requires pagination"):
                capture_live_snapshot(PaginatedClient(), metadata, path, max_items=20)
            self.assertFalse(path.exists())

    def test_unknown_and_non_triage_targets_fail_closed(self):
        issues = load_snapshot(TRIAGE_FIXTURE, max_items=20)
        unknown = json.loads(json.dumps(self.fixture()))
        unknown["decisions"][0]["issue_id"] = "fabricated"
        with self.assertRaisesRegex(MalformedModelOutput, "target"):
            parse_decisions(unknown, issues, max_items=20)
        backlog = json.loads(json.dumps(self.fixture()))
        backlog["decisions"][0]["issue_id"] = "issue-c"
        with self.assertRaisesRegex(MalformedModelOutput, "target"):
            parse_decisions(backlog, issues, max_items=20)

    def test_shadow_fixture_is_read_only_and_terra_escalation_is_explicit(self):
        config = load_config(CONFIG)
        before = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                "os.environ", {"SANCTUM_AGENT_PREFIX": str(Path(directory) / "agents")}
            ),
        ):
            luna = run_triage(
                config,
                ROOT,
                TRIAGE_FIXTURE,
                RunMode.SHADOW,
                decision_fixture=self.fixture(),
            )
            terra = run_triage(
                config,
                ROOT,
                TRIAGE_FIXTURE,
                RunMode.DRY_RUN,
                escalate=True,
                decision_fixture=self.fixture(),
            )
        self.assertEqual("gpt-5.6-luna", luna["model"])
        self.assertEqual("gpt-5.6-terra", terra["model"])
        self.assertEqual("dry-run", terra["mode"])
        self.assertEqual(0, luna["linear_writes"])
        after = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(before, after)


class ImplementationLifecycleTests(unittest.TestCase):
    def test_implementation_backend_dispatch_is_bounded_and_config_only(self):
        symphony = load_config(CONFIG).symphony
        self.assertEqual(
            ImplementationBackendDispatch("codex", "implementation", "WORKFLOW.md"),
            implementation_backend_dispatch(symphony, "standard"),
        )
        selected = {**symphony, "implementation_backend": "work-mode"}
        self.assertEqual(
            ImplementationBackendDispatch(
                "work-mode", "implementation_deep", "WORKFLOW.work-mode.deep.md"
            ),
            implementation_backend_dispatch(selected, "deep"),
        )
        with self.assertRaisesRegex(LifecycleError, "codex or work-mode"):
            implementation_backend_dispatch(
                {**symphony, "implementation_backend": "from-issue-text"},
                "standard",
            )

    def test_branch_name_dispatch_gate_and_human_review_stop(self):
        self.assertEqual("symphony/san-123", issue_branch("SAN-123"))
        validate_dispatch("Ready for Agent", ["security", "symphony", "agent-standard"])
        with self.assertRaises(LifecycleError):
            validate_dispatch("Backlog", ["symphony", "agent-standard"])
        with self.assertRaises(LifecycleError):
            validate_dispatch("Ready for Agent", ["symphony"])
        self.assertTrue(worker_class_eligible(["symphony", "agent-deep"], "deep"))
        self.assertFalse(
            worker_class_eligible(
                ["symphony", "agent-standard", "agent-deep"], "standard"
            )
        )
        valid = PullRequestHandoff(
            "v1.3-dev", "symphony/san-123", False, "Human Review"
        )
        validate_handoff(valid, "SAN-123")
        for invalid in (
            PullRequestHandoff("main", "symphony/san-123", False, "Human Review"),
            PullRequestHandoff("v1.3-dev", "feature/loose", False, "Human Review"),
            PullRequestHandoff("v1.3-dev", "symphony/san-123", True, "Human Review"),
            PullRequestHandoff("v1.3-dev", "symphony/san-123", False, "Done"),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(LifecycleError):
                validate_handoff(invalid, "SAN-123")

    def test_proportional_validation_profiles(self):
        self.assertEqual(
            "docs-config",
            validation_profile(["docs/runbook.md", "config/example.json"]),
        )
        self.assertEqual("normal-code", validation_profile(["router/decision.py"]))
        self.assertEqual("architecture-security", validation_profile(["WORKFLOW.md"]))
        self.assertEqual(
            "architecture-security", validation_profile(["tests/security_contract.py"])
        )

    def test_workflow_pins_model_limits_and_never_merges(self):
        workflow = (ROOT / "WORKFLOW.md").read_text()
        deep_workflow = (ROOT / "WORKFLOW.deep.md").read_text()
        self.assertIn('model="gpt-5.6-sol"', workflow)
        self.assertIn("agent-standard", workflow)
        self.assertIn("max_turns: 20", workflow)
        self.assertIn("turn_timeout_ms: 3600000", workflow)
        self.assertIn("stall_timeout_ms: 900000", workflow)
        self.assertIn("dashboard_enabled: false", workflow)
        self.assertIn("run_validation_profile", workflow)
        self.assertIn('model="gpt-6-astra"', deep_workflow)
        self.assertIn("agent-deep", deep_workflow)
        self.assertIn("max_turns: 30", deep_workflow)
        self.assertIn("Human Review` is a hard stopping point", workflow)
        self.assertIn("github_ensure_issue_pull_request", workflow)
        self.assertNotIn(" gh ", workflow)
        self.assertNotIn("gh pr merge", workflow)

    def test_standard_and_deep_workflows_have_identical_authority(self):
        standard = (ROOT / "WORKFLOW.md").read_text()
        deep = (ROOT / "WORKFLOW.deep.md").read_text()
        normalized = (
            deep.replace("    - agent-deep\n", "    - agent-standard\n")
            .replace("max_turns: 30", "max_turns: 20")
            .replace('model="gpt-6-astra"', 'model="gpt-5.6-sol"')
            .replace('model_reasoning_effort="high"', 'model_reasoning_effort="medium"')
            .replace(
                "Worker class: deep (`agent-deep`).",
                "Worker class: standard (`agent-standard`).",
            )
        )
        self.assertEqual(standard, normalized)


class SymphonySupervisorTests(unittest.TestCase):
    def running(self, session: str, turns: int, tokens: int) -> dict[str, object]:
        return {
            "issue_identifier": "SAN-7",
            "session_id": session,
            "turn_count": turns,
            "tokens": {"total_tokens": tokens},
            "started_at": "1970-01-01T00:01:40Z",
            "last_event_at": "1970-01-01T00:03:15Z",
        }

    def evaluate(self, snapshot, ledger, now=200, runtime_id="runtime-one"):
        return evaluate_snapshot(
            snapshot,
            ledger,
            runtime_id=runtime_id,
            now=now,
            wall_clock_seconds=100,
            max_turns=8,
            max_tokens=500,
            max_retries=2,
        )

    def test_five_workers_are_allowed_but_a_sixth_stops_the_service(self):
        running = []
        for index in range(6):
            entry = self.running(f"session-{index}", 1, 1)
            entry["issue_identifier"] = f"SAN-{index + 1}"
            running.append(entry)
        arguments = dict(
            runtime_id="five-worker-service",
            now=200,
            wall_clock_seconds=100,
            max_turns=8,
            max_tokens=500,
            max_retries=2,
            max_concurrency=5,
        )
        self.assertEqual(
            [], evaluate_snapshot({"running": running[:5]}, {"issues": {}}, **arguments)
        )
        violations = evaluate_snapshot(
            {"running": running}, {"issues": {}}, **arguments
        )
        self.assertEqual(["concurrency_budget"], [item.reason for item in violations])
        self.assertEqual("service", violations[0].issue_identifier)

    def test_cumulative_counters_are_not_summed_across_continuation_sessions(self):
        ledger: dict[str, object] = {"issues": {}}
        first = self.evaluate(
            {"running": [self.running("one", 4, 300)], "retrying": []}, ledger
        )
        self.assertEqual([], first)
        second = self.evaluate(
            {"running": [self.running("two", 5, 400)], "retrying": []}, ledger
        )
        self.assertEqual([], second)
        record = ledger["issues"]["SAN-7"]
        self.assertEqual(5, _ledger_totals(record, 200)["turn_count"])
        self.assertEqual(400, _ledger_totals(record, 200)["tokens"])

    def test_total_turn_and_token_caps_span_supervisor_runtimes(self):
        ledger: dict[str, object] = {"issues": {}}
        first = self.evaluate(
            {"running": [self.running("one", 4, 300)], "retrying": []},
            ledger,
            runtime_id="runtime-one",
        )
        self.assertEqual([], first)
        second = self.evaluate(
            {"running": [self.running("two", 5, 300)], "retrying": []},
            ledger,
            runtime_id="runtime-two",
        )
        self.assertEqual(
            {"turns_budget", "tokens_budget"}, {item.reason for item in second}
        )

    def test_input_and_output_token_high_water_marks_are_preserved(self):
        ledger: dict[str, object] = {"issues": {}}
        entry = self.running("one", 1, 30)
        entry["tokens"] = {
            "total_tokens": 30,
            "input_tokens": 20,
            "output_tokens": 10,
        }
        self.evaluate({"running": [entry], "retrying": []}, ledger)
        runtime = ledger["issues"]["SAN-7"]["runtimes"]["runtime-one"]
        self.assertEqual(20, runtime["input_tokens"])
        self.assertEqual(10, runtime["output_tokens"])

    def test_legacy_session_ledger_uses_cumulative_high_water_marks(self):
        record = {
            "first_seen": 1,
            "last_seen": 2,
            "sessions": {
                "one": {"turns": 1, "tokens": 100},
                "two": {"turns": 2, "tokens": 180},
                "three": {"turns": 3, "tokens": 250},
            },
            "max_retry": 0,
        }
        totals = _ledger_totals(record, 200)
        self.assertEqual(3, totals["turn_count"])
        self.assertEqual(250, totals["tokens"])
        ledger = {"issues": {"SAN-7": record}}
        self.evaluate(
            {"running": [self.running("four", 4, 300)], "retrying": []},
            ledger,
            runtime_id="runtime-two",
        )
        self.assertNotIn("sessions", record)
        self.assertEqual(7, _ledger_totals(record, 200)["turn_count"])
        self.assertEqual(550, _ledger_totals(record, 200)["tokens"])

    def test_supervisor_environment_drops_unrelated_credentials(self):
        value = _sanitized_supervisor_environment(
            {
                "PATH": "/usr/bin",
                "HOME": "/synthetic/home",
                "LINEAR_API_KEY": "linear-secret",
                "GH_TOKEN": "github-secret",
                "AWS_SECRET_ACCESS_KEY": "cloud-secret",
                "SANCTUM_SYMPHONY_BIN": "/reviewed/symphony",
            },
            "SANCTUM_SYMPHONY_BIN",
        )
        self.assertEqual(
            {
                "PATH": "/usr/bin",
                "HOME": "/synthetic/home",
                "LINEAR_API_KEY": "linear-secret",
                "SANCTUM_SYMPHONY_BIN": "/reviewed/symphony",
            },
            value,
        )

    def test_wall_and_retry_caps_are_outer_supervisor_owned(self):
        ledger = {
            "issues": {
                "SAN-7": {
                    "first_seen": 50,
                    "last_seen": 50,
                    "sessions": {},
                    "max_retry": 0,
                }
            }
        }
        running = self.evaluate(
            {"running": [self.running("one", 1, 10)], "retrying": []}, ledger
        )
        self.assertEqual({"wall_clock_budget"}, {item.reason for item in running})
        retry = self.evaluate(
            {
                "running": [],
                "retrying": [{"issue_identifier": "SAN-8", "attempt": 3}],
            },
            {"issues": {}},
            now=200,
        )
        self.assertEqual({"retries_budget"}, {item.reason for item in retry})

    def test_failure_classification_is_deterministic(self):
        self.assertEqual(
            TerminationClass.TOKEN_BUDGET,
            classify_termination("tokens_budget"),
        )
        self.assertEqual(
            TerminationClass.SANDBOX,
            classify_termination(
                "operator_action_required", "/bin/ps operation_not_permitted"
            ),
        )
        self.assertEqual(
            TerminationClass.GIT_CONTROL_PLANE,
            classify_termination("retries_budget", "push result unknown"),
        )
        cases = {
            TerminationClass.MODEL_REASONING: ("failed", "malformed model output"),
            TerminationClass.ENVIRONMENT: ("state_api_stall", None),
            TerminationClass.VALIDATION: ("failed", "test failed"),
            TerminationClass.NETWORK_PROVIDER: ("failed", "provider rate limit"),
            TerminationClass.TIME_BUDGET: ("wall_clock_budget", None),
            TerminationClass.OWNER_ACTION_REQUIRED: (
                "operator_action_required",
                None,
            ),
            TerminationClass.UNKNOWN: ("unclassified", None),
        }
        for expected, (reason, detail) in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(expected, classify_termination(reason, detail))

    def test_fresh_failed_validation_preflight_stops_supervisor_run(self):
        with tempfile.TemporaryDirectory() as root:
            receipts = Path(root) / "receipts" / "SAN-7"
            receipts.mkdir(parents=True)
            (receipts / "normal-code-check.json").write_text(
                json.dumps(
                    {
                        "issue_id": "SAN-7",
                        "state": "completed",
                        "requested_at": "2026-09-21T00:00:00+00:00",
                        "events": [
                            "validation_requested",
                            "environment_preflight_failed",
                        ],
                    }
                )
            )
            snapshot = {"running": [self.running("one", 1, 1)], "retrying": []}
            violations = validation_environment_violations(
                Path(root), snapshot, launched_at=0
            )
            self.assertEqual(1, len(violations))
            self.assertEqual("SANDBOX", violations[0].termination_class)
            self.assertEqual("validation_environment_preflight", violations[0].reason)
            self.assertEqual(
                [],
                validation_environment_violations(
                    Path(root), snapshot, launched_at=2_000_000_000
                ),
            )

    def test_completed_issue_ledger_is_eventually_removed(self):
        ledger = {
            "issues": {
                "SAN-7": {
                    "first_seen": 1,
                    "last_seen": 100,
                    "sessions": {},
                    "max_retry": 0,
                }
            }
        }
        self.evaluate({"running": [], "retrying": []}, ledger, now=161)
        self.assertEqual({}, ledger["issues"])

    def test_budget_incident_resume_starts_new_epoch_without_linear_state_bounce(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "private"
            incident = prefix / "incidents" / "implementation-budget.json"
            ledger = prefix / "state" / "symphony-ledger.json"
            incident.parent.mkdir(parents=True)
            ledger.parent.mkdir(parents=True)
            record = {
                "first_seen": 1,
                "last_seen": 2,
                "sessions": {"one": {"turns": 8, "tokens": 99}},
                "max_retry": 0,
            }
            incident.write_text(
                json.dumps(
                    {
                        "linear_state_changed": False,
                        "violations": [
                            {
                                "issue_identifier": "TTE-14",
                                "reason": "tokens_budget",
                            }
                        ],
                        "issue_metrics": {
                            "TTE-14": {
                                "ledger_epoch_sha256": _ledger_epoch_sha256(record)
                            }
                        },
                    }
                )
            )
            ledger.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "issues": {"TTE-14": record},
                    }
                )
            )
            config = load_config(CONFIG)
            environment = {"SANCTUM_AGENT_PREFIX": str(prefix)}
            first = resume_from_incident(config, incident, "TTE-14", environment)
            second = resume_from_incident(config, incident, "TTE-14", environment)
            self.assertEqual("applied", first["status"])
            self.assertEqual("already_applied", second["status"])
            self.assertFalse(first["linear_state_changed"])
            self.assertNotIn("TTE-14", json.loads(ledger.read_text())["issues"])

    def test_resume_rejects_stale_incident_or_nonbudget_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "private"
            incident = prefix / "incidents" / "blocked.json"
            ledger = prefix / "state" / "symphony-ledger.json"
            incident.parent.mkdir(parents=True)
            ledger.parent.mkdir(parents=True)
            record = {"first_seen": 1, "sessions": {}, "max_retry": 0}
            ledger.write_text(
                json.dumps({"schema_version": 1, "issues": {"TTE-14": record}})
            )
            incident.write_text(
                json.dumps(
                    {
                        "linear_state_changed": False,
                        "violations": [
                            {
                                "issue_identifier": "TTE-14",
                                "reason": "operator_action_required",
                            }
                        ],
                        "issue_metrics": {
                            "TTE-14": {
                                "ledger_epoch_sha256": _ledger_epoch_sha256(record)
                            }
                        },
                    }
                )
            )
            with self.assertRaisesRegex(ConfigError, "not a resumable"):
                resume_from_incident(
                    load_config(CONFIG),
                    incident,
                    "TTE-14",
                    {"SANCTUM_AGENT_PREFIX": str(prefix)},
                )
            payload = json.loads(incident.read_text())
            payload["violations"][0]["reason"] = "tokens_budget"
            payload["issue_metrics"]["TTE-14"]["ledger_epoch_sha256"] = "0" * 64
            incident.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ConfigError, "current ledger epoch"):
                resume_from_incident(
                    load_config(CONFIG),
                    incident,
                    "TTE-14",
                    {"SANCTUM_AGENT_PREFIX": str(prefix)},
                )

    def test_operator_blocker_is_terminal_without_retry_loop(self):
        snapshot = {
            "running": [],
            "retrying": [],
            "blocked": [
                {
                    "issue_identifier": "TTE-9",
                    "error": "deterministic Git metadata permission blocker",
                }
            ],
        }
        ledger: dict[str, object] = {"issues": {}}
        first = self.evaluate(snapshot, ledger)
        second = self.evaluate(snapshot, ledger, now=201)
        self.assertEqual(["operator_action_required"], [item.reason for item in first])
        self.assertEqual(["operator_action_required"], [item.reason for item in second])
        self.assertEqual(0, ledger["issues"]["TTE-9"]["max_retry"])

    def test_supervisor_kills_fake_service_and_writes_incident(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                state_port = probe.getsockname()[1]
            binary = root / "fake-symphony"
            binary.write_text("""#!/usr/bin/env python3
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
port = int(sys.argv[sys.argv.index('--port') + 1])
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({'running': [{'issue_identifier': 'SAN-SMOKE', 'session_id': 'one', 'turn_count': 99, 'tokens': {'total_tokens': 10}, 'started_at': '2026-09-19T00:00:00Z', 'last_event_at': '2099-01-01T00:00:00Z'}], 'retrying': []}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, format, *args):
        pass
HTTPServer(('127.0.0.1', port), Handler).serve_forever()
""")
            binary.chmod(0o700)
            raw = json.loads(CONFIG.read_text())
            raw["symphony"]["default_binary"] = str(binary)
            raw["symphony"]["state_port"] = state_port
            raw["symphony"]["poll_seconds"] = 1
            config_path = root / "source" / "config" / "agents.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(json.dumps(raw))
            config = load_config(config_path)
            prefix = root / "private-agents"
            workspace = root / "workspaces"
            github_config = root / "github-config"
            github_config.mkdir(mode=0o700)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            gh = bin_dir / "gh"
            gh.write_text("#!/bin/sh\nexit 0\n")
            gh.chmod(0o700)
            result = supervise(
                config,
                ROOT,
                {
                    "PATH": f"{bin_dir}:{os.environ['PATH']}",
                    "LINEAR_API_KEY": "synthetic-test-token",
                    "SYMPHONY_WORKSPACE_ROOT": str(workspace),
                    "SANCTUM_AGENT_PREFIX": str(prefix),
                    "SANCTUM_GIT_GH_CONFIG_DIR": str(github_config),
                },
            )
            self.assertEqual(75, result)
            incidents = list((prefix / "incidents").glob("*.json"))
            self.assertEqual(1, len(incidents))
            incident = json.loads(incidents[0].read_text())
            self.assertEqual("turns_budget", incident["violations"][0]["reason"])
            self.assertFalse(incident["linear_state_changed"])


class ReviewerTests(unittest.TestCase):
    def fixture(self) -> dict[str, object]:
        return {
            "verdict": "Approve",
            "summary": "The bounded documentation-only change satisfies both supplied acceptance criteria.",
            "blocking": [],
            "nonblocking": [],
        }

    def test_packet_requires_unmerged_issue_scoped_pr_in_human_review(self):
        packet = load_packet(REVIEW_FIXTURE)
        self.assertEqual("Human Review", packet["issue"]["state"])
        for key, value in (
            ("base_branch", "main"),
            ("head_branch", "feature/loose"),
            ("merged", True),
        ):
            changed = json.loads(REVIEW_FIXTURE.read_text())
            changed["pull_request"][key] = value
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "packet.json"
                path.write_text(json.dumps(changed))
                with self.subTest(key=key), self.assertRaises(LifecycleError):
                    load_packet(path)

    def test_review_findings_must_bind_to_known_evidence(self):
        packet = load_packet(REVIEW_FIXTURE)
        invalid = {
            "verdict": "Request changes",
            "summary": "A blocking finding references content outside the supplied review packet.",
            "blocking": [
                {
                    "title": "Unknown file reference",
                    "category": "failure",
                    "criterion_ids": ["AC-1"],
                    "file": "invented.py",
                    "line": 1,
                    "evidence": "The reviewer claimed evidence from a file that was not supplied in context.",
                    "recommendation": "Supply concrete packet evidence before treating this as a blocking issue.",
                }
            ],
            "nonblocking": [],
        }
        with self.assertRaisesRegex(MalformedModelOutput, "unknown file"):
            parse_review(invalid, packet)
        invalid["blocking"][0]["file"] = "docs/guides/operations.md"
        invalid["blocking"][0]["criterion_ids"] = ["AC-404"]
        with self.assertRaisesRegex(MalformedModelOutput, "criteria"):
            parse_review(invalid, packet)

    def test_shadow_review_is_independent_read_only_and_has_no_posts(self):
        config = load_config(CONFIG)
        before = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                "os.environ", {"SANCTUM_AGENT_PREFIX": str(Path(directory) / "agents")}
            ),
        ):
            result = run_reviewer(
                config,
                ROOT,
                REVIEW_FIXTURE,
                RunMode.SHADOW,
                review_fixture=self.fixture(),
            )
        self.assertEqual("Approve", result["review"]["verdict"])
        self.assertEqual(0, result["github_writes"])
        self.assertEqual(0, result["linear_writes"])
        after = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(before, after)


class LinearPayloadTests(unittest.TestCase):
    @staticmethod
    def metadata_client(
        *, missing_state: str | None = None, paginate_states: bool = False
    ):
        fixture = json.loads(LINEAR_METADATA_FIXTURE.read_text())

        class FakeClient:
            def __init__(self):
                self.calls = []

            def query(self, query, variables=None):
                self.calls.append((query, variables or {}))
                if "SanctumProjectMetadata" in query:
                    return {
                        "project": {
                            "id": "project-live",
                            "name": "Sanctum V1.3",
                            "slugId": "aafdb6e2bb76",
                            "url": "https://linear.app/team/project/sanctum-v13-aafdb6e2bb76",
                            "teams": {
                                "nodes": [{"id": "team-live", "name": "Team"}],
                                "pageInfo": {"hasNextPage": False},
                            },
                        }
                    }
                if "SanctumTeamMetadata" in query:
                    states = [
                        {"id": identifier, "name": name}
                        for name, identifier in fixture["states"].items()
                        if name != missing_state
                    ]
                    labels = []
                    for name, identifier in fixture["labels"].items():
                        parent = (
                            {"id": "source-group", "name": "source"}
                            if name in {"Repo Steward", "Product Scout"}
                            else None
                        )
                        labels.append(
                            {"id": identifier, "name": name, "parent": parent}
                        )
                    templates = [
                        {"id": identifier, "name": name, "type": "issue"}
                        for name, identifier in fixture["templates"].items()
                    ]
                    return {
                        "team": {
                            "id": "team-live",
                            "name": "Team",
                            "states": {
                                "nodes": states,
                                "pageInfo": {"hasNextPage": paginate_states},
                            },
                            "labels": {
                                "nodes": labels,
                                "pageInfo": {"hasNextPage": False},
                            },
                            "templates": {
                                "nodes": templates,
                                "pageInfo": {"hasNextPage": False},
                            },
                        }
                    }
                raise AssertionError("unexpected query")

        return FakeClient()

    def test_metadata_capture_is_read_only_exact_and_private(self):
        client = self.metadata_client()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "linear-metadata.json"
            metadata = capture_qualified_metadata(
                client, "sanctum-v13-aafdb6e2bb76", path
            )
            snapshot = json.loads(path.read_text())
            fixture = json.loads(LINEAR_METADATA_FIXTURE.read_text())
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            self.assertEqual(0o700, stat.S_IMODE(path.parent.stat().st_mode))
            self.assertEqual("project-live", snapshot["project"]["id"])
            self.assertEqual("team-live", snapshot["project"]["team_id"])
            self.assertEqual(fixture["states"], snapshot["states"])
            self.assertEqual(fixture["labels"], snapshot["labels"])
            self.assertEqual(fixture["templates"], snapshot["templates"])
            self.assertEqual("project-live", metadata.project_id)
        self.assertEqual(2, len(client.calls))
        self.assertTrue(
            all("mutation" not in query.lower() for query, _ in client.calls)
        )

    def test_metadata_capture_stops_before_write_on_contract_mismatch(self):
        client = self.metadata_client(missing_state="Human Review")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "linear-metadata.json"
            with self.assertRaisesRegex(
                LinearMetadataError, "missing required names: Human Review"
            ):
                capture_qualified_metadata(client, "sanctum-v13-aafdb6e2bb76", path)
            self.assertFalse(path.exists())

    def test_metadata_capture_stops_before_write_on_pagination(self):
        client = self.metadata_client(paginate_states=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "linear-metadata.json"
            with self.assertRaisesRegex(
                LinearMetadataError, "states metadata requires pagination"
            ):
                capture_qualified_metadata(client, "sanctum-v13-aafdb6e2bb76", path)
            self.assertFalse(path.exists())

    def test_engineering_finding_targets_triage_without_execution_authority(self):
        metadata = load_qualified_metadata(
            LINEAR_METADATA_FIXTURE, "sanctum-v13-aafdb6e2bb76"
        )
        finding = Finding(
            "Bound continuation runtime",
            "Continuation retries can outlive per-turn limits and require an independent hard deadline.",
            "high",
            "Investigate",
            ("e-1",),
            ("tech-debt", "reliability"),
            "Repo Steward",
        )
        proposal = engineering_finding_proposal(
            metadata, finding, {"e-1": "Observed workflow gap."}
        )
        issue_input = proposal.variables["input"]
        self.assertEqual("state-triage", issue_input["stateId"])
        self.assertIn("label-source-repo", issue_input["labelIds"])
        self.assertNotIn("label-symphony", issue_input["labelIds"])
        self.assertIn(proposal.fingerprint, issue_input["description"])

    def test_product_discovery_uses_qualified_sources_and_triage(self):
        metadata = load_qualified_metadata(
            LINEAR_METADATA_FIXTURE, "sanctum-v13-aafdb6e2bb76"
        )
        source = ResearchSource(
            "release",
            "https://github.com/example/project/releases",
            "Project release",
            "2026-09-19",
            "release_notes",
            "The release adds bounded execution leases.",
        )
        finding = ProductDiscovery(
            "Compare bounded execution leases",
            "The project provides a concrete bounded worker lease implementation.",
            "Sanctum can compare cleanup receipts without changing owner authorization.",
            "Investigate",
            ("release",),
            ("product-discovery", "research"),
        )
        proposal = product_discovery_proposal(metadata, finding, {"release": source})
        issue_input = proposal.variables["input"]
        self.assertEqual("state-triage", issue_input["stateId"])
        self.assertIn("label-source-product", issue_input["labelIds"])
        self.assertNotIn("label-symphony", issue_input["labelIds"])

    def test_metadata_and_triage_transitions_fail_closed(self):
        with self.assertRaisesRegex(LinearMetadataError, "slug"):
            load_qualified_metadata(LINEAR_METADATA_FIXTURE, "wrong-project")
        metadata = load_qualified_metadata(
            LINEAR_METADATA_FIXTURE, "sanctum-v13-aafdb6e2bb76"
        )
        self.assertEqual(
            {"id": "issue-a", "input": {"stateId": "state-backlog"}},
            triage_update_variables(metadata, "issue-a", "Backlog"),
        )
        with self.assertRaises(AuthorityError):
            triage_update_variables(metadata, "issue-a", "Ready for Agent")

    def test_writer_searches_duplicates_caps_creation_and_links_triage(self):
        metadata = load_qualified_metadata(
            LINEAR_METADATA_FIXTURE, "sanctum-v13-aafdb6e2bb76"
        )
        calls: list[tuple[str, dict[str, object]]] = []

        class FakeClient:
            def query(self, query, variables=None):
                calls.append((query, variables or {}))
                if "DuplicateCandidates" in query:
                    return {"project": {"issues": {"nodes": []}}}
                if "IssueCreate" in query:
                    return {
                        "issueCreate": {
                            "success": True,
                            "issue": {
                                "id": "created-1",
                                "identifier": "SAN-301",
                                "url": "https://linear.app/x",
                            },
                        }
                    }
                if "IssueUpdate" in query:
                    return {
                        "issueUpdate": {"success": True, "issue": {"id": "issue-a"}}
                    }
                if "IssueRelationCreate" in query:
                    return {
                        "issueRelationCreate": {
                            "success": True,
                            "issueRelation": {"id": "relation-1"},
                        }
                    }
                raise AssertionError("unexpected query")

        finding = Finding(
            "Bound continuation runtime",
            "Continuation retries require an independent total runtime deadline.",
            "high",
            "Investigate",
            ("e-1",),
            ("reliability",),
            "Repo Steward",
        )
        proposal = engineering_finding_proposal(
            metadata, finding, {"e-1": "Observed gap."}
        )
        writer = LinearWriter(FakeClient(), metadata)
        outcomes = writer.create_proposals([proposal, proposal], max_created=1)
        self.assertEqual(
            ["created", "duplicate"], [item["status"] for item in outcomes]
        )
        linked = writer.apply_triage("issue-a", "Canceled", "issue-c")
        self.assertEqual(
            ["updated", "linked_duplicate"], [item["status"] for item in linked]
        )
        self.assertEqual(1, sum("IssueCreate" in query for query, _ in calls))


class SchedulePlanTests(unittest.TestCase):
    def test_schedule_plan_activates_only_qualified_management_cadences(self):
        plan = load_schedule_plan(SCHEDULES)
        schedules = plan["schedules"]
        repo = [item for item in schedules if item["role"] == "repo_steward"]
        self.assertEqual(2, len(repo))
        self.assertTrue(all(item["enabled"] for item in repo))
        self.assertTrue(all(not item["blocked_by"] for item in repo))
        self.assertTrue(all("live" in item["command"] for item in repo))
        product = next(item for item in schedules if item["role"] == "product_scout")
        self.assertEqual(["Monday", "Wednesday", "Friday"], product["days"])
        self.assertIn("product-scout", product["command"])
        self.assertTrue(product["enabled"])
        self.assertFalse(product["blocked_by"])
        self.assertIn("live", product["command"])
        triage = next(item for item in schedules if item["role"] == "triage")
        self.assertTrue(triage["enabled"])
        self.assertFalse(triage["blocked_by"])
        self.assertIn("live", triage["command"])
        self.assertNotIn("--snapshot", triage["command"])

    def test_blocked_schedule_cannot_be_enabled(self):
        raw = json.loads(SCHEDULES.read_text())
        triage = next(item for item in raw["schedules"] if item["role"] == "triage")
        triage["blocked_by"] = ["synthetic blocker"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedules.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ScheduleError, "blocked"):
                load_schedule_plan(path)


class SymphonyRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.prefix = (Path(self.temporary.name) / "private").resolve()
        (self.prefix / "incidents").mkdir(parents=True)
        (self.prefix / "state").mkdir()
        self.config = load_config(CONFIG)
        self.issue = "SAN-7"
        self.record = {
            "first_seen": 1,
            "last_seen": 2,
            "runtimes": {"test": {"turns": 40, "tokens": 8000001}},
            "max_retry": 0,
        }
        self.incident = self.prefix / "incidents" / "implementation-test.json"
        self._write_incident()
        (self.prefix / "state" / "symphony-ledger.json").write_text(
            json.dumps({"schema_version": 1, "issues": {self.issue: self.record}})
        )

    def _write_incident(self, reason="tokens_budget", turns=40, observed=8000001):
        self.incident.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "linear_state_changed": False,
                    "violations": [
                        {
                            "issue_identifier": self.issue,
                            "reason": reason,
                            "observed": observed,
                            "limit": 8000000,
                        }
                    ],
                    "issue_metrics": {
                        self.issue: {
                            "turn_count": turns,
                            "tokens": 8000001,
                            "retry_count": 0,
                            "ledger_epoch_sha256": _ledger_epoch_sha256(self.record),
                        }
                    },
                }
            )
        )

    def test_one_time_extension_is_bound_to_existing_epoch(self):
        self.assertEqual(
            (self.issue, "eligible"), _candidate(self.prefix, self.incident)
        )
        _grant(self.config, self.prefix, self.incident, self.issue)
        self.assertEqual(6, load_continuations(self.prefix)[self.issue]["max_turns"])
        self.assertEqual(
            (self.issue, "already_continued"), _candidate(self.prefix, self.incident)
        )
        with self.assertRaisesRegex(ConfigError, "continuation gate closed"):
            _grant(self.config, self.prefix, self.incident, self.issue)

    def test_deterministic_blockers_never_consult_advisor(self):
        self._write_incident(reason="validation_environment_preflight")
        self.assertEqual("ineligible_stop", _candidate(self.prefix, self.incident)[1])
        self._write_incident(turns=0)
        self.assertEqual("no_turn_progress", _candidate(self.prefix, self.incident)[1])
        self._write_incident(observed=8300000)
        self.assertEqual(
            "extension_exhausted", _candidate(self.prefix, self.incident)[1]
        )
        self._write_incident()
        operations = (
            self.prefix / "state" / "git-control-plane" / "operations" / self.issue
        )
        operations.mkdir(parents=True)
        (operations / "push-test.json").write_text(json.dumps({"state": "pending"}))
        self.assertEqual(
            "uncertain_git_state", _candidate(self.prefix, self.incident)[1]
        )

    def test_extension_is_cumulative_and_a_second_stop_remains_enforced(self):
        ledger = {
            "issues": {
                self.issue: {
                    "first_seen": 1,
                    "last_seen": 1,
                    "runtimes": {},
                    "max_retry": 0,
                }
            }
        }
        snapshot = {
            "running": [
                {
                    "issue_identifier": self.issue,
                    "turn_count": 43,
                    "tokens": {"total_tokens": 8100000},
                }
            ],
            "retrying": [],
            "blocked": [],
        }
        base = evaluate_snapshot(
            snapshot,
            ledger,
            now=2,
            wall_clock_seconds=100,
            max_turns=40,
            max_tokens=8000000,
            max_retries=3,
        )
        self.assertTrue(base)
        continued = evaluate_snapshot(
            snapshot,
            ledger,
            now=2,
            wall_clock_seconds=100,
            max_turns=40,
            max_tokens=8000000,
            max_retries=3,
            continuations={
                self.issue: {
                    "wall_clock_seconds": 1800,
                    "max_turns": 6,
                    "max_tokens": 250000,
                }
            },
        )
        self.assertEqual([], continued)
        snapshot["running"][0]["turn_count"] = 47
        stopped = evaluate_snapshot(
            snapshot,
            ledger,
            now=2,
            wall_clock_seconds=100,
            max_turns=40,
            max_tokens=8000000,
            max_retries=3,
            continuations={
                self.issue: {
                    "wall_clock_seconds": 1800,
                    "max_turns": 6,
                    "max_tokens": 250000,
                }
            },
        )
        self.assertEqual("turns_budget", stopped[0].reason)

    def test_wrapper_restarts_at_most_once(self):
        with (
            patch.dict(
                os.environ, {self.config.runtime["prefix_env"]: str(self.prefix)}
            ),
            patch("sanctum_agents.symphony_recovery.supervise") as supervisor,
            patch(
                "sanctum_agents.symphony_recovery._workspace_progress",
                return_value={"changed_paths": 2, "commits_ahead": 0},
            ),
            patch(
                "sanctum_agents.symphony_recovery._advise", return_value="CONTINUE_ONCE"
            ),
            patch("sanctum_agents.symphony_recovery._report") as report,
        ):

            def stopped(_config, _repository, *, incident_sink, **_kwargs):
                incident_sink.append(self.incident)
                return 75

            supervisor.side_effect = stopped
            self.assertEqual(75, run_with_recovery(self.config, ROOT))
            self.assertEqual(2, supervisor.call_count)
            self.assertEqual("continuation_stopped", report.call_args.args[-1])

    def test_gmail_delivery_uses_starttls_and_keychain(self):
        binding = self.prefix / "config" / "symphony-notifications.json"
        binding.parent.mkdir()
        binding.write_text(
            json.dumps(
                {"sender": "owner@gmail.com", "recipient": "owner+alert@gmail.com"}
            )
        )
        binding.chmod(0o600)
        with (
            patch("sanctum_agents.symphony_recovery.subprocess.run") as keychain,
            patch("sanctum_agents.symphony_recovery.smtplib.SMTP") as smtp,
        ):
            keychain.return_value.returncode = 0
            keychain.return_value.stdout = "synthetic-app-password\n"
            self.assertEqual(
                "owner+alert@gmail.com",
                _notify(self.prefix, self.incident, self.issue, "needs_owner"),
            )
            keychain.assert_called_once()
            self.assertEqual("/usr/bin/security", keychain.call_args.args[0][0])
            client = smtp.return_value.__enter__.return_value
            client.starttls.assert_called_once()
            client.login.assert_called_once_with(
                "owner@gmail.com", "synthetic-app-password"
            )
            client.send_message.assert_called_once()

    def test_email_attempt_is_not_repeated_after_failure(self):
        with patch(
            "sanctum_agents.symphony_recovery._notify",
            side_effect=ConfigError("missing"),
        ) as notify:
            _report(self.prefix, self.incident, self.issue, "blocked")
            _report(self.prefix, self.incident, self.issue, "blocked")
            self.assertEqual(1, notify.call_count)
            receipt = json.loads(
                (
                    self.prefix
                    / "state"
                    / "symphony-recovery"
                    / "implementation-test.json"
                ).read_text()
            )
            self.assertEqual("failed", receipt["email"])


if __name__ == "__main__":
    unittest.main()
