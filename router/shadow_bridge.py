#!/usr/bin/env python3
"""
Phase 9A.5 shadow observer bridge.

Consumes one local metadata/event envelope from stdin. For route_decision only, the
last actual user message is supplied transiently at agent_end to the existing deterministic
request classifier. Raw prompt text is never written to disk by this module.

Persistent shadow data contains only:
- hashed OpenClaw session/run/call correlation ids
- privacy/task/difficulty/route/tier labels
- tool names and deterministic provenance class
- provider/model/timing/outcome metadata
- session privacy state transitions
- boundary-alert booleans

No prompt, history, assistant output, tool params, tool result, Gmail body, Messages
text, file content, web content, or credential value is persisted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from request_classifier import load_rules, classify_request
from router import load_policy
from provenance import load_registry, build_envelope, route_envelope, tool_to_source
from session_state import SessionStore
from session_decision import (
    state_to_classifier_context,
    decision_privacy_to_session_state,
)

DEFAULT_STATE_DIR = HERE / "state"
DEFAULT_SHADOW_DIR = HERE / "shadow"
DEFAULT_LOG = DEFAULT_SHADOW_DIR / "shadow-events.jsonl"

SAFE_EVENT_KEYS = {
    "schema", "ts", "event", "session_id", "run_hash", "call_hash",
    "resumed", "reason", "provider", "model", "api", "transport",
    "duration_ms", "outcome", "success",
    "session_before", "session_after",
    "privacy_hint", "task", "quality", "auto_declassified", "tags",
    "privacy", "difficulty", "preferred_route", "action",
    "reasoning_tier", "hosted_egress_allowed", "authority",
    "tool_name", "source", "tool_privacy", "mapping_reason",
    "prior_shadow_route", "prior_shadow_tier", "boundary_alert",
    "error_code",
}


def ensure_dirs(shadow_dir: Path) -> None:
    shadow_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(shadow_dir, 0o700)


def append_event(log_path: Path, event: dict[str, Any]) -> None:
    ensure_dirs(log_path.parent)
    unsafe = set(event) - SAFE_EVENT_KEYS
    if unsafe:
        raise RuntimeError(f"unsafe shadow log key(s): {sorted(unsafe)}")

    line = json.dumps(event, sort_keys=True, separators=(",", ":"))
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
    finally:
        try:
            os.chmod(log_path, 0o600)
        except FileNotFoundError:
            pass


def load_recent(log_path: Path, limit: int = 2000) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def find_prior_route(log_path: Path, run_hash: str | None) -> tuple[str | None, str | None]:
    if not run_hash:
        return None, None
    for e in reversed(load_recent(log_path)):
        if e.get("event") == "model_input" and e.get("run_hash") == run_hash:
            return e.get("preferred_route"), e.get("reasoning_tier")
    return None, None


def ensure_session(
    store: SessionStore,
    session_id: str,
    *,
    resumed: bool,
    missing_start_is_personal: bool = False,
) -> dict[str, Any]:
    rec = store.get(session_id)
    if rec["privacy"] != "UNKNOWN":
        return rec

    rec = store.start(session_id)
    if resumed or missing_start_is_personal:
        why = (
            "shadow attached to resumed OpenClaw session"
            if resumed
            else "shadow missing trusted session_start; fail closed"
        )
        rec = store.observe(session_id, "PERSONAL", reason=why)
    return rec


def find_turn_start(
    log_path: Path,
    run_hash: str | None,
) -> dict[str, Any] | None:
    if not run_hash:
        return None
    for e in reversed(load_recent(log_path)):
        if e.get("event") == "turn_start" and e.get("run_hash") == run_hash:
            return e
    return None


def observe_turn_start(payload: dict[str, Any], log_path: Path) -> dict[str, Any]:
    session_id = payload["session_id"]
    run_hash = payload.get("run_hash")

    prior = find_turn_start(log_path, run_hash)
    if prior is not None:
        return {
            "ok": True,
            "session_before": prior.get("session_before"),
            "duplicate": True,
        }

    store = SessionStore(Path(payload.get("state_dir") or DEFAULT_STATE_DIR))
    before = ensure_session(
        store,
        session_id,
        resumed=False,
        missing_start_is_personal=True,
    )

    append_event(log_path, {
        "schema": "hybrid-ai-shadow-event/v1",
        "ts": payload.get("ts"),
        "event": "turn_start",
        "session_id": session_id,
        "run_hash": run_hash,
        "session_before": before["privacy"],
    })
    return {
        "ok": True,
        "session_before": before["privacy"],
        "duplicate": False,
    }


def run_tools_for_privacy(
    log_path: Path,
    run_hash: str | None,
) -> list[dict[str, Any]]:
    if not run_hash:
        return []
    return [
        e for e in load_recent(log_path)
        if e.get("event") == "tool_provenance" and e.get("run_hash") == run_hash
    ]


def route_user_turn(payload: dict[str, Any], log_path: Path) -> dict[str, Any]:
    session_id = payload["session_id"]
    run_hash = payload.get("run_hash")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("route_decision requires nonempty string prompt")

    store = SessionStore(Path(payload.get("state_dir") or DEFAULT_STATE_DIR))
    current = ensure_session(
        store,
        session_id,
        resumed=False,
        missing_start_is_personal=True,
    )

    start = find_turn_start(log_path, run_hash)
    start_privacy = (
        start.get("session_before")
        if start and start.get("session_before") in ("CLEAN", "PERSONAL", "RESTRICTED")
        else current["privacy"]
    )

    rules = load_rules(HERE / "classifier_rules.json")
    policy = load_policy(HERE / "policy.json")
    registry = load_registry(HERE / "source_registry.json")

    classification = classify_request(
        rules,
        prompt,
        session_context=state_to_classifier_context(start_privacy),
        explicit_public=False,
    )

    tags = [t for t in classification["tags"] if t != "session_restricted"]

    envelope = build_envelope(
        registry,
        tools=[],
        user_class=classification["user_class"],
        browser_visibility="private",
        task=classification["task"],
        context_tokens=int(payload.get("context_tokens") or 0),
        tags=tags,
        quality=classification["quality"],
        aws_state=payload.get("aws_state", "stopped"),
        hosted_state=payload.get("hosted_state", "available"),
    )
    decision = route_envelope(policy, envelope)["decision"]

    if start_privacy == "RESTRICTED" and decision["privacy"] != "RESTRICTED":
        envelope = build_envelope(
            registry,
            tools=[],
            user_class="personal",
            browser_visibility="private",
            task=classification["task"],
            context_tokens=int(payload.get("context_tokens") or 0),
            tags=list(dict.fromkeys(tags + ["work_confidential"])),
            quality=classification["quality"],
            aws_state=payload.get("aws_state", "stopped"),
            hosted_state=payload.get("hosted_state", "available"),
        )
        decision = route_envelope(policy, envelope)["decision"]

    # Persist only upward from the session's CURRENT state. Tool provenance may
    # already have escalated the session during this run.
    after = store.observe(
        session_id,
        decision_privacy_to_session_state(decision["privacy"]),
        reason=f"shadow end-of-turn routing decision => {decision['privacy']}",
    )

    tool_events = run_tools_for_privacy(log_path, run_hash)
    private_tools = [
        e for e in tool_events
        if e.get("tool_privacy") in ("PERSONAL", "RESTRICTED")
    ]
    boundary_alert = (
        decision["preferred_route"] == "HOSTED_REMOTE"
        and len(private_tools) > 0
    )

    event = {
        "schema": "hybrid-ai-shadow-event/v1",
        "ts": payload.get("ts"),
        "event": "route_decision",
        "session_id": session_id,
        "run_hash": run_hash,
        "session_before": start_privacy,
        "session_after": after["privacy"],
        "privacy_hint": classification["privacy_hint"],
        "task": classification["task"],
        "quality": classification["quality"],
        "auto_declassified": classification["auto_declassified"],
        "tags": classification["tags"],
        "privacy": decision["privacy"],
        "difficulty": decision["difficulty"],
        "preferred_route": decision["preferred_route"],
        "action": decision["action"],
        "reasoning_tier": decision["reasoning_tier"],
        "hosted_egress_allowed": decision["hosted_egress_allowed"],
        "authority": decision["authority"],
        "boundary_alert": boundary_alert,
    }
    append_event(log_path, event)

    return {
        "ok": True,
        "decision": {
            "privacy": decision["privacy"],
            "difficulty": decision["difficulty"],
            "preferred_route": decision["preferred_route"],
            "reasoning_tier": decision["reasoning_tier"],
            "action": decision["action"],
        },
        "session_after": after["privacy"],
        "boundary_alert": boundary_alert,
    }

def observe_tool(payload: dict[str, Any], log_path: Path) -> dict[str, Any]:
    session_id = payload["session_id"]
    tool_name = str(payload.get("tool_name") or "unknown")

    store = SessionStore(Path(payload.get("state_dir") or DEFAULT_STATE_DIR))
    before = ensure_session(
        store,
        session_id,
        resumed=False,
        missing_start_is_personal=True,
    )
    policy = load_policy(HERE / "policy.json")
    registry = load_registry(HERE / "source_registry.json")

    source, mapping_reason = tool_to_source(
        registry,
        tool_name,
        payload.get("browser_visibility", "private"),
    )
    tool_privacy = policy["source_privacy"].get(
        source,
        policy["default_source_privacy"],
    )
    observed_state = decision_privacy_to_session_state(tool_privacy)
    after = store.observe(
        session_id,
        observed_state,
        reason=f"shadow tool provenance: {tool_name} => {tool_privacy}",
    )

    # The hypothetical route is intentionally computed only at agent_end from the
    # raw last user message. Mid-turn boundary alerts are therefore evaluated
    # retrospectively in route_user_turn().
    prior_route, prior_tier = None, None
    boundary_alert = False

    event = {
        "schema": "hybrid-ai-shadow-event/v1",
        "ts": payload.get("ts"),
        "event": "tool_provenance",
        "session_id": session_id,
        "run_hash": payload.get("run_hash"),
        "tool_name": tool_name,
        "source": source,
        "tool_privacy": tool_privacy,
        "mapping_reason": mapping_reason,
        "session_before": before["privacy"],
        "session_after": after["privacy"],
        "prior_shadow_route": prior_route,
        "prior_shadow_tier": prior_tier,
        "boundary_alert": boundary_alert,
    }
    append_event(log_path, event)

    return {
        "ok": True,
        "tool_privacy": tool_privacy,
        "session_after": after["privacy"],
        "boundary_alert": boundary_alert,
    }


def observe_simple(payload: dict[str, Any], log_path: Path) -> dict[str, Any]:
    event_type = payload["event_type"]
    event = {
        "schema": "hybrid-ai-shadow-event/v1",
        "ts": payload.get("ts"),
        "event": event_type,
        "session_id": payload.get("session_id"),
        "run_hash": payload.get("run_hash"),
    }

    if event_type == "gateway_start":
        # Definitive proof that this hook-only plugin loaded inside the actual
        # Gateway lifecycle. No conversation/session data is involved.
        pass

    elif event_type == "session_start":
        store = SessionStore(Path(payload.get("state_dir") or DEFAULT_STATE_DIR))
        rec = ensure_session(
            store,
            payload["session_id"],
            resumed=bool(payload.get("resumed")),
        )
        event.update({
            "resumed": bool(payload.get("resumed")),
            "session_after": rec["privacy"],
        })

    elif event_type == "session_end":
        event["reason"] = payload.get("reason")

    elif event_type == "model_call_started":
        event.update({
            "call_hash": payload.get("call_hash"),
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "api": payload.get("api"),
            "transport": payload.get("transport"),
        })

    elif event_type == "model_call_ended":
        event.update({
            "call_hash": payload.get("call_hash"),
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "duration_ms": payload.get("duration_ms"),
            "outcome": payload.get("outcome"),
        })

    elif event_type == "agent_end":
        event.update({
            "duration_ms": payload.get("duration_ms"),
            "success": payload.get("success"),
        })

    else:
        raise ValueError(f"unsupported simple event: {event_type}")

    append_event(log_path, event)
    return {"ok": True}


def print_report(log_path: Path, last: int | None) -> int:
    events = load_recent(log_path, 100000)
    if last is not None:
        events = events[-last:]

    if not events:
        print("No shadow events recorded yet.")
        print(f"Log: {log_path}")
        return 0

    inputs = [e for e in events if e.get("event") == "route_decision"]
    tools = [e for e in events if e.get("event") == "tool_provenance"]
    models = [e for e in events if e.get("event") == "model_call_started"]
    alerts = [e for e in inputs if e.get("boundary_alert") is True]

    print("Phase 9A.5 shadow report")
    print(f"Log: {log_path}")
    print(f"Events: {len(events)}")
    print(f"Route-decision observations: {len(inputs)}")
    print(f"Tool provenance observations: {len(tools)}")
    print(f"Model calls observed: {len(models)}")
    print(f"Mid-turn privacy boundary alerts: {len(alerts)}")

    if inputs:
        print()
        print("Shadow routes:")
        for key, count in Counter(e.get("preferred_route") for e in inputs).most_common():
            print(f"  {key}: {count}")

        print()
        print("Reasoning tiers:")
        for key, count in Counter(e.get("reasoning_tier") for e in inputs).most_common():
            print(f"  {key}: {count}")

        print()
        print("Privacy:")
        for key, count in Counter(e.get("privacy") for e in inputs).most_common():
            print(f"  {key}: {count}")

        print()
        print("Task classes:")
        for key, count in Counter(e.get("task") for e in inputs).most_common():
            print(f"  {key}: {count}")

    if models:
        print()
        print("Actual providers/models observed:")
        for (provider, model), count in Counter(
            (e.get("provider"), e.get("model")) for e in models
        ).most_common():
            print(f"  {provider}/{model}: {count}")

    if alerts:
        print()
        print("BOUNDARY ALERTS:")
        for e in alerts[-10:]:
            print(
                "  "
                f"run={e.get('run_hash') or '-'} "
                f"route={e.get('preferred_route')}/{e.get('reasoning_tier')} "
                "-> private tool result occurred in same run"
            )

    return 0


def handle_event(payload: dict[str, Any], log_path: Path) -> dict[str, Any]:
    event_type = payload.get("event_type")
    if event_type == "turn_start":
        return observe_turn_start(payload, log_path)
    if event_type == "route_decision":
        return route_user_turn(payload, log_path)
    if event_type == "tool_result":
        return observe_tool(payload, log_path)
    return observe_simple(payload, log_path)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--log", default=str(DEFAULT_LOG))
    p.add_argument("--report", action="store_true")
    p.add_argument("--last", type=int)
    args = p.parse_args()

    log_path = Path(args.log)

    if args.report:
        return print_report(log_path, args.last)

    try:
        payload = json.load(sys.stdin)
        result = handle_event(payload, log_path)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        # Do not serialize exception text because future exceptions could accidentally
        # include user-controlled material. The OpenClaw observer treats this as a
        # non-authoritative miss and continues normal operation.
        print(json.dumps({"ok": False, "error_code": "SHADOW_EVENT_FAILED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
