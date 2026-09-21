"""Implementation lifecycle contracts independent of Symphony internals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .authority import implementation_eligible


class LifecycleError(ValueError):
    """An implementation lifecycle invariant was not satisfied."""


def issue_branch(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier.strip():
        raise LifecycleError("issue identifier must be non-empty")
    slug = re.sub(r"[^a-z0-9]+", "-", identifier.strip().lower()).strip("-")
    if not slug or len(slug) > 80:
        raise LifecycleError("issue identifier cannot form a safe branch")
    return f"symphony/{slug}"


def validation_profile(changed_files: list[str]) -> str:
    if not changed_files:
        raise LifecycleError("validation profile requires changed files")
    normalized = [Path(item) for item in changed_files]
    architecture_markers = {
        "AGENTS.md",
        "WORKFLOW.md",
        "SECURITY.md",
        "config/agents.json",
        "sanctum_agents/authority.py",
        "sanctum_agents/symphony_supervisor.py",
    }
    if any(
        str(item) in architecture_markers or "security" in str(item).lower()
        for item in normalized
    ):
        return "architecture-security"
    docs_config = {".md", ".json", ".yaml", ".yml", ".toml"}
    if all(item.suffix.lower() in docs_config for item in normalized):
        return "docs-config"
    return "normal-code"


@dataclass(frozen=True)
class PullRequestHandoff:
    base_branch: str
    head_branch: str
    merged: bool
    issue_state: str


def worker_class_eligible(labels: list[str], worker_class: str) -> bool:
    selected = {label for label in labels if label in {"agent-standard", "agent-deep"}}
    expected = {
        "standard": "agent-standard",
        "deep": "agent-deep",
    }.get(worker_class)
    return expected is not None and selected == {expected}


def validate_dispatch(
    state: str, labels: list[str], worker_class: str = "standard"
) -> None:
    if not implementation_eligible(state, labels):
        raise LifecycleError("implementation requires Ready for Agent + symphony")
    if not worker_class_eligible(labels, worker_class):
        raise LifecycleError(
            "implementation requires exactly one matching agent-standard/agent-deep label"
        )


def validate_handoff(value: PullRequestHandoff, identifier: str) -> None:
    if value.base_branch != "v1.3-dev":
        raise LifecycleError("pull request must target v1.3-dev")
    if value.head_branch != issue_branch(identifier):
        raise LifecycleError(
            "pull request branch is not deterministic and issue-scoped"
        )
    if value.merged:
        raise LifecycleError("implementation worker may not merge")
    if value.issue_state != "Human Review":
        raise LifecycleError("implementation must stop in Human Review")
