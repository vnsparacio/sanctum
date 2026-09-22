"""Host-owned isolated worktrees for reviewed Work Mode project profiles."""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sanctum_agents.work_projects import ProjectProfile, ProjectProfiles


class WorkWorkspaceError(RuntimeError):
    """A project binding or task workspace failed closed."""


STATE_SCHEMA = "sanctum-work-mode-task-workspace/v1"
_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_COMMIT = re.compile(r"[a-f0-9]{40}")
_GIT_ENV = {
    "PATH": "/usr/bin:/bin",
    "LANG": "C",
    "LC_ALL": "C",
    "HOME": "/nonexistent",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
}


@dataclass(frozen=True)
class TaskWorkspace:
    project_id: str
    task_id: str
    root: Path
    repository: str
    base_branch: str
    base_commit: str
    resumed: bool


def _real_directory(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise WorkWorkspaceError(f"{label} must be an existing absolute directory")
    resolved = path.resolve(strict=True)
    if resolved != path:
        raise WorkWorkspaceError(f"{label} must not use aliases or symlinks")
    return resolved


def _atomic_private_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


class WorkWorkspaceManager:
    """Creates worktrees using only a selected profile and private host bindings."""

    def __init__(
        self,
        profiles: ProjectProfiles,
        repository_bindings: Mapping[str, Path],
        workspace_root: Path,
        state_root: Path,
    ) -> None:
        self.profiles = profiles
        self.repository_bindings = dict(repository_bindings)
        self.workspace_root = _real_directory(workspace_root, "workspace root")
        self.state_root = _real_directory(state_root, "workspace state root")
        if (
            self.state_root == self.workspace_root
            or self.state_root.is_relative_to(self.workspace_root)
            or self.workspace_root.is_relative_to(self.state_root)
        ):
            raise WorkWorkspaceError("workspace state must remain outside workspaces")
        self.receipt_root = self.state_root / "workspaces"
        self.lock_root = self.state_root / "locks"
        for directory in (self.receipt_root, self.lock_root):
            directory.mkdir(mode=0o700, exist_ok=True)
            checked = _real_directory(directory, "workspace state directory")
            if checked.parent != self.state_root:
                raise WorkWorkspaceError("workspace state directory escaped its root")
            checked.chmod(0o700)
        self.git = Path("/usr/bin/git")
        if not self.git.is_file():
            raise WorkWorkspaceError("reviewed Git executable unavailable")

    def _git(
        self, repository: Path, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                [str(self.git), "-c", "core.hooksPath=/dev/null", *arguments],
                cwd=repository,
                env=_GIT_ENV,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkWorkspaceError("workspace Git operation unavailable") from exc
        if check and result.returncode != 0:
            raise WorkWorkspaceError("workspace Git operation refused")
        return result

    @staticmethod
    def _remote_repository(remote: str) -> str | None:
        patterns = (
            r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?",
            r"git@github\.com:([^/]+/[^/]+?)(?:\.git)?",
            r"ssh://git@github\.com/([^/]+/[^/]+?)(?:\.git)?/?",
        )
        for pattern in patterns:
            match = re.fullmatch(pattern, remote)
            if match:
                return match.group(1)
        return None

    def _binding(self, profile: ProjectProfile) -> Path:
        reference = profile.private_config_refs.repository
        if reference not in self.repository_bindings:
            raise WorkWorkspaceError("approved repository binding is unavailable")
        repository = _real_directory(
            Path(self.repository_bindings[reference]), "repository binding"
        )
        if (
            repository == self.workspace_root
            or repository.is_relative_to(self.workspace_root)
            or self.workspace_root.is_relative_to(repository)
            or repository == self.state_root
            or repository.is_relative_to(self.state_root)
            or self.state_root.is_relative_to(repository)
        ):
            raise WorkWorkspaceError("repository binding overlaps private task state")
        top = self._git(repository, "rev-parse", "--show-toplevel").stdout.strip()
        if Path(top).resolve(strict=True) != repository:
            raise WorkWorkspaceError("repository binding is not a repository root")
        remote = self._git(repository, "remote", "get-url", "origin").stdout.strip()
        if self._remote_repository(remote) != profile.repository:
            raise WorkWorkspaceError("repository binding identity mismatch")
        return repository

    def _base_commit(self, repository: Path, profile: ProjectProfile) -> str:
        reference = f"refs/remotes/origin/{profile.base_branch}^{{commit}}"
        result = self._git(repository, "rev-parse", "--verify", reference, check=False)
        commit = result.stdout.strip()
        if result.returncode != 0 or not _COMMIT.fullmatch(commit):
            raise WorkWorkspaceError("approved base branch is unavailable")
        return commit

    @contextmanager
    def _locked(self, task_id: str):
        lock_path = self.lock_root / f"{task_id}.lock"
        descriptor = os.open(
            lock_path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _task_paths(self, task_id: str) -> tuple[Path, Path]:
        if type(task_id) is not str or not _TASK_ID.fullmatch(task_id):
            raise WorkWorkspaceError("unsafe task workspace identifier")
        workspace = self.workspace_root / task_id
        receipt = self.receipt_root / f"{task_id}.json"
        if (
            workspace.parent != self.workspace_root
            or receipt.parent != self.receipt_root
        ):
            raise WorkWorkspaceError("task workspace escaped its approved root")
        return workspace, receipt

    def _state(
        self,
        profile: ProjectProfile,
        task_id: str,
        repository: Path,
        workspace: Path,
        base_commit: str,
    ) -> dict[str, Any]:
        return {
            "schema": STATE_SCHEMA,
            "project_id": profile.project_id,
            "task_id": task_id,
            "repository": profile.repository,
            "repository_path": str(repository),
            "base_branch": profile.base_branch,
            "base_commit": base_commit,
            "workspace_path": str(workspace),
        }

    def _load_state(
        self, receipt: Path, expected_identity: Mapping[str, Any]
    ) -> dict[str, Any]:
        if receipt.is_symlink() or not receipt.is_file():
            raise WorkWorkspaceError("task workspace state mismatch")
        info = receipt.stat()
        if info.st_mode & 0o077:
            raise WorkWorkspaceError("task workspace state mismatch")
        try:
            value = json.loads(receipt.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkWorkspaceError("task workspace state is unreadable") from exc
        if not isinstance(value, dict) or set(value) != {
            *expected_identity,
            "base_commit",
        }:
            raise WorkWorkspaceError("task workspace state mismatch")
        if any(value[key] != item for key, item in expected_identity.items()) or not (
            isinstance(value["base_commit"], str)
            and _COMMIT.fullmatch(value["base_commit"])
        ):
            raise WorkWorkspaceError("task workspace state mismatch")
        return value

    def _verify_workspace(
        self,
        workspace: Path,
        repository: Path,
        base_commit: str,
        *,
        exact_base: bool = False,
    ) -> None:
        root = _real_directory(workspace, "task workspace")
        top = self._git(root, "rev-parse", "--show-toplevel").stdout.strip()
        if Path(top).resolve(strict=True) != root:
            raise WorkWorkspaceError("task workspace is not a repository root")
        head = self._git(root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
        if exact_base and head != base_commit:
            raise WorkWorkspaceError("task workspace base mismatch")
        if not exact_base:
            ancestry = self._git(
                root,
                "merge-base",
                "--is-ancestor",
                base_commit,
                head,
                check=False,
            )
            if ancestry.returncode != 0:
                raise WorkWorkspaceError("task workspace base mismatch")
        common = self._git(
            root, "rev-parse", "--path-format=absolute", "--git-common-dir"
        )
        source_common = self._git(
            repository, "rev-parse", "--path-format=absolute", "--git-common-dir"
        )
        if Path(common.stdout.strip()).resolve(strict=True) != Path(
            source_common.stdout.strip()
        ).resolve(strict=True):
            raise WorkWorkspaceError("task workspace repository mismatch")

    def create(self, project_id: str, task_id: str) -> TaskWorkspace:
        """Create or resume the task worktree derived from one reviewed profile."""
        profile = self.profiles.select(project_id)
        workspace, receipt = self._task_paths(task_id)
        with self._locked(task_id):
            repository = self._binding(profile)
            if receipt.exists() or receipt.is_symlink():
                identity = self._state(profile, task_id, repository, workspace, "")
                identity.pop("base_commit")
                state = self._load_state(receipt, identity)
                base_commit = state["base_commit"]
                self._verify_workspace(workspace, repository, base_commit)
                resumed = True
            else:
                base_commit = self._base_commit(repository, profile)
                expected = self._state(
                    profile, task_id, repository, workspace, base_commit
                )
                if workspace.exists() or workspace.is_symlink():
                    self._verify_workspace(
                        workspace, repository, base_commit, exact_base=True
                    )
                    _atomic_private_json(receipt, expected)
                    resumed = True
                else:
                    self._git(
                        repository,
                        "worktree",
                        "add",
                        "--detach",
                        str(workspace),
                        base_commit,
                    )
                    try:
                        self._verify_workspace(
                            workspace, repository, base_commit, exact_base=True
                        )
                        if self._git(workspace, "status", "--porcelain").stdout.strip():
                            raise WorkWorkspaceError("new task workspace is not clean")
                        _atomic_private_json(receipt, expected)
                    except Exception:
                        self._git(
                            repository,
                            "worktree",
                            "remove",
                            "--force",
                            str(workspace),
                            check=False,
                        )
                        raise
                    resumed = False
            return TaskWorkspace(
                project_id=profile.project_id,
                task_id=task_id,
                root=workspace,
                repository=profile.repository,
                base_branch=profile.base_branch,
                base_commit=base_commit,
                resumed=resumed,
            )

    def cleanup(self, project_id: str, task_id: str) -> bool:
        """Remove only the exact profiled task worktree; return false if absent."""
        profile = self.profiles.select(project_id)
        workspace, receipt = self._task_paths(task_id)
        with self._locked(task_id):
            repository = self._binding(profile)
            if not (receipt.exists() or receipt.is_symlink()):
                if not (workspace.exists() or workspace.is_symlink()):
                    return False
                base_commit = self._base_commit(repository, profile)
                self._verify_workspace(workspace, repository, base_commit)
            else:
                identity = self._state(profile, task_id, repository, workspace, "")
                identity.pop("base_commit")
                state = self._load_state(receipt, identity)
                base_commit = state["base_commit"]
                if workspace.exists() or workspace.is_symlink():
                    self._verify_workspace(workspace, repository, base_commit)
            if workspace.exists():
                result = self._git(
                    repository,
                    "worktree",
                    "remove",
                    "--force",
                    str(workspace),
                    check=False,
                )
                if result.returncode != 0 or workspace.exists():
                    raise WorkWorkspaceError("task workspace cleanup failed")
            self._git(repository, "worktree", "prune", "--expire", "now", check=False)
            if receipt.exists():
                receipt.unlink()
            return True
