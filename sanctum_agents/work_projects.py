"""Reviewed, path-free project profiles for host-owned Work Mode orchestration."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


class ProjectProfileError(ValueError):
    """A project profile document or owner-selected project is unsafe."""


SCHEMA = "sanctum-work-mode-project-profiles/v1"
VALIDATION_OPERATIONS = frozenset({"build", "lint", "test"})

_PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{0,63}")
_REPOSITORY = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})/[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,99})"
)
_PRIVATE_REF = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")
_PROFILE_FIELDS = {
    "project_id",
    "repository",
    "base_branch",
    "validation_operations",
    "private_config_refs",
}
_PRIVATE_REF_FIELDS = {"repository", "validation"}
_CREDENTIAL_NAMES = {
    "access_key",
    "api_key",
    "authorization",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}
_CREDENTIAL_NAMES_COMPACT = {name.replace("_", "") for name in _CREDENTIAL_NAMES}


@dataclass(frozen=True)
class PrivateConfigRefs:
    repository: str
    validation: str


@dataclass(frozen=True)
class ProjectProfile:
    project_id: str
    repository: str
    base_branch: str
    validation_operations: tuple[str, ...]
    private_config_refs: PrivateConfigRefs


@dataclass(frozen=True)
class ProjectProfiles:
    profiles: Mapping[str, ProjectProfile]

    def select(self, project_id: str) -> ProjectProfile:
        """Select only the exact project ID supplied by the owner/orchestrator."""
        if type(project_id) is not str or not _PROJECT_ID.fullmatch(project_id):
            raise ProjectProfileError("unsafe Work Mode project selection")
        try:
            return self.profiles[project_id]
        except KeyError as exc:
            raise ProjectProfileError("unknown Work Mode project") from exc


def _contains_credential_field(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            if (
                normalized in _CREDENTIAL_NAMES
                or normalized.replace("_", "") in _CREDENTIAL_NAMES_COMPACT
                or _contains_credential_field(item)
            ):
                return True
    elif isinstance(value, list):
        return any(_contains_credential_field(item) for item in value)
    return False


def _safe_branch(value: Any) -> bool:
    if type(value) is not str or not _BRANCH.fullmatch(value):
        return False
    if value.startswith(("-", ".", "/", "refs/")) or value.endswith(
        ("/", ".", ".lock")
    ):
        return False
    return not any(
        unsafe in value for unsafe in ("..", "//", "@{", "\\", "~", "^", ":")
    )


def _parse_profile(value: Any) -> ProjectProfile:
    if not isinstance(value, dict) or set(value) != _PROFILE_FIELDS:
        raise ProjectProfileError("invalid Work Mode project profile fields")
    project_id = value["project_id"]
    repository = value["repository"]
    base_branch = value["base_branch"]
    operations = value["validation_operations"]
    refs = value["private_config_refs"]
    if type(project_id) is not str or not _PROJECT_ID.fullmatch(project_id):
        raise ProjectProfileError("invalid Work Mode project ID")
    if type(repository) is not str or not _REPOSITORY.fullmatch(repository):
        raise ProjectProfileError("invalid Work Mode repository identity")
    if not _safe_branch(base_branch):
        raise ProjectProfileError("unsafe Work Mode base branch")
    if (
        not isinstance(operations, list)
        or not operations
        or len(operations) != len(set(operations))
        or any(type(item) is not str for item in operations)
        or not set(operations) <= VALIDATION_OPERATIONS
    ):
        raise ProjectProfileError("unreviewed Work Mode validation operation")
    if not isinstance(refs, dict) or set(refs) != _PRIVATE_REF_FIELDS:
        raise ProjectProfileError("invalid Work Mode private configuration references")
    if any(
        type(refs[name]) is not str or not _PRIVATE_REF.fullmatch(refs[name])
        for name in _PRIVATE_REF_FIELDS
    ):
        raise ProjectProfileError("invalid Work Mode private configuration reference")
    return ProjectProfile(
        project_id=project_id,
        repository=repository,
        base_branch=base_branch,
        validation_operations=tuple(operations),
        private_config_refs=PrivateConfigRefs(
            repository=refs["repository"], validation=refs["validation"]
        ),
    )


def parse_project_profiles(value: Any) -> ProjectProfiles:
    """Parse a reviewed project profile document without resolving private refs."""
    if _contains_credential_field(value):
        raise ProjectProfileError("credential-bearing Work Mode profiles are forbidden")
    if not isinstance(value, dict) or set(value) != {"schema", "profiles"}:
        raise ProjectProfileError("invalid Work Mode project profile document")
    if value["schema"] != SCHEMA or not isinstance(value["profiles"], list):
        raise ProjectProfileError("unsupported Work Mode project profile schema")
    parsed: dict[str, ProjectProfile] = {}
    for item in value["profiles"]:
        profile = _parse_profile(item)
        if profile.project_id in parsed:
            raise ProjectProfileError("duplicate Work Mode project ID")
        parsed[profile.project_id] = profile
    if not parsed:
        raise ProjectProfileError("at least one Work Mode project profile is required")
    return ProjectProfiles(MappingProxyType(parsed))


def load_project_profiles(path: str | Path) -> ProjectProfiles:
    """Load profiles from a host-selected file; the document cannot select itself."""
    source = Path(path)
    try:
        value = json.loads(source.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectProfileError("cannot load Work Mode project profiles") from exc
    return parse_project_profiles(value)
