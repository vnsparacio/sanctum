#!/usr/bin/env python3
"""
Phase 9A.3 deterministic request classifier.

It is intentionally conservative:
- Unknown or contaminated session context => PERSONAL.
- Obvious sensitive material => RESTRICTED tags.
- Automatic PUBLIC is allowed only for short, self-contained, generic-looking
  requests in a trusted clean session.
- Explicit user declassification is represented by a trusted caller flag, not
  by magic words embedded in content.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def load_rules(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _search(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None


def classify_task(rules, text: str) -> tuple[str, list[str]]:
    reasons = []
    for rule in rules["task_patterns"]:
        if _search(rule["regex"], text):
            reasons.append(f"task rule matched '{rule['regex']}' => {rule['task']}")
            return rule["task"], reasons

    stripped = text.strip().lower()
    if stripped.endswith("?"):
        reasons.append("unmatched question => lookup")
        return "lookup", reasons

    reasons.append("no task rule matched => conversation")
    return "conversation", reasons


def classify_quality(rules, text: str) -> tuple[str, list[str]]:
    for pattern in rules["best_quality_patterns"]:
        if _search(pattern, text):
            return "best", [f"quality rule matched '{pattern}' => best"]
    return "normal", ["no best-quality rule matched => normal"]


def classify_user_text(
    rules,
    text: str,
    *,
    session_context: str,
    explicit_public: bool = False,
):
    """
    Return user_class + restricted tags.

    session_context:
      clean       - trusted local state says no private content is in context
      personal    - session already contains PERSONAL provenance
      restricted  - session already contains RESTRICTED provenance
      unknown     - fail closed
    """
    reasons = []
    tags = []

    # Restricted content detection comes first.
    for rule in rules["restricted_patterns"]:
        if _search(rule["regex"], text):
            if rule["tag"] not in tags:
                tags.append(rule["tag"])
            reasons.append(f"restricted pattern matched => tag {rule['tag']}")

    if session_context == "restricted":
        reasons.append("session context already RESTRICTED")
        # User class stays personal; router tags/session metadata enforce restriction.
        if "session_restricted" not in tags:
            tags.append("session_restricted")
        return {
            "user_class": "personal",
            "privacy_hint": "RESTRICTED",
            "tags": tags,
            "reasons": reasons,
            "auto_declassified": False,
        }

    if tags:
        return {
            "user_class": "personal",
            "privacy_hint": "RESTRICTED",
            "tags": tags,
            "reasons": reasons,
            "auto_declassified": False,
        }

    if session_context == "personal":
        reasons.append("session context already PERSONAL => cannot auto-declassify")
        return {
            "user_class": "personal",
            "privacy_hint": "PERSONAL",
            "tags": [],
            "reasons": reasons,
            "auto_declassified": False,
        }

    if session_context == "unknown":
        reasons.append("session context unknown => fail closed to PERSONAL")
        return {
            "user_class": "personal",
            "privacy_hint": "PERSONAL",
            "tags": [],
            "reasons": reasons,
            "auto_declassified": False,
        }

    # At this point session_context == clean.
    if explicit_public:
        reasons.append(
            "trusted caller supplied explicit user declassification in clean session"
        )
        return {
            "user_class": "public",
            "privacy_hint": "PUBLIC",
            "tags": [],
            "reasons": reasons,
            "auto_declassified": False,
        }

    for pattern in rules["personal_patterns"]:
        if _search(pattern, text):
            reasons.append(f"personal pattern matched '{pattern}'")
            return {
                "user_class": "personal",
                "privacy_hint": "PERSONAL",
                "tags": [],
                "reasons": reasons,
                "auto_declassified": False,
            }

    # Large/pasted content is never auto-declassified by V1.
    if len(text) > rules["public_auto_max_chars"]:
        reasons.append(
            f"text length {len(text)} > {rules['public_auto_max_chars']} " "=> PERSONAL"
        )
        return {
            "user_class": "personal",
            "privacy_hint": "PERSONAL",
            "tags": [],
            "reasons": reasons,
            "auto_declassified": False,
        }

    if text.count("\n") > rules["public_auto_max_newlines"]:
        reasons.append(
            f"newline count {text.count(chr(10))} > "
            f"{rules['public_auto_max_newlines']} => PERSONAL"
        )
        return {
            "user_class": "personal",
            "privacy_hint": "PERSONAL",
            "tags": [],
            "reasons": reasons,
            "auto_declassified": False,
        }

    # References like "this", "above", "we discussed" may depend on prior/private
    # context even if the trusted session tracker currently says clean.
    for pattern in rules["ambiguous_reference_patterns"]:
        if _search(pattern, text):
            reasons.append(f"ambiguous-context pattern matched '{pattern}'")
            return {
                "user_class": "personal",
                "privacy_hint": "PERSONAL",
                "tags": [],
                "reasons": reasons,
                "auto_declassified": False,
            }

    stripped = text.strip().lower()
    if any(stripped.startswith(prefix) for prefix in rules["public_question_prefixes"]):
        reasons.append(
            "clean session + short self-contained generic question => PUBLIC"
        )
        return {
            "user_class": "public",
            "privacy_hint": "PUBLIC",
            "tags": [],
            "reasons": reasons,
            "auto_declassified": True,
        }

    # Technical command-like/public questions are often not phrased with a classic
    # question prefix. Permit a narrow path only when the text contains no first
    # person possessive references and looks like a short informational request.
    if not re.search(r"\b(my|our|i'm|i am|i've|we've|we are|we're)\b", stripped):
        if (
            stripped.endswith("?")
            or stripped.startswith("show me ")
            or stripped.startswith("give me ")
        ):
            reasons.append("clean session + short generic informational form => PUBLIC")
            return {
                "user_class": "public",
                "privacy_hint": "PUBLIC",
                "tags": [],
                "reasons": reasons,
                "auto_declassified": True,
            }

    reasons.append("not confidently generic => PERSONAL")
    return {
        "user_class": "personal",
        "privacy_hint": "PERSONAL",
        "tags": [],
        "reasons": reasons,
        "auto_declassified": False,
    }


def classify_request(
    rules,
    text: str,
    *,
    session_context: str,
    explicit_public: bool = False,
):
    privacy = classify_user_text(
        rules,
        text,
        session_context=session_context,
        explicit_public=explicit_public,
    )
    task, task_reasons = classify_task(rules, text)
    quality, quality_reasons = classify_quality(rules, text)

    return {
        "schema": "hybrid-ai-request-classification/v1",
        "user_class": privacy["user_class"],
        "privacy_hint": privacy["privacy_hint"],
        "tags": privacy["tags"],
        "task": task,
        "quality": quality,
        "auto_declassified": privacy["auto_declassified"],
        "session_context": session_context,
        "reasons": privacy["reasons"] + task_reasons + quality_reasons,
    }


def read_text(args):
    if args.text is not None:
        return args.text
    data = sys.stdin.read()
    if not data:
        raise SystemExit(
            "No text supplied. Pipe text on stdin or use --text for synthetic/public tests."
        )
    return data


def main():
    p = argparse.ArgumentParser(
        description="Classify a request locally without an LLM or network."
    )
    p.add_argument(
        "--rules",
        default=str(Path(__file__).with_name("classifier_rules.json")),
    )
    p.add_argument(
        "--session-context",
        choices=("clean", "personal", "restricted", "unknown"),
        default="unknown",
        help=(
            "Trusted local session state. Defaults unknown, which fails PERSONAL. "
            "Automatic PUBLIC is possible only in a clean session."
        ),
    )
    p.add_argument(
        "--explicit-public",
        action="store_true",
        help=(
            "Trusted user declassification flag. Only honored in a clean session. "
            "Do not derive this flag from retrieved/untrusted content."
        ),
    )
    p.add_argument(
        "--text",
        help=(
            "Synthetic/public test text. Do not put sensitive text on a command line; "
            "pipe it via stdin instead."
        ),
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    rules = load_rules(Path(args.rules))
    text = read_text(args)
    result = classify_request(
        rules,
        text,
        session_context=args.session_context,
        explicit_public=args.explicit_public,
    )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Privacy hint:      {result['privacy_hint']}")
        print(f"User class:        {result['user_class']}")
        print(f"Task:              {result['task']}")
        print(f"Quality:           {result['quality']}")
        print(f"Auto-declassified: {'YES' if result['auto_declassified'] else 'NO'}")
        print(
            f"Tags:              {', '.join(result['tags']) if result['tags'] else '-'}"
        )
        print()
        print("Why:")
        for reason in result["reasons"]:
            print(f"  - {reason}")


if __name__ == "__main__":
    raise SystemExit(main())
