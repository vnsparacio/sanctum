"""Sanctum-owned hard governor around the external Symphony service."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
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


def _parse_time(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def evaluate_snapshot(
    snapshot: dict[str, Any],
    ledger: dict[str, Any],
    *,
    now: float,
    wall_clock_seconds: int,
    stall_seconds: int,
    max_turns: int,
    max_tokens: int,
    max_retries: int,
) -> list[SymphonyViolation]:
    if not isinstance(snapshot, dict):
        raise ValueError("Symphony snapshot must be an object")
    running = snapshot.get("running", [])
    retrying = snapshot.get("retrying", [])
    if not isinstance(running, list) or not isinstance(retrying, list):
        raise ValueError("Symphony snapshot collections are malformed")
    issues = ledger.setdefault("issues", {})
    violations: list[SymphonyViolation] = []
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
            {"first_seen": now, "last_seen": now, "sessions": {}, "max_retry": 0},
        )
        record["last_seen"] = now
        sessions = record.setdefault("sessions", {})
        if not isinstance(sessions, dict):
            raise ValueError("Symphony supervisor session ledger is malformed")
        session = entry.get("session_id")
        session_key = (
            session
            if isinstance(session, str) and session
            else f"started:{entry.get('started_at')}"
        )
        session_record = sessions.setdefault(session_key, {"turns": 0, "tokens": 0})
        elapsed = max(0, now - float(record["first_seen"]))
        turns = entry.get("turn_count", 0)
        tokens = (
            entry.get("tokens", {}).get("total_tokens", 0)
            if isinstance(entry.get("tokens"), dict)
            else 0
        )
        if type(turns) is not int or turns < 0 or type(tokens) is not int or tokens < 0:
            raise ValueError("Symphony running counters are malformed")
        session_record["turns"] = max(session_record.get("turns", 0), turns)
        session_record["tokens"] = max(session_record.get("tokens", 0), tokens)
        total_turns = sum(item["turns"] for item in sessions.values())
        total_tokens = sum(item["tokens"] for item in sessions.values())
        last_event = _parse_time(entry.get("last_event_at")) or _parse_time(
            entry.get("started_at")
        )
        checks = [
            ("wall_clock_budget", elapsed, wall_clock_seconds),
            ("turns_budget", total_turns, max_turns),
            ("tokens_budget", total_tokens, max_tokens),
        ]
        if last_event is not None:
            checks.append(("stall_budget", max(0, now - last_event), stall_seconds))
        for reason, observed, limit in checks:
            if type(observed) in {int, float} and observed > limit:
                violations.append(
                    SymphonyViolation(identifier, reason, float(observed), float(limit))
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
            {"first_seen": now, "last_seen": now, "sessions": {}, "max_retry": 0},
        )
        record["last_seen"] = now
        record["max_retry"] = max(record.get("max_retry", 0), attempt)
        elapsed = max(0, now - float(record["first_seen"]))
        if elapsed > wall_clock_seconds:
            violations.append(
                SymphonyViolation(
                    identifier, "wall_clock_budget", elapsed, float(wall_clock_seconds)
                )
            )
        if attempt > max_retries:
            violations.append(
                SymphonyViolation(
                    identifier, "retries_budget", float(attempt), float(max_retries)
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


def preflight(
    config: AgentConfig, repository: Path, environ: dict[str, str] | None = None
) -> dict[str, Any]:
    values = os.environ if environ is None else environ
    binary = _resolve_binary(config, values)
    workflow = repository / config.symphony["workflow"]
    if not workflow.is_file():
        raise ConfigError("Symphony workflow is unavailable")
    if not values.get("LINEAR_API_KEY"):
        raise ConfigError("LINEAR_API_KEY is required by Symphony")
    raw_root = values.get("SYMPHONY_WORKSPACE_ROOT")
    if not raw_root or not Path(raw_root).expanduser().is_absolute():
        raise ConfigError("SYMPHONY_WORKSPACE_ROOT must be an absolute external path")
    workspace_root = Path(raw_root).expanduser().resolve(strict=False)
    source = repository.resolve()
    if workspace_root == source or workspace_root.is_relative_to(source):
        raise ConfigError("Symphony workspace root must remain outside source")
    return {
        "binary": binary,
        "launch_prefix": _launch_prefix(binary),
        "workflow": str(workflow),
        "workspace_root": str(workspace_root),
    }


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
    config: AgentConfig, repository: Path, environ: dict[str, str] | None = None
) -> int:
    values = dict(os.environ if environ is None else environ)
    checked = preflight(config, repository, values)
    role = config.roles["implementation"]
    workspace_root = Path(checked["workspace_root"])
    workspace_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if workspace_root.is_symlink():
        raise ConfigError("Symphony workspace root may not be a symlink")
    workspace_root.chmod(0o700)
    prefix = config.runtime_prefix(values)
    ensure_private_prefix(prefix)
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
            model=config.model_for("implementation").model,
        )
        unavailable_since: float | None = None
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
                            )
                        ]
                    else:
                        violations = evaluate_snapshot(
                            snapshot,
                            ledger,
                            now=time.time(),
                            wall_clock_seconds=role.wall_clock_seconds,
                            stall_seconds=300,
                            max_turns=role.max_turns,
                            max_tokens=role.max_tokens,
                            max_retries=role.max_retries,
                        )
                        _save_json(ledger_path, ledger)
                if violations:
                    incident = {
                        "schema_version": 1,
                        "run_id": run_id,
                        "stopped_at": datetime.now(UTC).isoformat(),
                        "violations": [item.__dict__ for item in violations],
                        "linear_state_changed": False,
                    }
                    incident_path = prefix / "incidents" / f"{run_id}.json"
                    _save_json(incident_path, incident)
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
        return process.returncode or 0
