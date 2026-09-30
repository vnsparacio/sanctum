"""Require every pull request to declare and satisfy documentation impact."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTION = re.compile(
    r"^## Documentation impact\s*$\n(.*?)(?=^##\s|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
PLACEHOLDER = re.compile(
    r"^(?:n/?a|none|not applicable|todo|tbd|why|reason|explain)(?:\W|$)",
    re.IGNORECASE,
)
BEHAVIOR_PREFIXES = (
    "gate/",
    "plugins/",
    "reliability/",
    "router/",
    "mcp-integration/",
    "sanctum_agents/",
    "scripts/",
    "config/",
    "host/",
    ".github/workflows/",
    ".github/rulesets/",
)
BEHAVIOR_FILES = {
    ".env.example",
    "AGENTS.md",
    "Makefile",
    "compose.yaml",
    "package.json",
    "package-lock.json",
    "requirements-dev.txt",
}


def is_documentation(path: str) -> bool:
    return path == "README.md" or path.startswith("docs/")


def is_behavior_or_configuration(path: str) -> bool:
    return (
        path in BEHAVIOR_FILES
        or path.startswith(BEHAVIOR_PREFIXES)
        or path.startswith("WORKFLOW")
        or path.startswith("requirements-")
    )


def documentation_section(body: str) -> tuple[str, str] | None:
    matches = SECTION.findall(body or "")
    if len(matches) != 1:
        return None
    content = re.sub(r"<!--.*?-->", "", matches[0], flags=re.DOTALL).strip()
    match = re.fullmatch(r"(Updated|None):\s*(.+)", content, re.DOTALL)
    if match is None:
        return None
    kind, explanation = match.groups()
    explanation = " ".join(explanation.split())
    return kind.lower(), explanation


def check_documentation_impact(changed: list[str], body: str) -> list[str]:
    errors: list[str] = []
    section = documentation_section(body)
    if section is None:
        return [
            "PR body must contain exactly one '## Documentation impact' section "
            "with 'Updated: <summary>' or 'None: <justification>'."
        ]

    kind, explanation = section
    if len(explanation) < 12 or PLACEHOLDER.match(explanation):
        errors.append(
            "Documentation impact explanation must be specific and justified."
        )

    documentation_changed = any(is_documentation(path) for path in changed)
    behavior_changed = any(is_behavior_or_configuration(path) for path in changed)
    if kind == "updated" and not documentation_changed:
        errors.append("'Updated:' requires a README.md or docs/ change in this PR.")
    if behavior_changed and kind != "none" and not documentation_changed:
        errors.append(
            "Behavior/configuration changed without documentation; add docs or use "
            "'None: <justification>'."
        )
    return errors


def changed_files(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACDMRTUXB", base, head],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-file", type=Path)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--body-file", type=Path)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    if args.event_file:
        event = json.loads(args.event_file.read_text())
        request = event.get("pull_request") or {}
        base = request.get("base", {}).get("sha")
        head = request.get("head", {}).get("sha")
        body = request.get("body") or ""
    else:
        base = args.base
        head = args.head
        body = args.body_file.read_text() if args.body_file else ""
    if not base or not head:
        raise SystemExit(
            "Documentation impact check requires pull-request base and head SHAs."
        )

    changed = changed_files(base, head)
    errors = check_documentation_impact(changed, body)
    if errors:
        for error in errors:
            print("ERROR: " + error)
        raise SystemExit(1)
    print(
        "Documentation impact declaration accepted for "
        f"{len(changed)} changed file(s)."
    )


if __name__ == "__main__":
    main()
