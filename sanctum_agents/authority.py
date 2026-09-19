"""Immutable role capabilities and Linear execution-gate checks."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Iterable


class AuthorityError(PermissionError):
    """A role attempted an action outside its authority."""


class Role(StrEnum):
    REPO_STEWARD = "repo_steward"
    PRODUCT_SCOUT = "product_scout"
    TRIAGE = "triage"
    IMPLEMENTATION = "implementation"
    REVIEWER = "reviewer"


class Action(StrEnum):
    READ_REPOSITORY = "read_repository"
    READ_LINEAR = "read_linear"
    PROPOSE_LINEAR = "propose_linear"
    TRIAGE_LINEAR = "triage_linear"
    MODIFY_CODE = "modify_code"
    CREATE_PR = "create_pr"
    REVIEW_PR = "review_pr"
    MERGE_PR = "merge_pr"
    AUTHORIZE_IMPLEMENTATION = "authorize_implementation"
    MOVE_DONE = "move_done"


_ALLOWED = {
    Role.REPO_STEWARD: {Action.READ_REPOSITORY, Action.READ_LINEAR, Action.PROPOSE_LINEAR},
    Role.PRODUCT_SCOUT: {Action.READ_REPOSITORY, Action.READ_LINEAR, Action.PROPOSE_LINEAR},
    Role.TRIAGE: {Action.READ_LINEAR, Action.TRIAGE_LINEAR},
    Role.IMPLEMENTATION: {
        Action.READ_REPOSITORY,
        Action.READ_LINEAR,
        Action.MODIFY_CODE,
        Action.CREATE_PR,
        Action.PROPOSE_LINEAR,
    },
    Role.REVIEWER: {Action.READ_REPOSITORY, Action.READ_LINEAR, Action.REVIEW_PR},
}


def validate_action(role: Role | str, action: Action | str) -> None:
    selected_role = Role(role)
    selected_action = Action(action)
    if selected_action not in _ALLOWED[selected_role]:
        raise AuthorityError(f"{selected_role.value} may not {selected_action.value}")


def implementation_eligible(status: str, labels: Iterable[str]) -> bool:
    normalized = {str(label).strip().lower() for label in labels}
    return status.strip().lower() == "ready for agent" and "symphony" in normalized


def validate_issue_mutation(role: Role | str, mutation: dict[str, Any]) -> None:
    selected_role = Role(role)
    if not isinstance(mutation, dict):
        raise AuthorityError("issue mutation must be an object")
    state = mutation.get("state")
    labels = mutation.get("add_labels", [])
    if state is not None and not isinstance(state, str):
        raise AuthorityError("issue mutation state must be a string")
    if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
        raise AuthorityError("issue mutation add_labels must be strings")
    normalized_labels = {label.strip().lower() for label in labels}
    if selected_role in {Role.REPO_STEWARD, Role.PRODUCT_SCOUT, Role.TRIAGE}:
        if state and state.strip().lower() == "ready for agent":
            raise AuthorityError("management agents may not authorize implementation")
        if "symphony" in normalized_labels:
            raise AuthorityError("management agents may not add the symphony label")
    if selected_role in {Role.REPO_STEWARD, Role.PRODUCT_SCOUT}:
        if state and state.strip().lower() != "triage":
            raise AuthorityError("finding agents may write only to Triage")
    if selected_role is Role.TRIAGE and state:
        permitted = {"triage", "backlog", "watch", "canceled", "cancelled", "duplicate"}
        if state.strip().lower() not in permitted:
            raise AuthorityError("triage may move work only within management queues")
    if selected_role is Role.IMPLEMENTATION:
        if state and state.strip().lower() not in {"in progress", "human review", "rework"}:
            raise AuthorityError("implementation may move work only within its handoff lifecycle")
    if selected_role is Role.REVIEWER and (state is not None or labels):
        raise AuthorityError("reviewer mutations are disabled by default")
    if state and state.strip().lower() == "done":
        validate_action(selected_role, Action.MOVE_DONE)


def assert_repository_unchanged(before: str, after: str, role: Role | str) -> None:
    selected_role = Role(role)
    if selected_role in {Role.REPO_STEWARD, Role.PRODUCT_SCOUT, Role.TRIAGE, Role.REVIEWER} and before != after:
        raise AuthorityError(f"{selected_role.value} changed repository state")
