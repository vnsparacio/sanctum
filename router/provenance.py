#!/usr/bin/env python3
"""
Phase 9A.2 trusted provenance helper.

This module converts trusted local metadata (tool names + explicit local user-input
classification) into a routing envelope. It never reads request/tool content and
never performs network I/O.

Important:
- Tool provenance is deterministic.
- Unknown tools fail closed to source=unknown.
- Browser defaults PRIVATE unless a trusted caller explicitly says the browser
  context is public.
- User text defaults PERSONAL unless a trusted local declassification step marks it
  public. That declassification mechanism is intentionally NOT implemented here.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from router import load_policy, route_request


def load_registry(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def tool_to_source(registry, tool_name: str, browser_visibility: str):
    if tool_name == "browser":
        if browser_visibility == "public":
            return registry["browser_public_source"], "explicit-public-browser-context"
        return registry["browser_default_source"], "browser-fails-private"

    tool_sources = registry["tool_sources"]
    if tool_name in tool_sources:
        return tool_sources[tool_name], "registered-tool"

    return registry["unknown_tool_source"], "unknown-tool-fails-closed"


def build_envelope(
    registry,
    *,
    tools,
    user_class,
    browser_visibility,
    task,
    context_tokens,
    tags,
    quality,
    aws_state,
    hosted_state,
    request_id=None,
):
    if request_id is None:
        request_id = str(uuid.uuid4())

    provenance = []
    sources = []

    if user_class == "public":
        sources.append("user_public")
        provenance.append(
            {
                "kind": "user_input",
                "source": "user_public",
                "trust": "trusted-local-classification",
                "note": "explicitly declassified public by trusted local caller",
            }
        )
    elif user_class == "personal":
        sources.append("user_input")
        provenance.append(
            {
                "kind": "user_input",
                "source": "user_input",
                "trust": "default-fail-closed",
                "note": "user input defaults PERSONAL",
            }
        )
    elif user_class != "none":
        raise ValueError(f"unsupported user_class: {user_class}")

    for tool in tools:
        source, mapping_reason = tool_to_source(registry, tool, browser_visibility)
        sources.append(source)
        provenance.append(
            {
                "kind": "tool_result",
                "tool": tool,
                "source": source,
                "trust": "local-tool-registry",
                "mapping_reason": mapping_reason,
            }
        )

    # If absolutely no metadata is present, router must still fail closed.
    if not sources:
        sources = ["unknown"]
        provenance.append(
            {
                "kind": "implicit",
                "source": "unknown",
                "trust": "fail-closed",
                "note": "no user/tool provenance supplied",
            }
        )

    # De-duplicate route inputs while preserving first-seen order.
    unique_sources = list(dict.fromkeys(sources))

    return {
        "schema": "hybrid-ai-routing-envelope/v1",
        "request_id": request_id,
        "sources": unique_sources,
        "provenance": provenance,
        "task": task,
        "context_tokens": context_tokens,
        "tags": list(dict.fromkeys(tags)),
        "quality": quality,
        "aws_state": aws_state,
        "hosted_state": hosted_state,
        "contains_content": False,
    }


def route_envelope(policy, envelope):
    result = route_request(
        policy=policy,
        sources=envelope["sources"],
        tags=envelope["tags"],
        task=envelope["task"],
        context_tokens=envelope["context_tokens"],
        quality=envelope["quality"],
        aws_state=envelope["aws_state"],
        hosted_state=envelope["hosted_state"],
    )

    return {
        "envelope": envelope,
        "decision": result,
    }


def human_output(combined):
    env = combined["envelope"]
    d = combined["decision"]

    lines = [
        f"Privacy:         {d['privacy']}",
        f"Difficulty:      {d['difficulty']}",
        f"Preferred route: {d['preferred_route']}",
        f"Action:          {d['action']}",
        f"Reasoning tier:  {d['reasoning_tier']}",
        f"Fallback:        {d['fallback_route'] or '-'}",
        f"Authority:       {d['authority']}",
        f"Hosted egress:   {'ALLOWED' if d['hosted_egress_allowed'] else 'BLOCKED'}",
        "",
        "Trusted provenance:",
    ]

    for p in env["provenance"]:
        if p["kind"] == "tool_result":
            lines.append(
                f"  - tool {p['tool']} => {p['source']} " f"({p['mapping_reason']})"
            )
        else:
            lines.append(f"  - {p['kind']} => {p['source']}")

    lines.extend(["", "Why:"])
    lines.extend(f"  - {r}" for r in d["reasons"])
    return "\n".join(lines)


def build_parser():
    p = argparse.ArgumentParser(
        description=(
            "Route a request using trusted local tool provenance. "
            "No request/tool content is read or transmitted."
        )
    )
    p.add_argument(
        "--tool",
        action="append",
        default=[],
        help="OpenClaw tool that produced content; repeatable.",
    )
    p.add_argument(
        "--user-class",
        choices=("personal", "public", "none"),
        default="personal",
        help=(
            "Classification of the user's own text. Defaults personal. "
            "'public' must eventually come only from a trusted local "
            "declassification step."
        ),
    )
    p.add_argument(
        "--browser-visibility",
        choices=("private", "public"),
        default="private",
        help="Browser provenance; defaults private/fail-closed.",
    )
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--task", required=True)
    p.add_argument("--context-tokens", type=int, default=0)
    p.add_argument("--quality", choices=("normal", "best"), default="normal")
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
    p.add_argument("--request-id")
    p.add_argument("--json", action="store_true")
    p.add_argument("--envelope-only", action="store_true")
    p.add_argument(
        "--policy",
        default=str(Path(__file__).with_name("policy.json")),
    )
    p.add_argument(
        "--registry",
        default=str(Path(__file__).with_name("source_registry.json")),
    )
    return p


def main():
    args = build_parser().parse_args()

    if args.context_tokens < 0:
        print("context tokens cannot be negative", file=sys.stderr)
        return 2

    policy = load_policy(Path(args.policy))
    registry = load_registry(Path(args.registry))

    envelope = build_envelope(
        registry,
        tools=args.tool,
        user_class=args.user_class,
        browser_visibility=args.browser_visibility,
        task=args.task,
        context_tokens=args.context_tokens,
        tags=args.tag,
        quality=args.quality,
        aws_state=args.aws_state,
        hosted_state=args.hosted_state,
        request_id=args.request_id,
    )

    if args.envelope_only:
        print(json.dumps(envelope, indent=2, sort_keys=True))
        return 0

    combined = route_envelope(policy, envelope)
    if args.json:
        print(json.dumps(combined, indent=2, sort_keys=True))
    else:
        print(human_output(combined))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
