"""Task-scoped OCI command execution with no model-visible host shell."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

from sanctum_agents.work_workspaces import TaskWorkspace


class WorkCommandError(RuntimeError):
    """A command request or isolated runner boundary failed closed."""


REQUEST_SCHEMA = "sanctum-work-mode-command-request/v1"
NETWORK_NONE = "none"
MOUNTS = ("workspace:rw", "tmp:rw")
CREDENTIALS_NONE = "none"
CONTAINER_ENVIRONMENT = MappingProxyType(
    {
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
    }
)
_REQUEST_FIELDS = {
    "schema",
    "operation",
    "cwd",
    "network",
    "mounts",
    "environment",
    "credentials",
}
_OPERATION = re.compile(r"[a-z][a-z0-9-]{0,31}")
_IMAGE = re.compile(r"sha256:[a-f0-9]{64}")
_RUNNER_USER = re.compile(r"[1-9][0-9]{0,9}:[1-9][0-9]{0,9}")
_Invoke = Callable[[list[str], Mapping[str, str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class CommandRequest:
    operation: str
    cwd: str


@dataclass(frozen=True)
class OciRunnerProfile:
    """Host-selected private binding for reviewed commands and a pinned image."""

    runtime: Path
    runtime_host: str
    image: str
    runner_user: str
    operations: Mapping[str, tuple[str, ...]]


def command_request(operation: str, cwd: str = ".") -> dict[str, Any]:
    """Build the complete request shape; parsing still enforces every value."""

    return {
        "schema": REQUEST_SCHEMA,
        "operation": operation,
        "cwd": cwd,
        "network": NETWORK_NONE,
        "mounts": list(MOUNTS),
        "environment": dict(CONTAINER_ENVIRONMENT),
        "credentials": CREDENTIALS_NONE,
    }


def parse_command_request(value: Any) -> CommandRequest:
    if not isinstance(value, dict) or set(value) != _REQUEST_FIELDS:
        raise WorkCommandError("invalid command request fields")
    if value["schema"] != REQUEST_SCHEMA:
        raise WorkCommandError("unsupported command request schema")
    operation = value["operation"]
    cwd = value["cwd"]
    if type(operation) is not str or not _OPERATION.fullmatch(operation):
        raise WorkCommandError("invalid command operation")
    if type(cwd) is not str or not _safe_relative_cwd(cwd):
        raise WorkCommandError("unsafe command cwd")
    if value["network"] != NETWORK_NONE:
        raise WorkCommandError("command network must be disabled")
    if value["mounts"] != list(MOUNTS):
        raise WorkCommandError("command mounts are not approved")
    if value["environment"] != dict(CONTAINER_ENVIRONMENT):
        raise WorkCommandError("command environment is not approved")
    if value["credentials"] != CREDENTIALS_NONE:
        raise WorkCommandError("command credentials are forbidden")
    return CommandRequest(operation=operation, cwd=cwd)


def _safe_relative_cwd(value: str) -> bool:
    if not value or len(value) > 256 or "\\" in value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in ("", "..") for part in path.parts)


def _contained_cwd(root: Path, relative: str) -> Path:
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise WorkCommandError("task workspace is not an exact absolute directory")
    resolved_root = root.resolve(strict=True)
    if resolved_root != root or "," in str(root):
        raise WorkCommandError("task workspace uses an unsafe path")
    current = root
    if relative != ".":
        for part in PurePosixPath(relative).parts:
            if part == ".":
                continue
            current = current / part
            try:
                info = current.lstat()
            except OSError as exc:
                raise WorkCommandError("command cwd is unavailable") from exc
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise WorkCommandError("command cwd must not traverse symlinks")
    try:
        current.relative_to(root)
    except ValueError as exc:
        raise WorkCommandError("command cwd escaped the task workspace") from exc
    return current


def _parse_profile(value: OciRunnerProfile) -> OciRunnerProfile:
    if not isinstance(value, OciRunnerProfile):
        raise WorkCommandError("invalid isolated runner profile")
    runtime = value.runtime
    if not runtime.is_absolute() or runtime.is_symlink() or not runtime.is_file():
        raise WorkCommandError("isolated runner executable is unavailable")
    if not os.access(runtime, os.X_OK):
        raise WorkCommandError("isolated runner executable is not executable")
    if not re.fullmatch(r"unix:///[^,\x00]+", value.runtime_host):
        raise WorkCommandError("isolated runner host is not a local socket")
    if not _IMAGE.fullmatch(value.image):
        raise WorkCommandError("isolated runner image is not digest-pinned")
    if not _RUNNER_USER.fullmatch(value.runner_user):
        raise WorkCommandError("isolated runner identity must be non-root")
    if not isinstance(value.operations, Mapping) or not value.operations:
        raise WorkCommandError("isolated runner operations are unavailable")
    checked: dict[str, tuple[str, ...]] = {}
    for operation, argv in value.operations.items():
        if (
            type(operation) is not str
            or not _OPERATION.fullmatch(operation)
            or not isinstance(argv, tuple)
            or not argv
            or any(
                type(item) is not str or not item or len(item) > 512 for item in argv
            )
        ):
            raise WorkCommandError("invalid isolated runner operation")
        checked[operation] = argv
    return OciRunnerProfile(
        runtime=runtime,
        runtime_host=value.runtime_host,
        image=value.image,
        runner_user=value.runner_user,
        operations=MappingProxyType(checked),
    )


class IsolatedCommandRunner:
    """Resolve reviewed operations and launch only the fixed OCI sandbox shape."""

    def __init__(
        self,
        profiles: Mapping[str, OciRunnerProfile],
        workspace_root: Path,
        *,
        invoke: _Invoke | None = None,
    ) -> None:
        if not isinstance(profiles, Mapping) or not profiles:
            raise WorkCommandError("isolated runner profiles are unavailable")
        self.profiles = MappingProxyType(
            {
                reference: _parse_profile(profile)
                for reference, profile in profiles.items()
                if type(reference) is str and reference
            }
        )
        if len(self.profiles) != len(profiles):
            raise WorkCommandError("invalid isolated runner profile reference")
        if (
            not workspace_root.is_absolute()
            or workspace_root.is_symlink()
            or not workspace_root.is_dir()
            or workspace_root.resolve(strict=True) != workspace_root
        ):
            raise WorkCommandError("approved workspace root is unavailable")
        self.workspace_root = workspace_root
        self._invoke = invoke or self._subprocess

    @staticmethod
    def _subprocess(
        arguments: list[str], environment: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                arguments,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise WorkCommandError("isolated runner unavailable") from exc

    def run(
        self,
        profile_reference: str,
        workspace: TaskWorkspace,
        request_value: Any,
    ) -> Mapping[str, Any]:
        request = parse_command_request(request_value)
        try:
            profile = self.profiles[profile_reference]
        except KeyError as exc:
            raise WorkCommandError("isolated runner profile is unavailable") from exc
        try:
            argv = profile.operations[request.operation]
        except KeyError as exc:
            raise WorkCommandError("command operation is not reviewed") from exc
        if (
            workspace.root.parent != self.workspace_root
            or workspace.root.name != workspace.task_id
        ):
            raise WorkCommandError(
                "command workspace is outside the approved task root"
            )
        _contained_cwd(workspace.root, request.cwd)

        runtime_environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "LC_ALL": "C",
            "HOME": "/nonexistent",
            "DOCKER_HOST": profile.runtime_host,
        }
        inspect = self._invoke(
            [
                str(profile.runtime),
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                profile.image,
            ],
            runtime_environment,
        )
        if inspect.returncode != 0 or inspect.stdout.strip() != profile.image:
            raise WorkCommandError("isolated runner image identity mismatch")

        container_cwd = "/workspace"
        if request.cwd != ".":
            container_cwd += "/" + request.cwd.removeprefix("./")
        arguments = [
            str(profile.runtime),
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            profile.runner_user,
            "--mount",
            f"type=bind,source={workspace.root},destination=/workspace",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,noexec",
            "--workdir",
            container_cwd,
        ]
        for name, item in CONTAINER_ENVIRONMENT.items():
            arguments.extend(("--env", f"{name}={item}"))
        result = self._invoke([*arguments, profile.image, *argv], runtime_environment)
        return MappingProxyType(
            {
                "ok": result.returncode == 0,
                "code": "OK" if result.returncode == 0 else "COMMAND_FAILED",
                "executionState": "COMPLETED",
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
