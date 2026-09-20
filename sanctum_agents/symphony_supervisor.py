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
    blocked = snapshot.get("blocked", [])
    if (
        not isinstance(running, list)
        or not isinstance(retrying, list)
        or not isinstance(blocked, list)
    ):
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
    for entry in blocked:
        if not isinstance(entry, dict):
            raise ValueError("Symphony blocked entry is malformed")
        identifier = entry.get("issue_identifier") or entry.get("identifier")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("Symphony blocked entry is malformed")
        active_identifiers.add(identifier)
        record = issues.setdefault(
            identifier,
            {"first_seen": now, "last_seen": now, "sessions": {}, "max_retry": 0},
        )
        record["last_seen"] = now
        violations.append(
            SymphonyViolation(identifier, "operator_action_required", 1.0, 0.0)
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


def _verified_broker_assets(repository: Path) -> tuple[str, str]:
    manifest_path = repository / "SOURCE-MANIFEST.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("source manifest unavailable for Git broker") from exc
    relative_paths = (
        "scripts/sanctum_git_broker.py",
        "sanctum_agents/git_control_plane.py",
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
    safe_path = re.compile(r"^[A-Za-z0-9_./-]+$")
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ConfigError("reviewed Git broker Python is unavailable")
    if not safe_path.fullmatch(str(python)) or not safe_path.fullmatch(str(script)):
        raise ConfigError("Git broker executable paths contain unsupported characters")
    return str(python), str(script)


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
    broker_python, broker_script = _verified_broker_assets(repository)
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
        "git_credential_helper": str(credential_helper_path),
        "git_github_config_dir": str(github_config_dir),
        "wall_clock_timeout_seconds": config.roles["implementation"].wall_clock_seconds,
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
    supplied = dict(os.environ if environ is None else environ)
    checked = preflight(config, repository, supplied)
    values = _sanitized_supervisor_environment(supplied, config.symphony["binary_env"])
    values["SANCTUM_GIT_BROKER_PYTHON"] = checked["git_broker_python"]
    values["SANCTUM_GIT_BROKER_SCRIPT"] = checked["git_broker_script"]
    values["SANCTUM_GIT_CREDENTIAL_HELPER"] = checked["git_credential_helper"]
    values["SANCTUM_GIT_GH_CONFIG_DIR"] = checked["git_github_config_dir"]
    role = config.roles["implementation"]
    workspace_root = Path(checked["workspace_root"])
    workspace_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if workspace_root.is_symlink():
        raise ConfigError("Symphony workspace root may not be a symlink")
    workspace_root.chmod(0o700)
    prefix = config.runtime_prefix(values)
    ensure_private_prefix(prefix)
    broker_state = prefix / "state" / "git-control-plane"
    broker_state.mkdir(parents=True, exist_ok=True, mode=0o700)
    broker_state.chmod(0o700)
    values["SANCTUM_GIT_BROKER_STATE"] = str(broker_state)
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
