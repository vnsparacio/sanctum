#!/usr/bin/env python3
"""
Combine Phase 9A.2 trusted provenance with Phase 9A.3 request classification
and Phase 9A.1 routing.

No network I/O. No authority is granted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from provenance import build_envelope, load_registry, route_envelope
from request_classifier import classify_request, load_rules

from router import load_policy


def main():
    p = argparse.ArgumentParser(description="Classify + route a request locally.")
    here = Path(__file__).resolve().parent

    p.add_argument("--policy", default=str(here / "policy.json"))
    p.add_argument("--registry", default=str(here / "source_registry.json"))
    p.add_argument("--rules", default=str(here / "classifier_rules.json"))

    p.add_argument("--tool", action="append", default=[])
    p.add_argument(
        "--browser-visibility",
        choices=("private", "public"),
        default="private",
    )
    p.add_argument(
        "--session-context",
        choices=("clean", "personal", "restricted", "unknown"),
        default="unknown",
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

    if args.text is not None:
        text = args.text
    else:
        text = sys.stdin.read()
        if not text:
            raise SystemExit(
                "No request text. Pipe it on stdin or use --text for synthetic/public tests."
            )

    rules = load_rules(Path(args.rules))
    classification = classify_request(
        rules,
        text,
        session_context=args.session_context,
        explicit_public=args.explicit_public,
    )

    policy = load_policy(Path(args.policy))
    registry = load_registry(Path(args.registry))

    tags = list(dict.fromkeys(args.tag + classification["tags"]))

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

    result = {
        "classification": classification,
        "envelope": combined["envelope"],
        "decision": combined["decision"],
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    d = result["decision"]
    c = result["classification"]

    print(f"Privacy:         {d['privacy']}")
    print(f"Task:            {c['task']}")
    print(f"Difficulty:      {d['difficulty']}")
    print(f"Preferred route: {d['preferred_route']}")
    print(f"Action:          {d['action']}")
    print(f"Reasoning tier:  {d['reasoning_tier']}")
    print(f"Authority:       {d['authority']}")
    print(f"Hosted egress:   {'ALLOWED' if d['hosted_egress_allowed'] else 'BLOCKED'}")
    print(f"Auto-public:     {'YES' if c['auto_declassified'] else 'NO'}")
    print()
    print("Classifier:")
    for reason in c["reasons"]:
        print(f"  - {reason}")
    print()
    print("Router:")
    for reason in d["reasons"]:
        print(f"  - {reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
