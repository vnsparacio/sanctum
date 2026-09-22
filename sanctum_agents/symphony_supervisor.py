"""Sanctum-owned hard governor around the external Symphony service."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib import error, request

from .config import AgentConfig, ConfigError
from .runtime import (
    ExclusiveRoleLock,
    JsonlRunLog,
    RunMode,
    ensure_private_prefix,
    new_run_id,
)


@dataclass(frozen=True)
class SymphonyViolation:
    issue_identifier: str
    reason: str
    observed: float
    limit: float
    termination_class: str


class TerminationClass(StrEnum):
    MODEL_REASONING = "MODEL_REASONING"
    ENVIRONMENT = "ENVIRONMENT"
    SANDBOX = "SANDBOX"
    VALIDATION = "VALIDATION"
    GIT_CONTROL_PLANE = "GIT_CONTROL_PLANE"
    NETWORK_PROVIDER = "NETWORK_PROVIDER"
    TOKEN_BUDGET = "TOKEN_BUDGET"
    TIME_BUDGET = "TIME_BUDGET"
    OWNER_ACTION_REQUIRED = "OWNER_ACTION_REQUIRED"
    UNKNOWN = "UNKNOWN"


def classify_termination(reason: str, detail: str | None = None) -> TerminationClass:
    normalized = f"{reason} {detail or ''}".lower()
    if reason == "tokens_budget":
        return TerminationClass.TOKEN_BUDGET
    if reason in {
        "wall_clock_budget",
        "turns_budget",
        "stall_budget",
        "output_budget",
    }:
        return TerminationClass.TIME_BUDGET
    if any(
        value in normalized
        for value in ("/bin/ps", "operation_not_permitted", "sandbox")
    ):
        return TerminationClass.SANDBOX
    if any(
        value in normalized
        for value in ("git_", "github_", "commit", "push", "pull request")
    ):
        return TerminationClass.GIT_CONTROL_PLANE
    if any(
        value in normalized
        for value in ("network", "provider", "rate limit", "connection")
    ):
        return TerminationClass.NETWORK_PROVIDER
    if any(
        value in normalized
        for value in ("validation", "test failed", "build failed", "audit failed")
    ):
        return TerminationClass.VALIDATION
    if any(
        value in normalized
        for value in ("context", "reasoning", "malformed model", "model output")
    ):
        return TerminationClass.MODEL_REASONING
    if reason == "operator_action_required":
        return TerminationClass.OWNER_ACTION_REQUIRED
    if reason == "state_api_stall":
        return TerminationClass.ENVIRONMENT
    if reason == "retries_budget":
        return TerminationClass.TIME_BUDGET
    return TerminationClass.UNKNOWN


def _parse_time(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def validation_environment_violations(
    validation_state: Path, snapshot: dict[str, Any], *, launched_at: float
) -> list[SymphonyViolation]:
    """Stop a run after its own host validation preflight fails."""
    violations: list[SymphonyViolation] = []
    active = snapshot.get("running", []) + snapshot.get("retrying", [])
    for entry in active:
        identifier = entry.get("issue_identifier")
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[A-Z][A-Z0-9]*-[1-9][0-9]*", identifier
        ):
            continue
        receipt_dir = validation_state / "receipts" / identifier
        for path in receipt_dir.glob("*.json"):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                receipt = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if (
                isinstance(receipt, dict)
                and isinstance(receipt.get("events"), list)
                and receipt.get("issue_id") == identifier
                and receipt.get("state") == "completed"
                and (_parse_time(receipt.get("requested_at")) or 0) >= launched_at
                and "environment_preflight_failed" in receipt.get("events", [])
            ):
                violations.append(
                    SymphonyViolation(
                        identifier,
                        "validation_environment_preflight",
                        1.0,
                        0.0,
                        TerminationClass.SANDBOX.value,
                    )
                )
                break
    return violations


def evaluate_snapshot(
    snapshot: dict[str, Any],
    ledger: dict[str, Any],
    *,
    runtime_id: str = "runtime",
    now: float,
    wall_clock_seconds: int,
    max_turns: int,
    max_tokens: int,
    max_retries: int,
    max_concurrency: int = 1,
    continuations: dict[str, dict[str, int]] | None = None,
) -> list[SymphonyViolation]:
    if not isinstance(snapshot, dict):
        raise ValueError("Symphony snapshot must be an object")
    running = snapshot.get("running", [])
    retrying = snapshot.get("retrying", [])
    blocked = snapshot.get("blocked", [])
    if (
        not isinstance(running, list)
        or not isinstance(retrying, list)
        or not isinstance(blocked, list)
    ):
        raise ValueError("Symphony snapshot collections are malformed")
    issues = ledger.setdefault("issues", {})
    violations: list[SymphonyViolation] = []
    if len(running) > max_concurrency:
        violations.append(
            SymphonyViolation(
                "service",
                "concurrency_budget",
                float(len(running)),
                float(max_concurrency),
                TerminationClass.ENVIRONMENT.value,
            )
        )
    active_identifiers: set[str] = set()
    for entry in running:
        if not isinstance(entry, dict) or not isinstance(
            entry.get("issue_identifier"), str
        ):
            raise ValueError("Symphony running entry is malformed")
        identifier = entry["issue_identifier"]
        active_identifiers.add(identifier)
        record = issues.setdefault(
            identifier,
            {"first_seen": now, "last_seen": now, "runtimes": {}, "max_retry": 0},
        )
        record["last_seen"] = now
        runtimes = _runtime_counters(record)
        runtime_record = runtimes.setdefault(
            runtime_id,
            {"turns": 0, "tokens": 0, "input_tokens": 0, "output_tokens": 0},
        )
        elapsed = max(0, now - float(record["first_seen"]))
        turns = entry.get("turn_count", 0)
        token_counters = entry.get("tokens", {})
        tokens = (
            token_counters.get("total_tokens", 0)
            if isinstance(token_counters, dict)
            else 0
        )
        input_tokens = (
            token_counters.get("input_tokens", 0)
            if isinstance(token_counters, dict)
            else 0
        )
        output_tokens = (
            token_counters.get("output_tokens", 0)
            if isinstance(token_counters, dict)
            else 0
        )
        counters = (turns, tokens, input_tokens, output_tokens)
        if any(type(value) is not int or value < 0 for value in counters):
            raise ValueError("Symphony running counters are malformed")
        runtime_record["turns"] = max(runtime_record.get("turns", 0), turns)
        runtime_record["tokens"] = max(runtime_record.get("tokens", 0), tokens)
        runtime_record["input_tokens"] = max(
            runtime_record.get("input_tokens", 0), input_tokens
        )
        runtime_record["output_tokens"] = max(
            runtime_record.get("output_tokens", 0), output_tokens
        )
        totals = _ledger_totals(record, now)
        total_turns = totals["turn_count"]
        total_tokens = totals["tokens"]
        extension = (continuations or {}).get(identifier, {})
        checks = [
            (
                "wall_clock_budget",
                elapsed,
                wall_clock_seconds + extension.get("wall_clock_seconds", 0),
            ),
            ("turns_budget", total_turns, max_turns + extension.get("max_turns", 0)),
            (
                "tokens_budget",
                total_tokens,
                max_tokens + extension.get("max_tokens", 0),
            ),
        ]
        for reason, observed, limit in checks:
            if type(observed) in {int, float} and observed > limit:
                violations.append(
                    SymphonyViolation(
                        identifier,
                        reason,
                        float(observed),
                        float(limit),
                        classify_termination(reason).value,
                    )
                )
    for entry in retrying:
        if not isinstance(entry, dict) or not isinstance(
            entry.get("issue_identifier"), str
        ):
            raise ValueError("Symphony retry entry is malformed")
        identifier = entry["issue_identifier"]
        active_identifiers.add(identifier)
        attempt = entry.get("attempt", 0)
        if type(attempt) is not int or attempt < 0:
            raise ValueError("Symphony retry attempt is malformed")
        record = issues.setdefault(
            identifier,
            {"first_seen": now, "last_seen": now, "runtimes": {}, "max_retry": 0},
        )
        record["last_seen"] = now
        record["max_retry"] = max(record.get("max_retry", 0), attempt)
        elapsed = max(0, now - float(record["first_seen"]))
        extension = (continuations or {}).get(identifier, {})
        wall_limit = wall_clock_seconds + extension.get("wall_clock_seconds", 0)
        if elapsed > wall_limit:
            violations.append(
                SymphonyViolation(
                    identifier,
                    "wall_clock_budget",
                    elapsed,
                    float(wall_limit),
                    TerminationClass.TIME_BUDGET.value,
                )
            )
        if attempt > max_retries:
            violations.append(
                SymphonyViolation(
                    identifier,
                    "retries_budget",
                    float(attempt),
                    float(max_retries),
                    classify_termination("retries_budget", entry.get("error")).value,
                )
            )
    for entry in blocked:
        if not isinstance(entry, dict):
            raise ValueError("Symphony blocked entry is malformed")
        identifier = entry.get("issue_identifier") or entry.get("identifier")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("Symphony blocked entry is malformed")
        active_identifiers.add(identifier)
        record = issues.setdefault(
            identifier,
            {"first_seen": now, "last_seen": now, "runtimes": {}, "max_retry": 0},
        )
        record["last_seen"] = now
        violations.append(
            SymphonyViolation(
                identifier,
                "operator_action_required",
                1.0,
                0.0,
                classify_termination(
                    "operator_action_required", entry.get("error")
                ).value,
            )
        )
    for identifier, record in list(issues.items()):
        if (
            identifier not in active_identifiers
            and now - float(record.get("last_seen", now)) > 60
        ):
            del issues[identifier]
    return violations


def _save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def load_continuations(prefix: Path) -> dict[str, dict[str, int]]:
    """Read host-issued, one-time extensions; malformed private state fails closed."""
    root = prefix / "state" / "symphony-continuations"
    if not root.exists():
        return {}
    if root.is_symlink() or not root.is_dir():
        raise ConfigError("Symphony continuation state is unsafe")
    result: dict[str, dict[str, int]] = {}
    for path in root.iterdir():
        identifier = path.stem
        if (
            path.suffix != ".json"
            or not re.fullmatch(r"[A-Z][A-Z0-9]*-[1-9][0-9]*", identifier)
            or path.is_symlink()
            or not path.is_file()
        ):
            raise ConfigError("Symphony continuation entry is unsafe")
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError("Symphony continuation entry is unreadable") from exc
        if (
            not isinstance(value, dict)
            or value.get("issue_identifier") != identifier
            or value.get("schema_version") != 1
            or not isinstance(value.get("incident"), str)
        ):
            raise ConfigError("Symphony continuation entry is malformed")
        limits = value.get("limits")
        if (
            not isinstance(limits, dict)
            or limits.get("wall_clock_seconds") != 1800
            or limits.get("max_turns") != 6
            or limits.get("max_tokens") != 250000
        ):
            raise ConfigError("Symphony continuation limits are unreviewed")
        result[identifier] = limits
    return result


def _runtime_counters(record: dict[str, Any]) -> dict[str, Any]:
    runtimes = record.setdefault("runtimes", {})
    if not isinstance(runtimes, dict):
        raise ValueError("Symphony supervisor runtime ledger is malformed")
    sessions = record.pop("sessions", None)
    if sessions is None:
        return runtimes
    if not isinstance(sessions, dict):
        raise ValueError("Symphony supervisor legacy session ledger is malformed")
    legacy = {"turns": 0, "tokens": 0, "input_tokens": 0, "output_tokens": 0}
    for session in sessions.values():
        if not isinstance(session, dict):
            raise ValueError("Symphony supervisor legacy session ledger is malformed")
        for name in legacy:
            value = session.get(name, 0)
            if type(value) is not int or value < 0:
                raise ValueError(
                    "Symphony supervisor legacy session counters are malformed"
                )
            legacy[name] = max(legacy[name], value)
    if sessions:
        runtimes.setdefault("legacy", legacy)
    return runtimes


def _ledger_totals(record: dict[str, Any], now: float) -> dict[str, float]:
    runtimes = record.get("runtimes")
    if runtimes is None:
        sessions = record.get("sessions", {})
        if not isinstance(sessions, dict):
            runtimes = {}
        else:
            legacy = {
                "turns": max(
                    (item.get("turns", 0) for item in sessions.values()), default=0
                ),
                "tokens": max(
                    (item.get("tokens", 0) for item in sessions.values()), default=0
                ),
                "input_tokens": max(
                    (item.get("input_tokens", 0) for item in sessions.values()),
                    default=0,
                ),
                "output_tokens": max(
                    (item.get("output_tokens", 0) for item in sessions.values()),
                    default=0,
                ),
            }
            runtimes = {"legacy": legacy} if sessions else {}
    if not isinstance(runtimes, dict):
        return {
            "elapsed_ms": 0.0,
            "turn_count": 0.0,
            "tokens": 0.0,
            "input_tokens": 0.0,
            "output_tokens": 0.0,
            "retry_count": 0.0,
        }
    return {
        "elapsed_ms": max(0.0, now - float(record.get("first_seen", now))) * 1000,
        "turn_count": float(sum(item.get("turns", 0) for item in runtimes.values())),
        "tokens": float(sum(item.get("tokens", 0) for item in runtimes.values())),
        "input_tokens": float(
            sum(item.get("input_tokens", 0) for item in runtimes.values())
        ),
        "output_tokens": float(
            sum(item.get("output_tokens", 0) for item in runtimes.values())
        ),
        "retry_count": float(record.get("max_retry", 0)),
    }


def _ledger_epoch_sha256(record: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _resolve_binary(config: AgentConfig, environ: dict[str, str]) -> str:
    raw = (
        environ.get(config.symphony["binary_env"]) or config.symphony["default_binary"]
    )
    binary = shutil.which(raw) if not Path(raw).is_absolute() else raw
    if not binary or not Path(binary).is_file() or not os.access(binary, os.X_OK):
        raise ConfigError(
            f"Symphony binary unavailable; set {config.symphony['binary_env']}"
        )
    return str(Path(binary).resolve())


def _verified_host_assets(repository: Path) -> tuple[str, str, str]:
    manifest_path = repository / "SOURCE-MANIFEST.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("source manifest unavailable for Git broker") from exc
    relative_paths = (
        "scripts/sanctum_git_broker.py",
        "sanctum_agents/git_control_plane.py",
        "scripts/sanctum_validation_runner.py",
        "sanctum_agents/validation.py",
    )
    for relative in relative_paths:
        path = repository / relative
        expected = manifest.get(relative)
        if (
            not isinstance(expected, str)
            or path.is_symlink()
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ConfigError(f"reviewed Git broker source drift: {relative}")
    python = repository.resolve() / ".venv" / "bin" / "python"
    script = (repository / relative_paths[0]).resolve()
    validation_script = (repository / relative_paths[2]).resolve()
    safe_path = re.compile(r"^[A-Za-z0-9_./-]+$")
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ConfigError("reviewed Git broker Python is unavailable")
    if (
        not safe_path.fullmatch(str(python))
        or not safe_path.fullmatch(str(script))
        or not safe_path.fullmatch(str(validation_script))
    ):
        raise ConfigError("host executable paths contain unsupported characters")
    return str(python), str(script), str(validation_script)


def _launch_prefix(binary: str) -> list[str]:
    project = Path(binary).parent.parent
    mise_config = project / "mise.toml"
    if mise_config.is_file():
        mise = shutil.which("mise")
        if not mise:
            raise ConfigError(
                "mise is required for the configured Symphony development binary"
            )
        return [mise, "-C", str(project), "exec", "--", binary]
    return [binary]


def _sanitized_supervisor_environment(
    values: dict[str, str], binary_env: str
) -> dict[str, str]:
    allowed = {
        "CODEX_HOME",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LINEAR_API_KEY",
        "LOGNAME",
        "MISE_CACHE_DIR",
        "MISE_CONFIG_DIR",
        "MISE_DATA_DIR",
        "PATH",
        "SANCTUM_AGENT_PREFIX",
        "SHELL",
        "SSH_AUTH_SOCK",
        "SYMPHONY_WORKSPACE_ROOT",
        "TMPDIR",
        "USER",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        binary_env,
    }
    return {key: value for key, value in values.items() if key in allowed}


def _worker_settings(config: AgentConfig, worker_class: str) -> tuple[str, str]:
    if worker_class == "standard":
        return "implementation", config.symphony["workflow"]
    if worker_class == "deep":
        return "implementation_deep", config.symphony["deep_workflow"]
    raise ConfigError("worker class must be standard or deep")


def preflight(
    config: AgentConfig,
    repository: Path,
    environ: dict[str, str] | None = None,
    *,
    worker_class: str = "standard",
) -> dict[str, Any]:
    values = os.environ if environ is None else environ
    role_name, workflow_name = _worker_settings(config, worker_class)
    binary = _resolve_binary(config, values)
    workflow = repository / workflow_name
    if not workflow.is_file():
        raise ConfigError("Symphony workflow is unavailable")
    workflow_text = workflow.read_text()
    route = config.project["worker_routing"][f"{worker_class}_label"]
    model = config.model_for(role_name)
    required_fragments = (
        f"    - {route}\n",
        f'model="{model.model}"',
        f'model_reasoning_effort="{model.reasoning}"',
        f"max_concurrent_agents: {config.symphony['max_concurrency']}",
    )
    if any(fragment not in workflow_text for fragment in required_fragments):
        raise ConfigError(
            "worker workflow does not match reviewed routing configuration"
        )
    if not values.get("LINEAR_API_KEY"):
        raise ConfigError("LINEAR_API_KEY is required by Symphony")
    raw_root = values.get("SYMPHONY_WORKSPACE_ROOT")
    if not raw_root or not Path(raw_root).expanduser().is_absolute():
        raise ConfigError("SYMPHONY_WORKSPACE_ROOT must be an absolute external path")
    workspace_root = Path(raw_root).expanduser().resolve(strict=False)
    source = repository.resolve()
    if workspace_root == source or workspace_root.is_relative_to(source):
        raise ConfigError("Symphony workspace root must remain outside source")
    broker_python, broker_script, validation_script = _verified_host_assets(repository)
    credential_helper = shutil.which("gh", path=values.get("PATH"))
    if not credential_helper:
        raise ConfigError("GitHub CLI credential helper is unavailable")
    credential_helper_path = Path(credential_helper).resolve()
    safe_path = re.compile(r"^[A-Za-z0-9_./-]+$")
    if (
        credential_helper_path.name != "gh"
        or not credential_helper_path.is_file()
        or credential_helper_path.is_symlink()
        or not os.access(credential_helper_path, os.X_OK)
        or not safe_path.fullmatch(str(credential_helper_path))
        or credential_helper_path.stat().st_uid not in {0, os.getuid()}
        or credential_helper_path.stat().st_mode & 0o022
    ):
        raise ConfigError("GitHub CLI credential helper is not a reviewed executable")
    raw_github_config = values.get("SANCTUM_GIT_GH_CONFIG_DIR")
    if not raw_github_config:
        raise ConfigError("SANCTUM_GIT_GH_CONFIG_DIR is required")
    github_config_dir = Path(raw_github_config).expanduser()
    if (
        not github_config_dir.is_absolute()
        or github_config_dir.is_symlink()
        or not github_config_dir.is_dir()
    ):
        raise ConfigError(
            "SANCTUM_GIT_GH_CONFIG_DIR must be an existing private directory"
        )
    github_config_dir = github_config_dir.resolve()
    if (
        github_config_dir.is_relative_to(source)
        or github_config_dir.is_relative_to(workspace_root)
        or github_config_dir.stat().st_mode & 0o077
    ):
        raise ConfigError(
            "GitHub CLI authentication must remain in a private external directory"
        )
    auth_environment = {
        "GH_CONFIG_DIR": str(github_config_dir),
        "GH_PROMPT_DISABLED": "1",
        "HOME": values.get("HOME", "/var/empty"),
        "NO_COLOR": "1",
        "PATH": values.get("PATH", "/usr/bin:/bin"),
    }
    try:
        authenticated = subprocess.run(
            [str(credential_helper_path), "auth", "status", "--hostname", "github.com"],
            env=auth_environment,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ConfigError("private GitHub CLI authentication check timed out") from exc
    if authenticated.returncode:
        raise ConfigError("private GitHub CLI authentication is unavailable")
    return {
        "binary": binary,
        "launch_prefix": _launch_prefix(binary),
        "workflow": str(workflow),
        "workspace_root": str(workspace_root),
        "git_broker_python": broker_python,
        "git_broker_script": broker_script,
        "validation_runner_script": validation_script,
        "git_credential_helper": str(credential_helper_path),
        "git_github_config_dir": str(github_config_dir),
        "worker_class": worker_class,
        "role_name": role_name,
        "model": model.model,
        "reasoning_effort": model.reasoning,
        "wall_clock_timeout_seconds": config.roles[role_name].wall_clock_seconds,
    }


def resume_from_incident(
    config: AgentConfig,
    incident: Path,
    issue_identifier: str,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    values = os.environ if environ is None else environ
    prefix = config.runtime_prefix(values)
    ensure_private_prefix(prefix)
    lock = ExclusiveRoleLock(
        prefix / "locks" / "implementation.lock",
        config.runtime["lock_stale_seconds"],
    )
    with lock.acquired_for(new_run_id("symphony-resume")):
        incidents = (prefix / "incidents").resolve(strict=False)
        source = incident.expanduser().resolve(strict=True)
        if source.parent != incidents or source.suffix != ".json":
            raise ConfigError(
                "resume incident must be a direct private incident receipt"
            )
        if not re.fullmatch(r"[A-Z][A-Z0-9]*-[1-9][0-9]*", issue_identifier):
            raise ConfigError("resume issue identifier is invalid")
        try:
            incident_receipt = json.loads(source.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError("resume incident is unreadable") from exc
        violations = incident_receipt.get("violations")
        resumable_reasons = {"tokens_budget", "turns_budget", "wall_clock_budget"}
        if (
            incident_receipt.get("linear_state_changed") is not False
            or not isinstance(violations, list)
            or not any(
                item.get("issue_identifier") == issue_identifier
                and item.get("reason") in resumable_reasons
                for item in violations
            )
        ):
            raise ConfigError("resume incident is not a resumable issue budget stop")
        issue_metrics = incident_receipt.get("issue_metrics", {}).get(
            issue_identifier, {}
        )
        expected_epoch = issue_metrics.get("ledger_epoch_sha256")
        if not isinstance(expected_epoch, str):
            raise ConfigError("resume incident has no ledger epoch binding")
        ledger_path = prefix / "state" / "symphony-ledger.json"
        try:
            ledger = json.loads(ledger_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError("Symphony supervisor ledger is unavailable") from exc
        issues = ledger.get("issues")
        if not isinstance(issues, dict):
            raise ConfigError("Symphony supervisor ledger is malformed")
        record = issues.get(issue_identifier)
        history_path = (
            prefix
            / "state"
            / "symphony-ledger-history"
            / issue_identifier
            / f"{source.stem}.json"
        )
        resume_path = prefix / "state" / "symphony-resumes" / f"{source.stem}.json"
        continuation_path = (
            prefix / "state" / "symphony-continuations" / f"{issue_identifier}.json"
        )
        prior = None
        if resume_path.exists():
            try:
                prior = json.loads(resume_path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise ConfigError("resume receipt is unreadable") from exc
            if (
                prior.get("issue_identifier") != issue_identifier
                or prior.get("ledger_epoch_sha256") != expected_epoch
            ):
                raise ConfigError("resume receipt conflicts with requested issue")
            if prior.get("state") == "applied":
                if continuation_path.exists():
                    continuation_path.unlink()
                return {"status": "already_applied", **prior}
        if record is not None and _ledger_epoch_sha256(record) != expected_epoch:
            raise ConfigError("resume incident does not match the current ledger epoch")
        if record is None and not history_path.exists():
            raise ConfigError(
                "resume issue has no matching exhausted supervisor ledger"
            )
        if record is None:
            try:
                history = json.loads(history_path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise ConfigError("resume ledger history is unreadable") from exc
            archived = history.get("issue")
            if (
                not isinstance(archived, dict)
                or _ledger_epoch_sha256(archived) != expected_epoch
            ):
                raise ConfigError("resume ledger history does not match the incident")
        value = prior or {
            "schema_version": 1,
            "state": "pending",
            "issue_identifier": issue_identifier,
            "incident": source.name,
            "ledger_epoch_sha256": expected_epoch,
            "history": str(history_path),
            "linear_state_changed": False,
        }
        if prior is None:
            _save_json(resume_path, value)
        if record is not None:
            if history_path.exists():
                try:
                    history = json.loads(history_path.read_text())
                except (OSError, json.JSONDecodeError) as exc:
                    raise ConfigError("resume ledger history is unreadable") from exc
                if history.get("issue") != record:
                    raise ConfigError(
                        "resume ledger history conflicts with current epoch"
                    )
            else:
                _save_json(history_path, {"schema_version": 1, "issue": record})
            del issues[issue_identifier]
            _save_json(ledger_path, ledger)
        value.update({"state": "applied", "resumed_at": datetime.now(UTC).isoformat()})
        _save_json(resume_path, value)
        if continuation_path.exists():
            continuation_path.unlink()
        return {"status": "applied", **value}


def _fetch_state(port: int, timeout: float) -> dict[str, Any]:
    try:
        with request.urlopen(
            f"http://127.0.0.1:{port}/api/v1/state", timeout=timeout
        ) as response:
            payload = json.loads(response.read())
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Symphony state API unavailable") from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise RuntimeError("Symphony state API returned an error")
    return payload


def _ensure_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"Symphony state port {port} is already in use") from exc


def _stop_group(process: subprocess.Popen[Any], grace_seconds: float) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def supervise(
    config: AgentConfig,
    repository: Path,
    environ: dict[str, str] | None = None,
    *,
    worker_class: str = "standard",
    incident_sink: list[Path] | None = None,
) -> int:
    supplied = dict(os.environ if environ is None else environ)
    checked = preflight(config, repository, supplied, worker_class=worker_class)
    values = _sanitized_supervisor_environment(supplied, config.symphony["binary_env"])
    values["SANCTUM_GIT_BROKER_PYTHON"] = checked["git_broker_python"]
    values["SANCTUM_GIT_BROKER_SCRIPT"] = checked["git_broker_script"]
    values["SANCTUM_VALIDATION_RUNNER_PYTHON"] = checked["git_broker_python"]
    values["SANCTUM_VALIDATION_RUNNER_SCRIPT"] = checked["validation_runner_script"]
    values["SANCTUM_GIT_CREDENTIAL_HELPER"] = checked["git_credential_helper"]
    values["SANCTUM_GIT_GH_CONFIG_DIR"] = checked["git_github_config_dir"]
    role = config.roles[checked["role_name"]]
    workspace_root = Path(checked["workspace_root"])
    workspace_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if workspace_root.is_symlink():
        raise ConfigError("Symphony workspace root may not be a symlink")
    workspace_root.chmod(0o700)
    prefix = config.runtime_prefix(values)
    ensure_private_prefix(prefix)
    continuations = load_continuations(prefix)
    broker_state = prefix / "state" / "git-control-plane"
    broker_state.mkdir(parents=True, exist_ok=True, mode=0o700)
    broker_state.chmod(0o700)
    values["SANCTUM_GIT_BROKER_STATE"] = str(broker_state)
    validation_state = prefix / "state" / "validation"
    validation_state.mkdir(parents=True, exist_ok=True, mode=0o700)
    validation_state.chmod(0o700)
    values["SANCTUM_VALIDATION_STATE"] = str(validation_state)
    run_id = new_run_id("implementation")
    log = JsonlRunLog(
        prefix / "logs" / "implementation" / f"{run_id}.jsonl",
        run_id,
        "implementation",
        RunMode.LIVE,
    )
    lock = ExclusiveRoleLock(
        prefix / "locks" / "implementation.lock", config.runtime["lock_stale_seconds"]
    )
    ledger_path = prefix / "state" / "symphony-ledger.json"
    try:
        ledger = (
            json.loads(ledger_path.read_text())
            if ledger_path.exists()
            else {"schema_version": 1, "issues": {}}
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid Symphony supervisor ledger") from exc
    port = config.symphony["state_port"]
    _ensure_port_available(port)
    output = prefix / "logs" / "implementation" / f"{run_id}.symphony.log"
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with lock.acquired_for(run_id), output.open("wb") as stream:
        output.chmod(0o600)
        command = [
            *checked["launch_prefix"],
            "--i-understand-that-this-will-be-running-without-the-usual-guardrails",
            "--logs-root",
            str(prefix / "logs" / "symphony"),
            "--port",
            str(port),
            checked["workflow"],
        ]
        launched_at = time.time()
        process = subprocess.Popen(
            command,
            cwd=repository,
            env=values,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log.emit(
            "started",
            pid=process.pid,
            state_port=port,
            worker_class=worker_class,
            model=checked["model"],
            reasoning_effort=checked["reasoning_effort"],
        )
        log.emit(
            "agent_run_started",
            worker_class=worker_class,
            model=checked["model"],
            reasoning_effort=checked["reasoning_effort"],
        )
        unavailable_since: float | None = None
        warning_events: set[tuple[str, str]] = set()
        seen_sessions: set[tuple[str, str]] = set()
        turn_high_water: dict[str, int] = {}
        try:
            while process.poll() is None:
                time.sleep(config.symphony["poll_seconds"])
                if output.stat().st_size > config.symphony["output_limit_bytes"]:
                    violations = [
                        SymphonyViolation(
                            "service",
                            "output_budget",
                            output.stat().st_size,
                            config.symphony["output_limit_bytes"],
                            TerminationClass.TIME_BUDGET.value,
                        )
                    ]
                else:
                    try:
                        snapshot = _fetch_state(
                            port, config.symphony["state_timeout_seconds"]
                        )
                        unavailable_since = None
                    except RuntimeError:
                        unavailable_since = unavailable_since or time.monotonic()
                        if time.monotonic() - unavailable_since <= 30:
                            continue
                        violations = [
                            SymphonyViolation(
                                "service",
                                "state_api_stall",
                                time.monotonic() - unavailable_since,
                                30,
                                TerminationClass.ENVIRONMENT.value,
                            )
                        ]
                    else:
                        prior_issues = set(ledger.get("issues", {}))
                        violations = evaluate_snapshot(
                            snapshot,
                            ledger,
                            runtime_id=run_id,
                            now=time.time(),
                            wall_clock_seconds=role.wall_clock_seconds,
                            max_turns=role.max_turns,
                            max_tokens=role.max_tokens,
                            max_retries=role.max_retries,
                            max_concurrency=config.symphony["max_concurrency"],
                            continuations=continuations,
                        )
                        violations.extend(
                            validation_environment_violations(
                                validation_state, snapshot, launched_at=launched_at
                            )
                        )
                        _save_json(ledger_path, ledger)
                        now = time.time()
                        for entry in snapshot.get("running", []):
                            identifier = entry["issue_identifier"]
                            session = (
                                entry.get("session_id")
                                or f"started:{entry.get('started_at')}"
                            )
                            session_identity = (identifier, session)
                            record = ledger.get("issues", {}).get(identifier, {})
                            if session_identity not in seen_sessions:
                                already_seen = any(
                                    issue_id == identifier
                                    for issue_id, _ in seen_sessions
                                )
                                seen_sessions.add(session_identity)
                                if already_seen or len(record.get("runtimes", {})) > 1:
                                    log.emit(
                                        "agent_run_resumed",
                                        issue_id=identifier,
                                        worker_class=worker_class,
                                    )
                            totals = _ledger_totals(record, now)
                            total_turns = int(totals["turn_count"])
                            if total_turns > turn_high_water.get(identifier, 0):
                                turn_high_water[identifier] = total_turns
                                log.emit(
                                    "agent_turn_completed",
                                    issue_id=identifier,
                                    turn_count=total_turns,
                                    tokens=int(totals["tokens"]),
                                    input_tokens=int(totals["input_tokens"]),
                                    output_tokens=int(totals["output_tokens"]),
                                )
                            limits = {
                                "elapsed_ms": (
                                    role.wall_clock_seconds
                                    + continuations.get(identifier, {}).get(
                                        "wall_clock_seconds", 0
                                    )
                                )
                                * 1000,
                                "turn_count": role.max_turns
                                + continuations.get(identifier, {}).get("max_turns", 0),
                                "tokens": role.max_tokens
                                + continuations.get(identifier, {}).get(
                                    "max_tokens", 0
                                ),
                            }
                            for name, limit in limits.items():
                                warning = (identifier, name)
                                if (
                                    warning not in warning_events
                                    and totals[name]
                                    >= limit * config.symphony["budget_warning_ratio"]
                                ):
                                    warning_events.add(warning)
                                    log.emit(
                                        "agent_budget_warning",
                                        issue_id=identifier,
                                        budget=name,
                                        observed=totals[name],
                                        limit=limit,
                                    )
                        removed = prior_issues - set(ledger.get("issues", {}))
                        for identifier in sorted(removed):
                            log.emit(
                                "agent_run_completed",
                                issue_id=identifier,
                                worker_class=worker_class,
                            )
                if violations:
                    incident_metrics = {}
                    for item in violations:
                        record = ledger.get("issues", {}).get(item.issue_identifier)
                        if isinstance(record, dict):
                            incident_metrics[item.issue_identifier] = {
                                **_ledger_totals(record, time.time()),
                                "attempt": record.get("max_retry", 0),
                                "ledger_epoch_sha256": _ledger_epoch_sha256(record),
                            }
                    incident = {
                        "schema_version": 1,
                        "run_id": run_id,
                        "stopped_at": datetime.now(UTC).isoformat(),
                        "violations": [item.__dict__ for item in violations],
                        "linear_state_changed": False,
                        "worker_class": worker_class,
                        "model": checked["model"],
                        "reasoning_effort": checked["reasoning_effort"],
                        "issue_metrics": incident_metrics,
                        "validation_profile": None,
                        "git_operation_state": None,
                    }
                    incident_path = prefix / "incidents" / f"{run_id}.json"
                    _save_json(incident_path, incident)
                    if incident_sink is not None:
                        incident_sink.append(incident_path)
                    log.emit(
                        "agent_budget_exhausted",
                        violations=incident["violations"],
                        worker_class=worker_class,
                    )
                    log.emit(
                        "agent_failure_classified",
                        classifications=sorted(
                            {item.termination_class for item in violations}
                        ),
                        worker_class=worker_class,
                    )
                    log.emit(
                        "budget_stopped",
                        violations=incident["violations"],
                        incident=str(incident_path),
                    )
                    _stop_group(process, config.symphony["shutdown_grace_seconds"])
                    return 75
        finally:
            _stop_group(process, config.symphony["shutdown_grace_seconds"])
        log.emit("exited", returncode=process.returncode)
        log.emit(
            "agent_run_completed",
            returncode=process.returncode,
            worker_class=worker_class,
        )
        return process.returncode or 0
