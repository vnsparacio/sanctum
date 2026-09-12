#!/usr/bin/env python3
"""
Hybrid AI Phase 9A deterministic router.

Security principle:
    Reasoning is replaceable. Authority stays on the Mac.

This component decides WHERE reasoning may occur. It grants no tool authority.
It does not inspect or transmit request bodies and does not contact any network.
"""

import argparse
import json
import sys
from pathlib import Path

PRIVACY_RANK = {"PUBLIC": 0, "PERSONAL": 1, "RESTRICTED": 2}
DIFFICULTY_RANK = {"EASY": 0, "HARD": 1, "VERY_HARD": 2}


def load_policy(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def max_level(values, rank, default):
    if not values:
        return default
    return max(values, key=lambda x: rank[x])


def classify_privacy(policy, sources, tags):
    reasons = []
    source_map = policy["source_privacy"]
    default = policy["default_source_privacy"]

    levels = []
    for source in sources:
        level = source_map.get(source, default)
        levels.append(level)
        if source not in source_map:
            reasons.append(
                f"source '{source}' is unknown, so it fails closed to {default}"
            )
        else:
            reasons.append(f"source '{source}' => {level}")

    restricted_tags = set(policy["restricted_tags"])
    matched_restricted = sorted(set(tags) & restricted_tags)
    if matched_restricted:
        levels.append("RESTRICTED")
        reasons.append(
            "restricted tag(s) => RESTRICTED: " + ", ".join(matched_restricted)
        )

    privacy = max_level(levels, PRIVACY_RANK, default)
    return privacy, reasons


def classify_difficulty(policy, task, context_tokens, source_count, quality):
    reasons = []
    task_map = policy["task_difficulty"]
    base = task_map.get(task, "HARD")
    difficulty = base
    reasons.append(f"task '{task}' => {base}")

    thresholds = policy["thresholds"]

    if context_tokens >= thresholds["very_hard_context_tokens"]:
        if DIFFICULTY_RANK[difficulty] < DIFFICULTY_RANK["VERY_HARD"]:
            difficulty = "VERY_HARD"
        reasons.append(
            f"context {context_tokens} >= {thresholds['very_hard_context_tokens']} => VERY_HARD"
        )
    elif context_tokens >= thresholds["hard_context_tokens"]:
        if DIFFICULTY_RANK[difficulty] < DIFFICULTY_RANK["HARD"]:
            difficulty = "HARD"
        reasons.append(
            f"context {context_tokens} >= {thresholds['hard_context_tokens']} => at least HARD"
        )

    if source_count >= thresholds["hard_source_count"]:
        if DIFFICULTY_RANK[difficulty] < DIFFICULTY_RANK["HARD"]:
            difficulty = "HARD"
        reasons.append(
            f"{source_count} sources >= {thresholds['hard_source_count']} => at least HARD"
        )

    if quality == "best":
        difficulty = "VERY_HARD"
        reasons.append("quality=best => VERY_HARD")

    return difficulty, reasons


def decide_route(policy, privacy, difficulty, aws_state, hosted_state):
    reasons = []
    local_tier = policy["local_tier"]
    aws_tier = policy["private_aws_tier"]

    # PERSONAL/RESTRICTED content is never auto-routed to hosted remote.
    if privacy in ("PERSONAL", "RESTRICTED"):
        if difficulty == "EASY":
            return {
                "preferred_route": "LOCAL",
                "action": "USE_NOW",
                "reasoning_tier": local_tier,
                "fallback_route": None,
                "hosted_egress_allowed": False,
                "reasons": [
                    f"{privacy} + EASY => LOCAL"
                ],
            }

        if aws_state == "running":
            action = "USE_NOW"
        elif aws_state == "stopped":
            action = "ASK_TO_START_AWS"
        else:
            action = "PRIVATE_AWS_UNAVAILABLE"

        return {
            "preferred_route": "PRIVATE_AWS",
            "action": action,
            "reasoning_tier": aws_tier,
            "fallback_route": "LOCAL",
            "hosted_egress_allowed": False,
            "reasons": [
                f"{privacy} + {difficulty} => PRIVATE_AWS",
                f"AWS state is {aws_state}",
                "HOSTED_REMOTE is prohibited without explicit future declassification",
            ],
        }

    # PUBLIC content.
    if difficulty == "EASY":
        return {
            "preferred_route": "LOCAL",
            "action": "USE_NOW",
            "reasoning_tier": local_tier,
            "fallback_route": None,
            "hosted_egress_allowed": True,
            "reasons": ["PUBLIC + EASY => LOCAL"],
        }

    if hosted_state == "available":
        tier = policy["hosted_tiers"][difficulty]
        return {
            "preferred_route": "HOSTED_REMOTE",
            "action": "USE_NOW",
            "reasoning_tier": tier,
            "fallback_route": "PRIVATE_AWS" if aws_state == "running" else "LOCAL",
            "hosted_egress_allowed": True,
            "reasons": [
                f"PUBLIC + {difficulty} => HOSTED_REMOTE",
                f"hosted tier => {tier}",
            ],
        }

    # Hosted unavailable: use private AWS if possible.
    if aws_state == "running":
        action = "USE_NOW"
    elif aws_state == "stopped":
        action = "ASK_TO_START_AWS"
    else:
        action = "PRIVATE_AWS_UNAVAILABLE"

    return {
        "preferred_route": "PRIVATE_AWS",
        "action": action,
        "reasoning_tier": aws_tier,
        "fallback_route": "LOCAL",
        "hosted_egress_allowed": True,
        "reasons": [
            f"PUBLIC + {difficulty}, but hosted remote is unavailable",
            f"fall back to PRIVATE_AWS; AWS state is {aws_state}",
        ],
    }


def route_request(policy, sources, tags, task, context_tokens, quality,
                  aws_state, hosted_state):
    if not sources:
        sources = ["unknown"]

    privacy, privacy_reasons = classify_privacy(policy, sources, tags)
    difficulty, difficulty_reasons = classify_difficulty(
        policy, task, context_tokens, len(sources), quality
    )
    decision = decide_route(
        policy, privacy, difficulty, aws_state, hosted_state
    )

    return {
        "policy_version": policy["policy_version"],
        "privacy": privacy,
        "difficulty": difficulty,
        "preferred_route": decision["preferred_route"],
        "action": decision["action"],
        "reasoning_tier": decision["reasoning_tier"],
        "fallback_route": decision["fallback_route"],
        "authority": "MAC_ONLY",
        "hosted_egress_allowed": decision["hosted_egress_allowed"],
        "sources": sources,
        "tags": tags,
        "context_tokens": context_tokens,
        "quality": quality,
        "aws_state": aws_state,
        "hosted_state": hosted_state,
        "reasons": privacy_reasons + difficulty_reasons + decision["reasons"],
    }


def human_output(result):
    lines = [
        f"Privacy:         {result['privacy']}",
        f"Difficulty:      {result['difficulty']}",
        f"Preferred route: {result['preferred_route']}",
        f"Action:          {result['action']}",
        f"Reasoning tier:  {result['reasoning_tier']}",
        f"Fallback:        {result['fallback_route'] or '-'}",
        f"Authority:       {result['authority']}",
        f"Hosted egress:   {'ALLOWED' if result['hosted_egress_allowed'] else 'BLOCKED'}",
        "",
        "Why:",
    ]
    lines.extend(f"  - {reason}" for reason in result["reasons"])
    return "\n".join(lines)


def build_parser():
    p = argparse.ArgumentParser(
        description="Deterministically select LOCAL, PRIVATE_AWS, or HOSTED_REMOTE."
    )
    p.add_argument(
        "--source",
        action="append",
        default=[],
        help=(
            "Data origin; repeatable. Examples: public_web, user_public, user_input, "
            "gmail, messages, vinceai, file_steward, local_file, browser_public, "
            "browser_private, credentials, unknown."
        ),
    )
    p.add_argument(
        "--tag",
        action="append",
        default=[],
        help=(
            "Deterministic sensitivity tag; repeatable. Restricted examples: "
            "credential, secret, authentication, financial_account, "
            "customer_confidential, work_confidential, health, legal_sensitive."
        ),
    )
    p.add_argument(
        "--task",
        required=True,
        help=(
            "Task class: conversation, lookup, summarize, extract, draft, tool_select, "
            "plan, analyze, debug, compare, synthesize, research, architecture, "
            "deep_research, high_value."
        ),
    )
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
    p.add_argument("--json", action="store_true", help="Emit JSON.")
    p.add_argument(
        "--policy",
        default=str(Path(__file__).with_name("policy.json")),
        help="Policy JSON path.",
    )
    return p


def main():
    args = build_parser().parse_args()
    if args.context_tokens < 0:
        print("context tokens cannot be negative", file=sys.stderr)
        return 2

    policy = load_policy(Path(args.policy))
    result = route_request(
        policy=policy,
        sources=args.source,
        tags=args.tag,
        task=args.task,
        context_tokens=args.context_tokens,
        quality=args.quality,
        aws_state=args.aws_state,
        hosted_state=args.hosted_state,
    )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(human_output(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
