"""Best-effort, content-free Symphony attempt evidence for the local AO collector.

This module is deliberately outside the worker decision path.  Its input is the
structured Symphony state API, never a prompt, workpad, tool body, or model
response.  A missing collector must not affect supervision.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import request
from uuid import UUID

COLLECTOR_TRACES_URL = "http://127.0.0.1:4318/v1/traces"
_ISSUE = re.compile(r"[A-Z][A-Z0-9]*-[1-9][0-9]*\Z")
_SESSION = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})-"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\Z"
)


def _uuid(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = str(UUID(value))
        return parsed if parsed == value.lower() else None
    except ValueError:
        return None


def _session_ids(value: Any) -> tuple[str, str] | None:
    matched = _SESSION.fullmatch(value) if isinstance(value, str) else None
    if matched is None:
        return None
    return matched.group(1), matched.group(2)


def _attempt_id(runtime_id: str, issue_id: str, started_at: str) -> str:
    return hashlib.sha256(
        f"{runtime_id}\0{issue_id}\0{started_at}".encode()
    ).hexdigest()[:24]


@dataclass(frozen=True)
class CorrelationEvent:
    name: str
    fields: dict[str, str | int | bool]


@dataclass
class AttemptObserver:
    """Remember only observed attempt/session transitions in one supervisor run."""

    runtime_id: str
    worker_class: str
    requested_model: str
    reasoning_effort: str
    active: dict[str, dict[str, Any]] = field(default_factory=dict)
    seen_retries: set[tuple[str, int]] = field(default_factory=set)
    seen_blocked: set[str] = field(default_factory=set)

    def observe(self, snapshot: dict[str, Any]) -> list[CorrelationEvent]:
        events: list[CorrelationEvent] = []
        current: set[str] = set()
        for entry in snapshot.get("running", []):
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("issue_identifier")
            issue_id = _uuid(entry.get("issue_id"))
            started_at = entry.get("started_at")
            if (
                not isinstance(identifier, str)
                or _ISSUE.fullmatch(identifier) is None
                or issue_id is None
                or not isinstance(started_at, str)
                or not started_at
            ):
                continue
            try:
                datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            attempt_id = _attempt_id(self.runtime_id, issue_id, started_at)
            current.add(attempt_id)
            base = {
                "sanctum.issue.identifier": identifier,
                "sanctum.issue.uuid": issue_id,
                "sanctum.symphony.run_id": self.runtime_id,
                "sanctum.symphony.attempt_id": attempt_id,
                "sanctum.worker.class": self.worker_class,
            }
            if attempt_id not in self.active:
                self.active[attempt_id] = {
                    "base": base,
                    "session": None,
                    "tokens": {},
                    "workspace_path": None,
                }
                events.append(
                    CorrelationEvent(
                        "sanctum.symphony.attempt_observed",
                        {
                            **base,
                            "sanctum.symphony.started_at": started_at,
                            "sanctum.codex.requested_model": self.requested_model,
                            "sanctum.codex.reasoning_effort": self.reasoning_effort,
                        },
                    )
                )
            session = _session_ids(entry.get("session_id"))
            if isinstance(entry.get("workspace_path"), str):
                self.active[attempt_id]["workspace_path"] = entry["workspace_path"]
            if session is not None and session != self.active[attempt_id]["session"]:
                self.active[attempt_id]["session"] = session
                events.append(
                    CorrelationEvent(
                        "sanctum.symphony.codex_session_observed",
                        {
                            **base,
                            "sanctum.codex.thread_id": session[0],
                            "sanctum.codex.turn_id": session[1],
                        },
                    )
                )
            tokens = entry.get("tokens")
            if isinstance(tokens, dict):
                self.active[attempt_id]["tokens"] = {
                    name: value
                    for name, value in (
                        ("input", tokens.get("input_tokens")),
                        ("output", tokens.get("output_tokens")),
                        ("total", tokens.get("total_tokens")),
                    )
                    if type(value) is int and value >= 0
                }
        for entry in snapshot.get("retrying", []):
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("issue_identifier")
            retry = entry.get("attempt")
            if (
                not isinstance(identifier, str)
                or _ISSUE.fullmatch(identifier) is None
                or type(retry) is not int
                or retry < 0
                or (identifier, retry) in self.seen_retries
            ):
                continue
            self.seen_retries.add((identifier, retry))
            events.append(
                CorrelationEvent(
                    "sanctum.symphony.retry_scheduled",
                    {
                        "sanctum.issue.identifier": identifier,
                        "sanctum.symphony.run_id": self.runtime_id,
                        "sanctum.symphony.retry_number": retry,
                    },
                )
            )
        for entry in snapshot.get("blocked", []):
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("issue_identifier")
            if (
                not isinstance(identifier, str)
                or _ISSUE.fullmatch(identifier) is None
                or identifier in self.seen_blocked
            ):
                continue
            self.seen_blocked.add(identifier)
            events.append(
                CorrelationEvent(
                    "sanctum.symphony.blocked_observed",
                    {
                        "sanctum.issue.identifier": identifier,
                        "sanctum.symphony.run_id": self.runtime_id,
                        "sanctum.workflow.observed_state": "blocked",
                    },
                )
            )
        for attempt_id in set(self.active) - current:
            record = self.active.pop(attempt_id)
            fields = dict(record["base"])
            session = record["session"]
            if session is not None:
                fields["sanctum.codex.thread_id"] = session[0]
                fields["sanctum.codex.turn_id"] = session[1]
            for name, value in record["tokens"].items():
                fields[f"sanctum.codex.context_{name}_tokens"] = value
            # Disappearance from the state API is not a workflow outcome.
            events.append(
                CorrelationEvent("sanctum.symphony.attempt_no_longer_active", fields)
            )
        return events


def persist_active_bindings(
    observer: AttemptObserver, state_root: Path, workspace_root: Path
) -> None:
    """Offer Git receipts an observed attempt binding; never authorize Git work."""
    directory = state_root / "ao-correlation" / "active"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    active_issues: set[str] = set()
    for attempt_id, record in observer.active.items():
        base = record["base"]
        identifier = base["sanctum.issue.identifier"]
        workspace = record["workspace_path"]
        if not isinstance(workspace, str):
            continue
        resolved = Path(workspace).resolve(strict=False)
        if not resolved.is_relative_to(workspace_root.resolve(strict=False)):
            continue
        active_issues.add(identifier)
        path = directory / f"{identifier}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "issue_identifier": identifier,
                    "workspace_path": str(resolved),
                    "run_id": observer.runtime_id,
                    "attempt_id": attempt_id,
                    "updated_at": time.time(),
                },
                sort_keys=True,
            )
            + "\n"
        )
        temporary.chmod(0o600)
        temporary.replace(path)
    for path in directory.glob("*.json"):
        if path.stem not in active_issues:
            try:
                current = json.loads(path.read_text())
                if current.get("run_id") == observer.runtime_id:
                    path.unlink()
            except (OSError, ValueError):
                pass


def read_active_binding(
    state_root: Path,
    issue_identifier: str,
    workspace: Path,
    *,
    now: float | None = None,
) -> dict[str, str] | None:
    """Return only a fresh, exact-workspace correlation hint for a Git receipt."""
    if _ISSUE.fullmatch(issue_identifier) is None:
        return None
    path = state_root.parent / "ao-correlation" / "active" / f"{issue_identifier}.json"
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text())
        age = (time.time() if now is None else now) - value["updated_at"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if (
        value.get("schema_version") != 1
        or value.get("issue_identifier") != issue_identifier
        or value.get("workspace_path") != str(workspace.resolve(strict=False))
        or not isinstance(value.get("run_id"), str)
        or not re.fullmatch(r"implementation-[0-9TZ]+-[0-9a-f]{12}", value["run_id"])
        or not isinstance(value.get("attempt_id"), str)
        or not re.fullmatch(r"[0-9a-f]{24}", value["attempt_id"])
        or not 0 <= age <= 15
    ):
        return None
    return {"ao_run_id": value["run_id"], "ao_attempt_id": value["attempt_id"]}


def applied_receipts(state_root: Path, issue_identifier: str) -> list[dict[str, Any]]:
    """Read only confirmed host Git facts for one issue, never workpad prose."""
    if _ISSUE.fullmatch(issue_identifier) is None:
        return []
    directory = state_root / "git-control-plane" / "operations" / issue_identifier
    if directory.is_symlink() or not directory.is_dir():
        return []
    receipts: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            value = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if (
            isinstance(value, dict)
            and value.get("schema_version") == 1
            and value.get("state") == "applied"
            and value.get("issue_identifier") == issue_identifier
            and value.get("kind") in {"commit", "pull-request"}
        ):
            receipts.append(value)
    return receipts


def validation_receipts(
    state_root: Path, issue_identifier: str
) -> list[dict[str, Any]]:
    if _ISSUE.fullmatch(issue_identifier) is None:
        return []
    directory = state_root / "validation" / "receipts" / issue_identifier
    if directory.is_symlink() or not directory.is_dir():
        return []
    receipts: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            value = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if (
            isinstance(value, dict)
            and value.get("issue_id") == issue_identifier
            and value.get("state") == "completed"
            and type(value.get("passed")) is bool
            and isinstance(value.get("completed_at"), str)
            and isinstance(value.get("profile"), str)
        ):
            receipts.append(value)
    return receipts


def pr_number_for_issue(receipts: list[dict[str, Any]]) -> int | None:
    numbers = {
        receipt.get("number")
        for receipt in receipts
        if receipt.get("kind") == "pull-request"
        and type(receipt.get("number")) is int
        and receipt["number"] > 0
    }
    return next(iter(numbers)) if len(numbers) == 1 else None


def _ci_result(checks: Any) -> str | None:
    if not isinstance(checks, list) or not checks:
        return None
    if any(not isinstance(check, dict) for check in checks):
        return None
    if any(check.get("status") != "COMPLETED" for check in checks):
        return None
    conclusions = {check.get("conclusion") for check in checks}
    if conclusions == {"SUCCESS"}:
        return "passed"
    if conclusions & {"FAILURE", "TIMED_OUT", "ACTION_REQUIRED"}:
        return "failed"
    return None


def outcome_event(
    issue_identifier: str,
    receipts: list[dict[str, Any]],
    *,
    validations: list[dict[str, Any]] | None = None,
    linear_issue: dict[str, Any] | None = None,
    pull_request: dict[str, Any] | None = None,
) -> CorrelationEvent | None:
    """Describe only provider-confirmed issue facts; unknowns stay absent."""
    if _ISSUE.fullmatch(issue_identifier) is None:
        return None
    fields: dict[str, str | int | bool] = {"sanctum.issue.identifier": issue_identifier}
    if validations:
        ordered = sorted(
            (
                item
                for item in validations
                if isinstance(item, dict)
                and item.get("issue_id") == issue_identifier
                and type(item.get("passed")) is bool
                and isinstance(item.get("completed_at"), str)
                and isinstance(item.get("profile"), str)
            ),
            key=lambda item: item.get("completed_at", ""),
        )
        if ordered:
            latest = ordered[-1]
            fields["sanctum.validation.observed_run_count"] = len(ordered)
            fields["sanctum.validation.observed_failed_count"] = sum(
                item.get("passed") is False for item in ordered
            )
            fields["sanctum.validation.latest_passed"] = latest["passed"]
            fields["sanctum.validation.latest_profile"] = latest["profile"]
    if (
        isinstance(linear_issue, dict)
        and linear_issue.get("identifier") == issue_identifier
    ):
        issue_id = _uuid(linear_issue.get("id"))
        if issue_id is not None:
            fields["sanctum.issue.uuid"] = issue_id
        state = linear_issue.get("state")
        name = state.get("name") if isinstance(state, dict) else None
        if name in {
            "Ready for Agent",
            "In Progress",
            "Rework",
            "Human Review",
            "Done",
            "Canceled",
            "Cancelled",
        }:
            fields["sanctum.workflow.linear_state"] = name
    number = pr_number_for_issue(receipts)
    if number is not None and isinstance(pull_request, dict):
        expected_branch = f"symphony/{issue_identifier.lower()}"
        if (
            pull_request.get("number") == number
            and pull_request.get("baseRefName") == "v1.3-dev"
            and pull_request.get("headRefName") == expected_branch
            and pull_request.get("state") in {"OPEN", "CLOSED", "MERGED"}
        ):
            fields["sanctum.github.pr_number"] = number
            fields["sanctum.github.pr_state"] = pull_request["state"]
            fields["sanctum.github.branch"] = expected_branch
            head = pull_request.get("headRefOid")
            matching = [
                receipt
                for receipt in receipts
                if receipt.get("kind") == "pull-request"
                and receipt.get("number") == number
                and receipt.get("head") == head
                and isinstance(head, str)
                and re.fullmatch(r"[0-9a-f]{40}", head)
            ]
            if len(matching) == 1:
                fields["sanctum.github.commit_sha"] = head
                binding = matching[0]
                if isinstance(binding.get("ao_attempt_id"), str) and re.fullmatch(
                    r"[0-9a-f]{24}", binding["ao_attempt_id"]
                ):
                    fields["sanctum.symphony.attempt_id"] = binding["ao_attempt_id"]
                if isinstance(binding.get("ao_run_id"), str):
                    fields["sanctum.symphony.run_id"] = binding["ao_run_id"]
            ci = _ci_result(pull_request.get("statusCheckRollup"))
            if ci is not None:
                fields["sanctum.github.ci_result"] = ci
    if len(fields) == 1:
        return None
    return CorrelationEvent("sanctum.engineering.outcome_observed", fields)


def otlp_trace_payload(event: CorrelationEvent, *, at_ns: int) -> dict[str, Any]:
    """Encode an independent OTLP span; joining uses safe IDs, not trace-parent guesses."""
    safe_fields = {
        "sanctum.observability.source": "symphony-host",
        **event.fields,
    }
    attributes = [
        (
            {"key": key, "value": {"boolValue": value}}
            if type(value) is bool
            else (
                {"key": key, "value": {"intValue": str(value)}}
                if type(value) is int
                else {"key": key, "value": {"stringValue": value}}
            )
        )
        for key, value in sorted(safe_fields.items())
    ]
    identity = json.dumps([event.name, event.fields], sort_keys=True)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": "sanctum-symphony-correlation"},
                        },
                        {
                            "key": "deployment.environment",
                            "value": {"stringValue": "sanctum-codex-dev"},
                        },
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "sanctum.ao_correlation", "version": "1"},
                        "spans": [
                            {
                                "traceId": digest[:32],
                                "spanId": digest[32:48],
                                "name": event.name,
                                "kind": 1,
                                "startTimeUnixNano": str(at_ns),
                                "endTimeUnixNano": str(at_ns + 1),
                                "attributes": attributes,
                            }
                        ],
                    }
                ],
            }
        ]
    }


class BestEffortAOEmitter:
    """Send only allowlisted host evidence to loopback, with a private journal."""

    def __init__(self, journal: Path, endpoint: str = COLLECTOR_TRACES_URL):
        self.journal = journal
        self.endpoint = endpoint

    def emit(self, event: CorrelationEvent) -> bool:
        at_ns = time.time_ns()
        payload = otlp_trace_payload(event, at_ns=at_ns)
        try:
            self.journal.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self.journal.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"at_ns": at_ns, **event.__dict__}) + "\n")
            self.journal.chmod(0o600)
        except OSError:
            pass
        try:
            outbound = request.Request(
                self.endpoint,
                data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(outbound, timeout=0.2):
                pass
            return True
        except (OSError, ValueError):
            # Evidence delivery never gates execution or changes an outcome.
            return False
