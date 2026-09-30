"""Host-owned isolated worktrees for reviewed Work Mode project profiles."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from sanctum_agents.work_projects import ProjectProfile, ProjectProfiles


class WorkWorkspaceError(RuntimeError):
    """A project binding or task workspace failed closed."""


STATE_SCHEMA = "sanctum-work-mode-task-workspace/v1"
BRANCH_STATE_SCHEMA = "sanctum-work-mode-task-branch/v1"
COMMIT_STATE_SCHEMA = "sanctum-work-mode-task-commit/v1"
PULL_REQUEST_STATE_SCHEMA = "sanctum-work-mode-task-pull-request/v1"
_TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_ISSUE_ID = re.compile(r"[A-Z][A-Z0-9]*-[1-9][0-9]*")
_OPERATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
_COMMIT = re.compile(r"[a-f0-9]{40}")
_PROTECTED_PARTS = {".git", ".agents", ".codex"}
_PRIVATE_NAMES = {
    ".env",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "secrets",
    "secrets.json",
}
_PRIVATE_SUFFIXES = {".key", ".p12", ".pem"}
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
        *,
        github_executable: Path | None = None,
        github_config_dir: Path | None = None,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.profiles = profiles
        self.repository_bindings = dict(repository_bindings)
        self.workspace_root = _real_directory(workspace_root, "workspace root")
        self.state_root = _real_directory(state_root, "workspace state root")
        self.github_executable = github_executable
        self.github_config_dir = github_config_dir
        self.fault_injector = fault_injector
        if (
            self.state_root == self.workspace_root
            or self.state_root.is_relative_to(self.workspace_root)
            or self.workspace_root.is_relative_to(self.state_root)
        ):
            raise WorkWorkspaceError("workspace state must remain outside workspaces")
        self.receipt_root = self.state_root / "workspaces"
        self.lock_root = self.state_root / "locks"
        self.branch_root = self.state_root / "branches"
        self.operation_root = self.state_root / "operations"
        for directory in (
            self.receipt_root,
            self.lock_root,
            self.branch_root,
            self.operation_root,
        ):
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

    def _gh(
        self, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        executable = self.github_executable
        config = self.github_config_dir
        executable_path = (
            executable.resolve(strict=False) if isinstance(executable, Path) else None
        )
        if (
            not isinstance(executable, Path)
            or not executable.is_absolute()
            or executable.name != "gh"
            or executable.is_symlink()
            or not executable.is_file()
            or not os.access(executable, os.X_OK)
            or executable_path != executable
            or executable.is_relative_to(self.workspace_root)
        ):
            raise WorkWorkspaceError("reviewed GitHub CLI is unavailable")
        if (
            not isinstance(config, Path)
            or not config.is_absolute()
            or config.is_symlink()
            or not config.is_dir()
            or config.resolve(strict=True) != config
            or config.stat().st_mode & 0o077
            or config == self.workspace_root
            or config.is_relative_to(self.workspace_root)
        ):
            raise WorkWorkspaceError(
                "private GitHub authentication directory is unavailable"
            )
        environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "LC_ALL": "C",
            "HOME": "/nonexistent",
            "GH_CONFIG_DIR": str(config),
        }
        try:
            result = subprocess.run(
                [str(executable), *arguments],
                cwd=self.workspace_root,
                env=environment,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkWorkspaceError("GitHub PR operation unavailable") from exc
        if check and result.returncode != 0:
            raise WorkWorkspaceError("GitHub PR operation refused")
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

    def _branch_path(self, task_id: str) -> Path:
        self._task_paths(task_id)
        return self.branch_root / f"{task_id}.json"

    def _operation_path(self, task_id: str, operation_id: str) -> Path:
        self._task_paths(task_id)
        if type(operation_id) is not str or not _OPERATION_ID.fullmatch(operation_id):
            raise WorkWorkspaceError("invalid commit operation identifier")
        directory = self.operation_root / task_id
        if directory.exists() and (
            directory.is_symlink()
            or not directory.is_dir()
            or directory.resolve(strict=True).parent != self.operation_root
        ):
            raise WorkWorkspaceError("commit operation state mismatch")
        directory.mkdir(mode=0o700, exist_ok=True)
        directory.chmod(0o700)
        return directory / f"commit-{operation_id}.json"

    def _pull_request_path(self, task_id: str, operation_id: Any) -> Path:
        self._task_paths(task_id)
        if type(operation_id) is not str or not _OPERATION_ID.fullmatch(operation_id):
            raise WorkWorkspaceError("invalid pull-request operation identifier")
        directory = self.operation_root / task_id
        if directory.exists() and (
            directory.is_symlink()
            or not directory.is_dir()
            or directory.resolve(strict=True).parent != self.operation_root
        ):
            raise WorkWorkspaceError("pull-request operation state mismatch")
        directory.mkdir(mode=0o700, exist_ok=True)
        directory.chmod(0o700)
        return directory / f"pull-request-{operation_id}.json"

    @staticmethod
    def _private_state(path: Path) -> dict[str, Any] | None:
        if not path.exists() and not path.is_symlink():
            return None
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise WorkWorkspaceError("private Git operation state mismatch")
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkWorkspaceError(
                "private Git operation state is unreadable"
            ) from exc
        if not isinstance(value, dict):
            raise WorkWorkspaceError("private Git operation state mismatch")
        return value

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

    def _verify_task(self, workspace: TaskWorkspace) -> ProjectProfile:
        if not isinstance(workspace, TaskWorkspace):
            raise WorkWorkspaceError("invalid task workspace")
        profile = self.profiles.select(workspace.project_id)
        expected_root, receipt = self._task_paths(workspace.task_id)
        repository = self._binding(profile)
        expected = self._state(
            profile,
            workspace.task_id,
            repository,
            expected_root,
            workspace.base_commit,
        )
        state = self._load_state(
            receipt, {k: v for k, v in expected.items() if k != "base_commit"}
        )
        if (
            workspace.root != expected_root
            or workspace.repository != profile.repository
            or workspace.base_branch != profile.base_branch
            or state["base_commit"] != workspace.base_commit
        ):
            raise WorkWorkspaceError("task workspace identity mismatch")
        self._verify_workspace(workspace.root, repository, workspace.base_commit)
        return profile

    @staticmethod
    def _branch_name(issue_identifier: str) -> str:
        if type(issue_identifier) is not str or not _ISSUE_ID.fullmatch(
            issue_identifier
        ):
            raise WorkWorkspaceError("invalid issue identifier")
        return f"symphony/{issue_identifier.lower()}"

    def establish_branch(
        self, workspace: TaskWorkspace, issue_identifier: str
    ) -> Mapping[str, str]:
        """Bind one task to its deterministic issue branch at the captured base."""
        branch = self._branch_name(issue_identifier)
        with self._locked(workspace.task_id):
            profile = self._verify_task(workspace)
            path = self._branch_path(workspace.task_id)
            expected = {
                "schema": BRANCH_STATE_SCHEMA,
                "project_id": profile.project_id,
                "task_id": workspace.task_id,
                "issue_identifier": issue_identifier,
                "repository": profile.repository,
                "base_branch": profile.base_branch,
                "base_commit": workspace.base_commit,
                "branch": branch,
                "workspace_path": str(workspace.root),
            }
            existing = self._private_state(path)
            current = self._git(
                workspace.root,
                "symbolic-ref",
                "--quiet",
                "--short",
                "HEAD",
                check=False,
            ).stdout.strip()
            head = self._git(
                workspace.root, "rev-parse", "--verify", "HEAD^{commit}"
            ).stdout.strip()
            if existing is not None:
                if existing != expected or current != branch:
                    raise WorkWorkspaceError("task branch state mismatch")
                return {
                    "branch": branch,
                    "base_commit": workspace.base_commit,
                    "head": head,
                }
            if head != workspace.base_commit:
                raise WorkWorkspaceError("task branch must start at the approved base")
            if current:
                if current != branch:
                    raise WorkWorkspaceError(
                        "task workspace is on an unapproved branch"
                    )
            else:
                self._git(
                    workspace.root,
                    "switch",
                    "--create",
                    branch,
                    workspace.base_commit,
                )
            _atomic_private_json(path, expected)
            return {
                "branch": branch,
                "base_commit": workspace.base_commit,
                "head": workspace.base_commit,
            }

    def _require_branch(self, workspace: TaskWorkspace) -> tuple[ProjectProfile, str]:
        profile = self._verify_task(workspace)
        state = self._private_state(self._branch_path(workspace.task_id))
        if state is None:
            raise WorkWorkspaceError("task branch has not been established")
        expected = {
            "schema": BRANCH_STATE_SCHEMA,
            "project_id": profile.project_id,
            "task_id": workspace.task_id,
            "issue_identifier": state.get("issue_identifier"),
            "repository": profile.repository,
            "base_branch": profile.base_branch,
            "base_commit": workspace.base_commit,
            "branch": state.get("branch"),
            "workspace_path": str(workspace.root),
        }
        issue = expected["issue_identifier"]
        branch = expected["branch"]
        if (
            state != expected
            or type(issue) is not str
            or type(branch) is not str
            or branch != self._branch_name(issue)
        ):
            raise WorkWorkspaceError("task branch state mismatch")
        current = self._git(
            workspace.root,
            "symbolic-ref",
            "--quiet",
            "--short",
            "HEAD",
            check=False,
        ).stdout.strip()
        ancestry = self._git(
            workspace.root,
            "merge-base",
            "--is-ancestor",
            workspace.base_commit,
            "HEAD",
            check=False,
        )
        if current != branch or ancestry.returncode != 0:
            raise WorkWorkspaceError(
                "Git mutation requires the deterministic task branch"
            )
        return profile, branch

    def _changed_paths(self, workspace: TaskWorkspace) -> set[str]:
        output = self._git(
            workspace.root,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ).stdout
        fields = output.split("\0")
        paths: set[str] = set()
        index = 0
        while index < len(fields) and fields[index]:
            field = fields[index]
            if len(field) < 4:
                raise WorkWorkspaceError("task Git status is malformed")
            paths.add(field[3:])
            if field[:2].strip() in {"R", "C"}:
                index += 1
                if index < len(fields) and fields[index]:
                    paths.add(fields[index])
            index += 1
        return paths

    def _commit_paths(self, workspace: TaskWorkspace, paths: Any) -> list[str]:
        if not isinstance(paths, list) or not paths or len(paths) > 100:
            raise WorkWorkspaceError("commit paths must be a non-empty bounded list")
        checked: list[str] = []
        for value in paths:
            if type(value) is not str or not value or "\x00" in value or "\\" in value:
                raise WorkWorkspaceError("commit path is invalid")
            path = PurePosixPath(value)
            lowered = {part.lower() for part in path.parts}
            if (
                path.is_absolute()
                or ".." in path.parts
                or _PROTECTED_PARTS & set(path.parts)
                or _PRIVATE_NAMES & lowered
                or path.suffix.lower() in _PRIVATE_SUFFIXES
                or any(part.startswith(".env.") for part in lowered)
            ):
                raise WorkWorkspaceError("commit path is not permitted")
            cursor = workspace.root
            for part in path.parts:
                cursor /= part
                if cursor.is_symlink():
                    raise WorkWorkspaceError("commit path may not traverse symlinks")
            checked.append(path.as_posix())
        if len(checked) != len(set(checked)):
            raise WorkWorkspaceError("duplicate commit paths are not permitted")
        return sorted(checked)

    def _commit_matches(
        self, workspace: TaskWorkspace, receipt: Mapping[str, Any]
    ) -> bool:
        head = self._git(workspace.root, "rev-parse", "HEAD").stdout.strip()
        if head == receipt.get("pre_head"):
            return False
        details = self._git(
            workspace.root, "show", "-s", "--format=%P%n%T", "HEAD"
        ).stdout.splitlines()
        return (
            len(details) == 2
            and details[0] == receipt.get("pre_head")
            and details[1] == receipt.get("expected_tree")
        )

    def _reconcile_commit(
        self, workspace: TaskWorkspace, path: Path, receipt: dict[str, Any]
    ) -> Mapping[str, Any]:
        if not self._commit_matches(workspace, receipt):
            raise WorkWorkspaceError(
                "commit result is unknown and was not replayed; operator review required"
            )
        head = self._git(workspace.root, "rev-parse", "HEAD").stdout.strip()
        receipt.update({"state": "applied", "commit": head, "reconciled": True})
        _atomic_private_json(path, receipt)
        return {"status": "reconciled", "commit": head, "paths": receipt["paths"]}

    def commit(
        self,
        workspace: TaskWorkspace,
        message: Any,
        paths: Any,
        operation_id: Any,
    ) -> Mapping[str, Any]:
        """Commit only exact selected task paths with replay-safe private state."""
        if (
            type(message) is not str
            or not 8 <= len(message) <= 120
            or message.strip() != message
            or "\n" in message
            or "\r" in message
        ):
            raise WorkWorkspaceError("commit message must be one bounded summary line")
        checked = self._commit_paths(workspace, paths)
        request_hash = hashlib.sha256(
            json.dumps(
                {"message": message, "paths": checked},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        with self._locked(workspace.task_id):
            _, branch = self._require_branch(workspace)
            receipt_path = self._operation_path(workspace.task_id, operation_id)
            existing = self._private_state(receipt_path)
            if existing is not None:
                if existing.get("request_sha256") != request_hash:
                    raise WorkWorkspaceError(
                        "operation identifier was used for a different commit request"
                    )
                if existing.get("state") == "applied":
                    return {
                        "status": "already_applied",
                        "commit": existing.get("commit"),
                        "paths": existing.get("paths"),
                    }
                return self._reconcile_commit(workspace, receipt_path, existing)
            changed = self._changed_paths(workspace)
            if not set(checked).issubset(changed):
                raise WorkWorkspaceError(
                    "every selected path must exactly identify a changed file"
                )
            if self._git(
                workspace.root, "diff", "--cached", "--quiet", check=False
            ).returncode:
                raise WorkWorkspaceError("task commit requires an unstaged Git index")
            try:
                self._git(workspace.root, "add", "-A", "--", *checked)
                staged = [
                    item
                    for item in self._git(
                        workspace.root,
                        "diff",
                        "--cached",
                        "--name-only",
                        "-z",
                        "--diff-filter=ACDMRTUXB",
                    ).stdout.split("\0")
                    if item
                ]
                if not staged or not set(staged).issubset(set(checked)):
                    raise WorkWorkspaceError(
                        "staged paths exceeded the explicit selection"
                    )
                expected_tree = self._git(workspace.root, "write-tree").stdout.strip()
            except Exception:
                self._git(workspace.root, "read-tree", "--reset", "HEAD", check=False)
                raise
            pre_head = self._git(workspace.root, "rev-parse", "HEAD").stdout.strip()
            receipt = {
                "schema": COMMIT_STATE_SCHEMA,
                "state": "pending",
                "operation_id": operation_id,
                "task_id": workspace.task_id,
                "branch": branch,
                "pre_head": pre_head,
                "expected_tree": expected_tree,
                "paths": staged,
                "request_sha256": request_hash,
            }
            _atomic_private_json(receipt_path, receipt)
            result = self._git(
                workspace.root,
                "-c",
                "user.name=Sanctum Work Mode",
                "-c",
                "user.email=work-mode@localhost",
                "commit",
                "--no-gpg-sign",
                "--message",
                message,
                check=False,
            )
            if self.fault_injector:
                self.fault_injector("after_commit")
            if result.returncode != 0:
                if self._commit_matches(workspace, receipt):
                    return self._reconcile_commit(workspace, receipt_path, receipt)
                receipt["state"] = "failed"
                _atomic_private_json(receipt_path, receipt)
                self._git(workspace.root, "read-tree", "--reset", "HEAD", check=False)
                raise WorkWorkspaceError("bounded task commit failed")
            head = self._git(workspace.root, "rev-parse", "HEAD").stdout.strip()
            receipt.update({"state": "applied", "commit": head, "reconciled": False})
            _atomic_private_json(receipt_path, receipt)
            return {"status": "applied", "commit": head, "paths": staged}

    @staticmethod
    def _validation_evidence(
        profile: ProjectProfile, receipts: Any
    ) -> list[dict[str, Any]]:
        from sanctum_agents.work_validation import ValidationReceipt

        if not isinstance(receipts, list) or not receipts:
            raise WorkWorkspaceError("successful validation receipts are required")
        evidence: dict[str, dict[str, Any]] = {}
        for receipt in receipts:
            if not isinstance(receipt, ValidationReceipt):
                raise WorkWorkspaceError("validation receipt provenance is invalid")
            result = receipt.result
            if (
                receipt.project_id != profile.project_id
                or receipt.profile != profile.private_config_refs.validation
                or receipt.command not in profile.validation_operations
                or receipt.command in evidence
                or result.get("ok") is not True
                or result.get("code") != "OK"
                or result.get("executionState") != "COMPLETED"
                or result.get("exit_code") != 0
                or type(result.get("stdout")) is not str
                or type(result.get("stderr")) is not str
            ):
                raise WorkWorkspaceError("validation receipt does not prove success")
            evidence[receipt.command] = {
                "schema": receipt.as_dict()["schema"],
                "project_id": receipt.project_id,
                "profile": receipt.profile,
                "command": receipt.command,
                "code": result["code"],
                "executionState": result["executionState"],
                "exit_code": result["exit_code"],
                "stdout_sha256": hashlib.sha256(result["stdout"].encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(result["stderr"].encode()).hexdigest(),
            }
        if set(evidence) != set(profile.validation_operations):
            raise WorkWorkspaceError(
                "validation receipts do not cover the project profile"
            )
        return [evidence[command] for command in profile.validation_operations]

    def _remote_task_head(self, profile: ProjectProfile, branch: str) -> str:
        result = self._gh(
            "api",
            f"repos/{profile.repository}/git/ref/heads/{branch.replace('/', '%2F')}",
            check=False,
        )
        if result.returncode != 0:
            raise WorkWorkspaceError("approved task branch is not available on GitHub")
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise WorkWorkspaceError("GitHub task branch response is invalid") from exc
        head = value.get("object", {}).get("sha") if isinstance(value, dict) else None
        if type(head) is not str or not _COMMIT.fullmatch(head):
            raise WorkWorkspaceError("GitHub task branch response is invalid")
        return head

    def _open_task_pull_request(
        self, profile: ProjectProfile, branch: str, head: str
    ) -> dict[str, Any] | None:
        result = self._gh(
            "pr",
            "list",
            "--repo",
            profile.repository,
            "--state",
            "open",
            "--head",
            branch,
            "--json",
            "number,url,baseRefName,headRefName,headRefOid,headRepository,headRepositoryOwner,isDraft,title,body",
        )
        try:
            values = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise WorkWorkspaceError("GitHub PR response is invalid") from exc
        if not isinstance(values, list):
            raise WorkWorkspaceError("GitHub PR state is ambiguous")
        if not values:
            return None
        owner = profile.repository.split("/", 1)[0]
        matching = [
            value
            for value in values
            if isinstance(value, dict)
            and value.get("baseRefName") == profile.base_branch
            and value.get("headRefName") == branch
            and value.get("headRefOid") == head
            and value.get("isDraft") is False
            and isinstance(value.get("headRepository"), dict)
            and value["headRepository"].get("nameWithOwner") == profile.repository
            and isinstance(value.get("headRepositoryOwner"), dict)
            and value["headRepositoryOwner"].get("login") == owner
            and type(value.get("number")) is int
            and type(value.get("url")) is str
        ]
        if len(values) != 1 or len(matching) != 1:
            raise WorkWorkspaceError(
                "open PR does not match the approved repository, base, and task head"
            )
        return matching[0]

    @staticmethod
    def _pull_request_body(
        workspace: TaskWorkspace,
        issue_identifier: str,
        branch: str,
        body: Any,
        evidence: list[dict[str, Any]],
    ) -> str:
        if (
            type(body) is not str
            or not 20 <= len(body) <= 2400
            or "\x00" in body
            or body.strip() != body
        ):
            raise WorkWorkspaceError("PR body must be bounded non-empty text")
        validation = json.dumps(evidence, indent=2, sort_keys=True)
        rendered = (
            f"{body}\n\n"
            "## Sanctum Work Mode provenance\n\n"
            f"- Issue: `{issue_identifier}`\n"
            f"- Project: `{workspace.project_id}`\n"
            f"- Task: `{workspace.task_id}`\n"
            f"- Repository: `{workspace.repository}`\n"
            f"- Head: `{branch}`\n"
            f"- Base: `{workspace.base_branch}`\n\n"
            "## Validation evidence\n\n"
            f"```json\n{validation}\n```"
        )
        if len(rendered) > 4000:
            raise WorkWorkspaceError("PR body and validation evidence are too large")
        return rendered

    def ensure_pull_request(
        self,
        workspace: TaskWorkspace,
        title: Any,
        body: Any,
        validation_receipts: Any,
        operation_id: Any,
    ) -> Mapping[str, Any]:
        """Create or update one validated PR for the exact profiled task branch."""
        if (
            type(title) is not str
            or not 8 <= len(title) <= 120
            or title.strip() != title
            or "\n" in title
            or "\r" in title
        ):
            raise WorkWorkspaceError("PR title must be one bounded summary line")
        with self._locked(workspace.task_id):
            profile, branch = self._require_branch(workspace)
            branch_state = self._private_state(self._branch_path(workspace.task_id))
            issue_identifier = (
                branch_state.get("issue_identifier")
                if isinstance(branch_state, dict)
                else None
            )
            if type(issue_identifier) is not str:
                raise WorkWorkspaceError("task branch state mismatch")
            evidence = self._validation_evidence(profile, validation_receipts)
            rendered_body = self._pull_request_body(
                workspace, issue_identifier, branch, body, evidence
            )
            repository = self._binding(profile)
            if self._base_commit(repository, profile) != workspace.base_commit:
                raise WorkWorkspaceError(
                    "approved base branch advanced after task start"
                )
            head = self._git(workspace.root, "rev-parse", "HEAD").stdout.strip()
            if self._remote_task_head(profile, branch) != head:
                raise WorkWorkspaceError(
                    "GitHub task branch does not match the local committed head"
                )
            receipt_path = self._pull_request_path(workspace.task_id, operation_id)
            intent = {
                "schema": PULL_REQUEST_STATE_SCHEMA,
                "operation_id": operation_id,
                "project_id": profile.project_id,
                "task_id": workspace.task_id,
                "issue_identifier": issue_identifier,
                "repository": profile.repository,
                "base_branch": profile.base_branch,
                "branch": branch,
                "head": head,
                "title": title,
                "body": rendered_body,
                "validation": evidence,
            }
            prior = self._private_state(receipt_path)
            if prior is not None:
                if any(prior.get(key) != value for key, value in intent.items()):
                    raise WorkWorkspaceError(
                        "operation identifier was used for a different PR request"
                    )
                reconciled = self._open_task_pull_request(profile, branch, head)
                if (
                    reconciled is not None
                    and reconciled.get("title") == title
                    and reconciled.get("body") == rendered_body
                ):
                    prior.update(
                        {
                            "state": "applied",
                            "number": reconciled["number"],
                            "url": reconciled["url"],
                            "reconciled": True,
                        }
                    )
                    _atomic_private_json(receipt_path, prior)
                    return {
                        "status": "already_applied",
                        "number": reconciled["number"],
                        "url": reconciled["url"],
                        "base": profile.base_branch,
                        "head": branch,
                    }
                raise WorkWorkspaceError(
                    "pull-request result is unknown and was not replayed; operator review required"
                )
            receipt = {**intent, "state": "pending"}
            _atomic_private_json(receipt_path, receipt)
            existing = self._open_task_pull_request(profile, branch, head)
            status = "updated"
            if existing is not None:
                if (
                    existing.get("title") != title
                    or existing.get("body") != rendered_body
                ):
                    result = self._gh(
                        "pr",
                        "edit",
                        str(existing["number"]),
                        "--repo",
                        profile.repository,
                        "--title",
                        title,
                        "--body",
                        rendered_body,
                        check=False,
                    )
                    if self.fault_injector:
                        self.fault_injector("after_pull_request_update")
                    reconciled = self._open_task_pull_request(profile, branch, head)
                    if (
                        result.returncode != 0
                        or reconciled is None
                        or reconciled.get("title") != title
                        or reconciled.get("body") != rendered_body
                    ):
                        raise WorkWorkspaceError(
                            "PR update result is unknown and was not replayed; operator review required"
                        )
                    existing = reconciled
            else:
                status = "created"
                result = self._gh(
                    "pr",
                    "create",
                    "--repo",
                    profile.repository,
                    "--base",
                    profile.base_branch,
                    "--head",
                    branch,
                    "--title",
                    title,
                    "--body",
                    rendered_body,
                    check=False,
                )
                if self.fault_injector:
                    self.fault_injector("after_pull_request_create")
                existing = self._open_task_pull_request(profile, branch, head)
                if result.returncode != 0 or existing is None:
                    raise WorkWorkspaceError(
                        "PR creation result is unknown and was not replayed; operator review required"
                    )
            receipt.update(
                {
                    "state": "applied",
                    "number": existing["number"],
                    "url": existing["url"],
                    "reconciled": False,
                }
            )
            _atomic_private_json(receipt_path, receipt)
            return {
                "status": status,
                "number": existing["number"],
                "url": existing["url"],
                "base": profile.base_branch,
                "head": branch,
            }

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
