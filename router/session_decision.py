#!/usr/bin/env python3
"""
Session-aware request decision.

Flow:
  1. Read trusted local session privacy state.
  2. Classify current user request deterministically.
  3. Combine trusted tool provenance.
  4. Route deterministically.
  5. Persist the resulting privacy level back to session metadata.

No network I/O. No model execution. No tool authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from request_classifier import load_rules, classify_request
from router import load_policy
from provenance import load_registry, build_envelope, route_envelope
from session_state import SessionStore


def state_to_classifier_context(state: str) -> str:
    return {
        "CLEAN": "clean",
        "PERSONAL": "personal",
        "RESTRICTED": "restricted",
        "UNKNOWN": "unknown",
    }[state]


def decision_privacy_to_session_state(privacy: str) -> str:
    return {
        "PUBLIC": "CLEAN",
        "PERSONAL": "PERSONAL",
        "RESTRICTED": "RESTRICTED",
    }[privacy]


def read_text(args) -> str:
    if args.text is not None:
        return args.text
    data = sys.stdin.read()
    if not data:
        raise SystemExit(
            "No request text. Pipe private text via stdin; use --text only for harmless tests."
        )
    return data


def main() -> int:
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(
        description="Session-aware deterministic classify + route + privacy-state update."
    )
    p.add_argument("session_id")
    p.add_argument("--state-dir", default=str(here / "state"))
    p.add_argument("--policy", default=str(here / "policy.json"))
    p.add_argument("--registry", default=str(here / "source_registry.json"))
    p.add_argument("--rules", default=str(here / "classifier_rules.json"))

    p.add_argument("--tool", action="append", default=[])
    p.add_argument(
        "--browser-visibility",
        choices=("private", "public"),
        default="private",
    )
    p.add_argument("--explicit-public", action="store_true")
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--context-tokens", type=int, default=0)
    p.add_argument(
        "--aws-state",
        choices=("running", "stopped", "unavailable"),
        default="stopped",
    )
    p.add_argument(
        "--hosted-state",
        choices=("available", "unavailable"),
        default="available",
    )
    p.add_argument("--text")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    text = read_text(args)

    store = SessionStore(Path(args.state_dir))
    before = store.get(args.session_id)
    session_context = state_to_classifier_context(before["privacy"])

    rules = load_rules(Path(args.rules))
    classification = classify_request(
        rules,
        text,
        session_context=session_context,
        explicit_public=args.explicit_public,
    )

    policy = load_policy(Path(args.policy))
    registry = load_registry(Path(args.registry))

    tags = list(dict.fromkeys(args.tag + classification["tags"]))
    # session_restricted is a classifier-internal marker, not a router restricted tag.
    # The source/user class and persisted session state already enforce restriction.
    tags = [t for t in tags if t != "session_restricted"]

    envelope = build_envelope(
        registry,
        tools=args.tool,
        user_class=classification["user_class"],
        browser_visibility=args.browser_visibility,
        task=classification["task"],
        context_tokens=args.context_tokens,
        tags=tags,
        quality=classification["quality"],
        aws_state=args.aws_state,
        hosted_state=args.hosted_state,
    )
    combined = route_envelope(policy, envelope)
    decision = combined["decision"]

    # If the session was already RESTRICTED, enforce it at route level even if no
    # current restricted tag is present. A RESTRICTED session must remain restricted.
    if before["privacy"] == "RESTRICTED" and decision["privacy"] != "RESTRICTED":
        # Re-route with an existing deterministic restricted tag.
        envelope = build_envelope(
            registry,
            tools=args.tool,
            user_class="personal",
            browser_visibility=args.browser_visibility,
            task=classification["task"],
            context_tokens=args.context_tokens,
            tags=list(dict.fromkeys(tags + ["work_confidential"])),
            quality=classification["quality"],
            aws_state=args.aws_state,
            hosted_state=args.hosted_state,
        )
        combined = route_envelope(policy, envelope)
        decision = combined["decision"]

    # Unknown sessions fail closed, but cannot be silently created. This preserves
    # lifecycle integrity: adapter must explicitly START a new session as CLEAN.
    after = before
    if before["privacy"] != "UNKNOWN":
        observed_state = decision_privacy_to_session_state(decision["privacy"])
        after = store.observe(
            args.session_id,
            observed_state,
            reason=f"routing decision => {decision['privacy']}",
        )

    result = {
        "session_before": before,
        "classification": classification,
        "envelope": combined["envelope"],
        "decision": decision,
        "session_after": after,
        "state_updated": before["privacy"] != "UNKNOWN",
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    print(f"Session before:   {before['privacy']}")
    print(f"Privacy decision: {decision['privacy']}")
    print(f"Task:             {classification['task']}")
    print(f"Difficulty:       {decision['difficulty']}")
    print(f"Preferred route:  {decision['preferred_route']}")
    print(f"Action:           {decision['action']}")
    print(f"Reasoning tier:   {decision['reasoning_tier']}")
    print(f"Hosted egress:    {'ALLOWED' if decision['hosted_egress_allowed'] else 'BLOCKED'}")
    print(f"Authority:        {decision['authority']}")
    print(f"Session after:    {after['privacy']}")
    print(f"State updated:    {'YES' if result['state_updated'] else 'NO — UNKNOWN session must be started'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
