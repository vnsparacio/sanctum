"""Project-bound dispatch for Work Mode validation operations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from sanctum_agents.work_projects import ProjectProfiles
from sanctum_agents.work_workspaces import TaskWorkspace


class WorkValidationError(RuntimeError):
    """A project validation request or backend result failed closed."""


RECEIPT_SCHEMA = "sanctum-work-mode-validation-receipt/v1"
ValidationBackend = Callable[[str, Path, str], Mapping[str, Any]]


@dataclass(frozen=True)
class ValidationReceipt:
    project_id: str
    profile: str
    command: str
    result: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": RECEIPT_SCHEMA,
            "project_id": self.project_id,
            "profile": self.profile,
            "command": self.command,
            "result": dict(self.result),
        }


class WorkValidationRunner:
    """Resolve project validation through reviewed profiles and a bounded backend."""

    def __init__(self, profiles: ProjectProfiles, backend: ValidationBackend) -> None:
        self.profiles = profiles
        self.backend = backend

    def run(self, workspace: TaskWorkspace, operation: Any) -> ValidationReceipt:
        profile = self.profiles.select(workspace.project_id)
        if (
            workspace.repository != profile.repository
            or workspace.base_branch != profile.base_branch
        ):
            raise WorkValidationError("task workspace does not match project profile")
        if type(operation) is not str or operation not in profile.validation_operations:
            raise WorkValidationError("validation operation is not allowed for project")

        validation_profile = profile.private_config_refs.validation
        try:
            result = self.backend(validation_profile, workspace.root, operation)
        except WorkValidationError:
            raise
        except Exception as exc:
            raise WorkValidationError("validation backend unavailable") from exc
        if (
            not isinstance(result, Mapping)
            or type(result.get("ok")) is not bool
            or type(result.get("code")) is not str
            or type(result.get("executionState")) is not str
        ):
            raise WorkValidationError("validation backend returned an invalid result")

        return ValidationReceipt(
            project_id=profile.project_id,
            profile=validation_profile,
            command=operation,
            result=MappingProxyType(dict(result)),
        )
