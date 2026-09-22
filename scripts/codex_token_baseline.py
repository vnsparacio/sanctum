#!/usr/bin/env python3
"""Build a content-free Codex usage baseline from local Token Meter evidence."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib import parse, request

ISSUE_RE = re.compile(r"^[A-Z][A-Z0-9]*-[1-9][0-9]*$")
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class TokenMeterError(RuntimeError):
    """Raised when local Token Meter evidence is absent or malformed."""


def _nonnegative_int(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _number(value: Any) -> float | None:
    return float(value) if type(value) in {int, float} and value >= 0 else None


def validate_base_url(value: str) -> str:
    parsed = parse.urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise TokenMeterError("Token Meter URL must be a bare loopback HTTP origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise TokenMeterError("Token Meter URL has an invalid port") from exc
    if port is None or not 1 <= port <= 65535:
        raise TokenMeterError("Token Meter URL must include an explicit port")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return f"http://{host}:{port}"


def fetch_json(base_url: str, path: str, timeout: float = 10) -> dict[str, Any]:
    if not path.startswith("/"):
        raise TokenMeterError("Token Meter path must be absolute")
    try:
        with request.urlopen(base_url + path, timeout=timeout) as response:
            payload = json.loads(response.read())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise TokenMeterError(
            f"Token Meter request failed for {path.split('?')[0]}"
        ) from exc
    if not isinstance(payload, dict):
        raise TokenMeterError("Token Meter returned a non-object response")
    return payload


def _sum_model_metric(session: dict[str, Any], name: str) -> int | None:
    rows = session.get("model_stats")
    if not isinstance(rows, list) or not rows:
        return None
    values = [_nonnegative_int(row.get(name)) for row in rows if isinstance(row, dict)]
    return (
        sum(values) if values and all(value is not None for value in values) else None
    )


def _add_optional(values: list[int | None]) -> int | None:
    return (
        sum(value for value in values if value is not None)
        if all(value is not None for value in values)
        else None
    )


def _maximum_optional(values: list[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return max(available) if len(available) == len(values) and available else None


def _issue_for_project(project: Any, workspace_root: Path) -> str | None:
    if not isinstance(project, str) or not project:
        return None
    candidate = Path(project).expanduser().resolve(strict=False)
    if candidate.parent != workspace_root or not ISSUE_RE.fullmatch(candidate.name):
        return None
    return candidate.name


def _aggregate_issue(issue: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    input_tokens = _add_optional(
        [_nonnegative_int(row.get("input_tokens")) for row in rows]
    )
    output_tokens = _add_optional(
        [_nonnegative_int(row.get("output_tokens")) for row in rows]
    )
    total_tokens = _add_optional([_nonnegative_int(row.get("tokens")) for row in rows])
    cached_input = _add_optional([row["_cache_read_tokens"] for row in rows])
    uncached_input = (
        input_tokens - cached_input
        if input_tokens is not None and cached_input is not None
        else None
    )
    cache_percent = (
        round(cached_input * 100 / input_tokens, 2)
        if input_tokens and cached_input is not None
        else None
    )
    input_per_output = (
        round(input_tokens / output_tokens, 2)
        if input_tokens is not None and output_tokens
        else None
    )
    starts = [row.get("start") for row in rows if isinstance(row.get("start"), str)]
    lasts = [row.get("last") for row in rows if isinstance(row.get("last"), str)]
    models = sorted(
        {
            str(model)
            for row in rows
            for model in (row.get("models") or [])
            if isinstance(model, str) and model
        }
    )
    return {
        "issue": issue,
        "sessions": len(rows),
        "session_restarts": max(0, len(rows) - 1),
        "start": min(starts) if len(starts) == len(rows) else None,
        "last": max(lasts) if len(lasts) == len(rows) else None,
        "wall_duration_seconds": _add_optional(
            [_nonnegative_int(row.get("wall_duration_s")) for row in rows]
        ),
        "turns": _add_optional([_nonnegative_int(row.get("turns")) for row in rows]),
        "executions": _add_optional([row["_executions"] for row in rows]),
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input,
        "uncached_input_tokens": uncached_input,
        "cache_percent": cache_percent,
        "output_tokens": output_tokens,
        "reasoning_tokens": _add_optional([row["_reasoning_tokens"] for row in rows]),
        "input_tokens_per_output_token": input_per_output,
        "peak_context_tokens": _maximum_optional(
            [row["_context_tokens"] for row in rows]
        ),
        "peak_context_percent": (
            round(value * 100, 2)
            if (value := _maximum_optional([row["_context_percent"] for row in rows]))
            is not None
            else None
        ),
        "tool_calls": _add_optional([row["_tool_calls"] for row in rows]),
        "tool_errors": _add_optional([row["_tool_errors"] for row in rows]),
        "tool_output_tokens_estimate": _add_optional(
            [row["_tool_output_tokens"] for row in rows]
        ),
        "subagent_turns": _add_optional([row["_subagent_turns"] for row in rows]),
        "truncated_sessions": sum(bool(row["_trace_truncated"]) for row in rows),
        "models": models,
        "reported_usage_sessions": sum(
            row.get("usage_basis") == "reported" for row in rows
        ),
        "unavailable_signals": [
            "intra_session_context_growth",
            "workflow_retry_count",
            "repeated_failed_approaches",
            "unused_tool_or_context_overhead",
            "completion_rework_outcome",
            "pull_request_ci_outcome",
        ],
    }


def collect_baseline(
    base_url: str,
    workspace_root: Path,
    issues: set[str] | None = None,
    *,
    fetcher: Callable[[str, str], dict[str, Any]] = fetch_json,
) -> dict[str, Any]:
    base_url = validate_base_url(base_url)
    workspace_root = workspace_root.expanduser().resolve(strict=False)
    if not workspace_root.is_absolute():
        raise TokenMeterError("workspace root must be absolute")
    if issues is not None and any(not ISSUE_RE.fullmatch(issue) for issue in issues):
        raise TokenMeterError("issue filters must use a Linear-style identifier")

    health = fetcher(base_url, "/health")
    clients = health.get("source_clients")
    if (
        health.get("ok") is not True
        or health.get("state_ready") is not True
        or not isinstance(clients, dict)
        or _nonnegative_int(clients.get("codex")) in {None, 0}
    ):
        raise TokenMeterError("Token Meter is not ready with Codex evidence")
    if health.get("runtime_adapter_failures") not in (None, []):
        raise TokenMeterError("Token Meter reports a runtime adapter failure")

    logs = fetcher(base_url, "/logs")
    sessions = logs.get("sessions")
    if not isinstance(sessions, list):
        raise TokenMeterError("Token Meter session inventory is malformed")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for original in sessions:
        if not isinstance(original, dict) or original.get("client") != "codex":
            continue
        issue = _issue_for_project(original.get("project"), workspace_root)
        if issue is None or (issues is not None and issue not in issues):
            continue
        session_id = original.get("id")
        if not isinstance(session_id, str) or not session_id or len(session_id) > 240:
            raise TokenMeterError("Token Meter returned an invalid session identifier")
        details = fetcher(base_url, "/session?" + parse.urlencode({"id": session_id}))
        tools = details.get("tools")
        if not isinstance(tools, dict):
            tools = {}
        context = original.get("context")
        if not isinstance(context, dict):
            context = {}
        row = dict(original)
        row.update(
            {
                "_cache_read_tokens": _sum_model_metric(original, "cache_read_tokens"),
                "_reasoning_tokens": _sum_model_metric(original, "reasoning_tokens"),
                "_executions": _sum_model_metric(original, "executions"),
                "_context_tokens": _number(context.get("latest")),
                "_context_percent": _number(context.get("latest_pct")),
                "_tool_calls": _nonnegative_int(tools.get("total_calls")),
                "_tool_errors": _nonnegative_int(tools.get("total_errors")),
                "_tool_output_tokens": _nonnegative_int(
                    tools.get("total_output_tokens")
                ),
                "_subagent_turns": _nonnegative_int(details.get("subagent_turns")),
                "_trace_truncated": details.get("trace_truncated") is True,
            }
        )
        grouped.setdefault(issue, []).append(row)

    issue_rows = [_aggregate_issue(issue, grouped[issue]) for issue in sorted(grouped)]
    return {
        "schema_version": 1,
        "source": "splunk-token-meter-local",
        "generated_at": logs.get("generated_at"),
        "codex_sources_discovered": clients["codex"],
        "token_meter_sessions": _nonnegative_int(logs.get("total_sessions")),
        "matched_issues": len(issue_rows),
        "issues": issue_rows,
        "privacy": {
            "content_exported": False,
            "session_ids_exported": False,
            "project_paths_exported": False,
            "cost_interpretation": "API-equivalent estimates intentionally excluded",
        },
    }


def markdown_report(baseline: dict[str, Any]) -> str:
    lines = [
        "| Issue | Sessions | Tokens | Input | Cached | Output | Turns | Tool calls | Peak context |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in baseline["issues"]:
        values = [
            row["issue"],
            row["sessions"],
            row["total_tokens"],
            row["input_tokens"],
            row["cached_input_tokens"],
            row["output_tokens"],
            row["turns"],
            row["tool_calls"],
            row["peak_context_tokens"],
        ]
        lines.append(
            "| "
            + " | ".join(
                "unavailable" if value is None else str(value) for value in values
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate content-free Sanctum issue metrics from local Token Meter"
    )
    parser.add_argument("--url", default="http://127.0.0.1:8722")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--issue", action="append", default=[])
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    try:
        baseline = collect_baseline(
            args.url,
            args.workspace_root,
            set(args.issue) if args.issue else None,
        )
    except TokenMeterError as exc:
        raise SystemExit(f"REFUSED: {exc}") from exc
    if args.format == "markdown":
        print(markdown_report(baseline), end="")
    else:
        print(json.dumps(baseline, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
