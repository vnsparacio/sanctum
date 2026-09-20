"""Narrow host-owned Git state transitions for Symphony issue workspaces."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

CANONICAL_REMOTE = "https://github.com/vnsparacio/sanctum.git"
CANONICAL_GITHUB_REPOSITORY = "vnsparacio/sanctum"
CANONICAL_GITHUB_OWNER = "vnsparacio"
INTEGRATION_BASE = "v1.2-dev"
ISSUE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*-[1-9][0-9]*$")
OPERATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
PROTECTED_PARTS = {".git", ".agents", ".codex"}
PRIVATE_NAMES = {
    ".env",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "secrets",
    "secrets.json",
}
PRIVATE_SUFFIXES = {".key", ".p12", ".pem"}
ALLOWED_LOCAL_CONFIG = {
    "core.bare",
    "core.filemode",
    "core.ignorecase",
    "core.logallrefupdates",
    "core.precomposeunicode",
    "core.repositoryformatversion",
    "remote.origin.fetch",
    "remote.origin.url",
}


class GitControlError(RuntimeError):
    """A deterministic Git control-plane invariant failed."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class UnknownGitResult(GitControlError):
    """A consequential operation could not be safely reconciled."""


class _InjectedAmbiguity(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkspaceIdentity:
    workspace: Path
    workspace_root: Path
    git_dir: Path
    issue_identifier: str
    branch: str


def _atomic_private_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
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


class GitControlPlane:
    """Validates one issue workspace and performs fixed Git operations."""

    def __init__(
        self,
        workspace: Path,
        workspace_root: Path,
        state_root: Path,
        *,
        expected_remote: str = CANONICAL_REMOTE,
        credential_helper: str | None = None,
        github_config_dir: str | None = None,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self.workspace = workspace
        self.workspace_root = workspace_root
        self.state_root = state_root
        self.expected_remote = expected_remote
        self.credential_helper = credential_helper
        self.github_config_dir = github_config_dir
        self.fault_injector = fault_injector
        self.git = Path("/usr/bin/git")
        if not self.git.is_file():
            raise GitControlError(
                "git_unavailable", "reviewed Git executable unavailable"
            )
        if (
            not state_root.is_absolute()
            or state_root.is_symlink()
            or state_root != state_root.resolve(strict=False)
        ):
            raise GitControlError(
                "state_root_invalid",
                "broker state root must be absolute and non-symlink",
            )
        resolved_state = state_root.resolve(strict=False)
        resolved_workspace_root = workspace_root.resolve(strict=False)
        if resolved_state == resolved_workspace_root or resolved_state.is_relative_to(
            resolved_workspace_root
        ):
            raise GitControlError(
                "state_root_invalid",
                "broker state must remain outside issue workspaces",
            )

    def _environment(self, *, github_authenticated: bool = False) -> dict[str, str]:
        allowed = (
            "HOME",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "PATH",
            "SSH_AUTH_SOCK",
            "TMPDIR",
            "XDG_CONFIG_HOME",
        )
        values = {key: os.environ[key] for key in allowed if key in os.environ}
        values.update(
            {
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_OPTIONAL_LOCKS": "1",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        if github_authenticated:
            if not self.github_config_dir:
                raise GitControlError(
                    "github_auth_unavailable",
                    "private GitHub authentication directory is unavailable",
                )
            config_dir = Path(self.github_config_dir)
            if (
                not config_dir.is_absolute()
                or config_dir.is_symlink()
                or not config_dir.is_dir()
                or config_dir != config_dir.resolve()
                or config_dir.stat().st_mode & 0o077
                or config_dir.is_relative_to(self.workspace_root.resolve(strict=False))
            ):
                raise GitControlError(
                    "github_auth_invalid",
                    "private GitHub authentication directory is invalid",
                )
            values["GH_CONFIG_DIR"] = str(config_dir)
        return values

    def _github_executable(self) -> Path:
        if not self.credential_helper:
            raise GitControlError(
                "github_cli_unavailable", "reviewed GitHub CLI is unavailable"
            )
        executable = Path(self.credential_helper)
        if (
            not executable.is_absolute()
            or executable.name != "gh"
            or not re.fullmatch(r"[A-Za-z0-9_./-]+", str(executable))
            or not executable.is_file()
            or executable.is_symlink()
            or not os.access(executable, os.X_OK)
        ):
            raise GitControlError(
                "github_cli_unavailable", "reviewed GitHub CLI is invalid"
            )
        return executable

    def _git(
        self,
        *arguments: str,
        check: bool = True,
        timeout: int = 60,
        credentialed: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command = [str(self.git), "-c", "core.hooksPath=/dev/null"]
        if credentialed and self.credential_helper:
            helper = self._github_executable()
            command.extend(
                [
                    "-c",
                    "credential.helper=",
                    "-c",
                    f"credential.https://github.com.helper={helper} auth git-credential",
                ]
            )
        command.extend(arguments)
        try:
            result = subprocess.run(
                command,
                cwd=self.workspace,
                env=self._environment(
                    github_authenticated=credentialed and bool(self.credential_helper)
                ),
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise _InjectedAmbiguity("Git operation timed out") from exc
        if check and result.returncode:
            raise GitControlError(
                "git_operation_failed",
                f"bounded Git operation failed with exit code {result.returncode}",
            )
        return result

    def _gh(
        self, *arguments: str, check: bool = True, timeout: int = 60
    ) -> subprocess.CompletedProcess[str]:
        executable = self._github_executable()
        environment = self._environment(github_authenticated=True)
        environment.update({"GH_PROMPT_DISABLED": "1", "NO_COLOR": "1"})
        try:
            result = subprocess.run(
                [str(executable), *arguments],
                cwd=self.workspace,
                env=environment,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise _InjectedAmbiguity("GitHub operation timed out") from exc
        if check and result.returncode:
            raise GitControlError(
                "github_operation_failed",
                f"bounded GitHub operation failed with exit code {result.returncode}",
            )
        return result

    def _canonical_workspace(self) -> tuple[Path, Path]:
        if not self.workspace_root.is_absolute() or not self.workspace.is_absolute():
            raise GitControlError(
                "workspace_invalid", "workspace paths must be absolute"
            )
        if self.workspace_root.is_symlink() or self.workspace.is_symlink():
            raise GitControlError(
                "workspace_symlink", "workspace paths may not be symlinks"
            )
        try:
            root = self.workspace_root.resolve(strict=True)
            workspace = self.workspace.resolve(strict=True)
        except OSError as exc:
            raise GitControlError(
                "workspace_unreadable", "workspace is unreadable"
            ) from exc
        if workspace.parent != root:
            raise GitControlError(
                "workspace_escape",
                "workspace must be a direct child of the reviewed root",
            )
        return root, workspace

    def _validate_local_config(self, expected_branch: str) -> None:
        result = self._git("config", "--local", "--name-only", "--list")
        allowed = ALLOWED_LOCAL_CONFIG | {
            f"branch.{INTEGRATION_BASE}.merge",
            f"branch.{INTEGRATION_BASE}.remote",
            f"branch.{expected_branch}.merge",
            f"branch.{expected_branch}.remote",
        }
        keys = {line.strip().lower() for line in result.stdout.splitlines() if line}
        unexpected = sorted(keys - {item.lower() for item in allowed})
        if unexpected:
            raise GitControlError(
                "git_config_rejected", "workspace contains unreviewed local Git config"
            )

    def identity(self) -> WorkspaceIdentity:
        root, workspace = self._canonical_workspace()
        identifier = workspace.name
        if not ISSUE_PATTERN.fullmatch(identifier):
            raise GitControlError(
                "issue_identity_invalid",
                "workspace name is not a supported issue identifier",
            )
        branch = f"symphony/{identifier.lower()}"
        git_dir = workspace / ".git"
        if not git_dir.is_dir() or git_dir.is_symlink():
            raise GitControlError(
                "git_dir_invalid",
                "workspace must use an in-place non-symlink Git directory",
            )
        top = Path(self._git("rev-parse", "--show-toplevel").stdout.strip()).resolve()
        actual_git = Path(
            self._git("rev-parse", "--absolute-git-dir").stdout.strip()
        ).resolve()
        common_git = Path(self._git("rev-parse", "--git-common-dir").stdout.strip())
        if not common_git.is_absolute():
            common_git = (workspace / common_git).resolve()
        else:
            common_git = common_git.resolve()
        if (
            top != workspace
            or actual_git != git_dir.resolve()
            or common_git != git_dir.resolve()
        ):
            raise GitControlError(
                "git_dir_redirected",
                "Git metadata is not owned by this issue workspace",
            )
        urls = [
            line
            for line in self._git(
                "remote", "get-url", "--all", "origin"
            ).stdout.splitlines()
            if line
        ]
        push_urls = [
            line
            for line in self._git(
                "remote", "get-url", "--push", "--all", "origin"
            ).stdout.splitlines()
            if line
        ]
        if urls != [self.expected_remote] or push_urls != [self.expected_remote]:
            raise GitControlError(
                "remote_rejected",
                "origin does not match the reviewed repository remote",
            )
        remotes = self._git("remote").stdout.split()
        if remotes != ["origin"]:
            raise GitControlError("remote_rejected", "only origin is permitted")
        self._validate_local_config(branch)
        return WorkspaceIdentity(workspace, root, git_dir, identifier, branch)

    def _lease_path(self, identity: WorkspaceIdentity) -> Path:
        digest = hashlib.sha256(str(identity.workspace).encode()).hexdigest()
        return self.state_root / "workspaces" / f"{digest}.json"

    def _lease_value(self, identity: WorkspaceIdentity) -> dict[str, Any]:
        stat = identity.workspace.stat()
        git_stat = identity.git_dir.stat()
        return {
            "schema_version": 1,
            "workspace": str(identity.workspace),
            "workspace_root": str(identity.workspace_root),
            "workspace_device": stat.st_dev,
            "workspace_inode": stat.st_ino,
            "git_dir": str(identity.git_dir),
            "git_dir_device": git_stat.st_dev,
            "git_dir_inode": git_stat.st_ino,
            "issue_identifier": identity.issue_identifier,
            "branch": identity.branch,
            "base": INTEGRATION_BASE,
            "remote": self.expected_remote,
        }

    def _write_lease(self, identity: WorkspaceIdentity) -> None:
        _atomic_private_json(self._lease_path(identity), self._lease_value(identity))

    def _require_lease(self, identity: WorkspaceIdentity) -> None:
        path = self._lease_path(identity)
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise GitControlError(
                "workspace_not_prepared", "host workspace lease is missing or invalid"
            ) from exc
        if value != self._lease_value(identity):
            raise GitControlError(
                "workspace_identity_changed",
                "host workspace identity no longer matches",
            )

    def _current_branch(self) -> str:
        return self._git("branch", "--show-current").stdout.strip()

    def _head(self) -> str:
        return self._git("rev-parse", "HEAD").stdout.strip()

    def _clean(self) -> bool:
        return not self._git("status", "--porcelain=v1", "--untracked-files=all").stdout

    def prepare(self, requested_base: str = INTEGRATION_BASE) -> dict[str, Any]:
        if requested_base != INTEGRATION_BASE:
            raise GitControlError("base_rejected", "only origin/v1.2-dev is permitted")
        identity = self.identity()
        lease_exists = self._lease_path(identity).exists()
        if lease_exists:
            self._require_lease(identity)
        self._git(
            "fetch",
            "--no-tags",
            "origin",
            f"refs/heads/{INTEGRATION_BASE}:refs/remotes/origin/{INTEGRATION_BASE}",
        )
        current = self._current_branch()
        if current == INTEGRATION_BASE:
            if not self._clean():
                raise GitControlError(
                    "bootstrap_dirty",
                    "base workspace must be clean before branch creation",
                )
            base_head = self._git(
                "rev-parse", f"refs/remotes/origin/{INTEGRATION_BASE}"
            ).stdout.strip()
            if self._head() != base_head:
                raise GitControlError(
                    "base_stale", "local base does not equal accepted origin/v1.2-dev"
                )
            self._git(
                "switch",
                "--create",
                identity.branch,
                f"refs/remotes/origin/{INTEGRATION_BASE}",
            )
        elif current != identity.branch:
            raise GitControlError(
                "branch_rejected", "workspace is not on its deterministic issue branch"
            )
        elif not lease_exists:
            ancestry = self._git(
                "merge-base",
                "--is-ancestor",
                f"refs/remotes/origin/{INTEGRATION_BASE}",
                "HEAD",
                check=False,
            )
            if ancestry.returncode:
                raise GitControlError(
                    "branch_base_rejected",
                    "unleased issue branch does not descend from accepted origin/v1.2-dev",
                )
        if not lease_exists:
            self._write_lease(identity)
        return {
            "issue_identifier": identity.issue_identifier,
            "branch": identity.branch,
            "base": f"origin/{INTEGRATION_BASE}",
            "head": self._head(),
        }

    def _require_issue_branch(self) -> WorkspaceIdentity:
        identity = self.identity()
        self._require_lease(identity)
        if self._current_branch() != identity.branch:
            raise GitControlError(
                "branch_rejected",
                "Git mutation requires the deterministic issue branch",
            )
        return identity

    def status(self) -> dict[str, Any]:
        identity = self._require_issue_branch()
        changed = self._changed_paths()
        return {
            "issue_identifier": identity.issue_identifier,
            "branch": identity.branch,
            "head": self._head(),
            "clean": not changed,
            "changed_files": changed,
        }

    def _changed_paths(self) -> list[str]:
        result = self._git("status", "--porcelain=v1", "-z", "--untracked-files=all")
        fields = result.stdout.split("\0")
        paths: list[str] = []
        index = 0
        while index < len(fields):
            field = fields[index]
            if not field:
                break
            if len(field) < 4:
                raise GitControlError(
                    "status_invalid", "Git status output is malformed"
                )
            paths.append(field[3:])
            if field[:2].strip() in {"R", "C"}:
                index += 1
                if index < len(fields) and fields[index]:
                    paths.append(fields[index])
            index += 1
        return sorted(set(paths))

    def _validate_paths(self, values: Any) -> list[str]:
        if not isinstance(values, list) or not values or len(values) > 100:
            raise GitControlError(
                "paths_invalid", "commit paths must be a non-empty bounded list"
            )
        checked: list[str] = []
        for value in values:
            if not isinstance(value, str) or not value or "\x00" in value:
                raise GitControlError("path_rejected", "commit path is invalid")
            path = PurePosixPath(value)
            if (
                path.is_absolute()
                or ".." in path.parts
                or any(part in PROTECTED_PARTS for part in path.parts)
            ):
                raise GitControlError("path_rejected", "commit path escapes policy")
            lowered = {part.lower() for part in path.parts}
            if (
                PRIVATE_NAMES & lowered
                or path.suffix.lower() in PRIVATE_SUFFIXES
                or any(part.startswith(".env.") for part in lowered)
            ):
                raise GitControlError(
                    "private_path_rejected",
                    "private or credential path cannot be committed",
                )
            candidate = self.workspace.joinpath(*path.parts)
            cursor = self.workspace
            for part in path.parts:
                cursor /= part
                if cursor.is_symlink():
                    raise GitControlError(
                        "path_symlink_rejected",
                        "symlink commit paths are not permitted",
                    )
            if candidate.exists() and not candidate.resolve().is_relative_to(
                self.workspace.resolve()
            ):
                raise GitControlError("path_rejected", "commit path escaped workspace")
            checked.append(path.as_posix())
        if len(set(checked)) != len(checked):
            raise GitControlError(
                "paths_invalid", "duplicate commit paths are not permitted"
            )
        return sorted(checked)

    def _receipt_path(
        self, identity: WorkspaceIdentity, kind: str, operation_id: str
    ) -> Path:
        if not OPERATION_PATTERN.fullmatch(operation_id):
            raise GitControlError("operation_id_invalid", "operation id is invalid")
        return (
            self.state_root
            / "operations"
            / identity.issue_identifier
            / f"{kind}-{operation_id}.json"
        )

    def _load_receipt(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise UnknownGitResult(
                "operation_unknown",
                "operation receipt is unreadable; operator review required",
            ) from exc
        if not isinstance(value, dict):
            raise UnknownGitResult(
                "operation_unknown",
                "operation receipt is invalid; operator review required",
            )
        return value

    def _fault(self, phase: str) -> None:
        if self.fault_injector:
            self.fault_injector(phase)

    def _commit_matches(self, receipt: dict[str, Any]) -> bool:
        if self._head() == receipt.get("pre_head"):
            return False
        result = self._git("show", "-s", "--format=%P%n%T", "HEAD").stdout.splitlines()
        return (
            len(result) == 2
            and result[0] == receipt.get("pre_head")
            and result[1] == receipt.get("expected_tree")
            and self._current_branch() == receipt.get("branch")
        )

    def _restore_clean_index(self) -> None:
        restored = self._git("read-tree", "--reset", "HEAD", check=False)
        if (
            restored.returncode
            or self._git("diff", "--cached", "--quiet", check=False).returncode
        ):
            raise UnknownGitResult(
                "index_restore_unknown",
                "staging failed and the index could not be restored; operator review required",
            )

    def _reconcile_commit(self, path: Path, receipt: dict[str, Any]) -> dict[str, Any]:
        if self._commit_matches(receipt):
            receipt.update(
                {"state": "applied", "head": self._head(), "reconciled": True}
            )
            _atomic_private_json(path, receipt)
            return {"status": "reconciled", "commit": receipt["head"]}
        if self._head() == receipt.get("pre_head"):
            raise UnknownGitResult(
                "commit_unknown",
                "commit result is unknown and was not replayed; operator review required",
            )
        raise UnknownGitResult(
            "commit_diverged",
            "repository changed after an uncertain commit; operator review required",
        )

    def commit(self, message: Any, paths: Any, operation_id: Any) -> dict[str, Any]:
        identity = self._require_issue_branch()
        if (
            not isinstance(message, str)
            or not 8 <= len(message) <= 120
            or message.strip() != message
            or "\n" in message
            or "\r" in message
        ):
            raise GitControlError(
                "commit_message_invalid",
                "commit message must be one bounded summary line",
            )
        if not isinstance(operation_id, str):
            raise GitControlError("operation_id_invalid", "operation id is required")
        checked_paths = self._validate_paths(paths)
        request_hash = hashlib.sha256(
            json.dumps(
                {"message": message, "paths": checked_paths},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        receipt_path = self._receipt_path(identity, "commit", operation_id)
        existing = self._load_receipt(receipt_path)
        if existing:
            if existing.get("request_sha256") != request_hash:
                raise GitControlError(
                    "operation_id_conflict",
                    "operation id was already used for a different commit request",
                )
            if existing.get("state") == "applied":
                return {"status": "already_applied", "commit": existing.get("head")}
            return self._reconcile_commit(receipt_path, existing)
        changed = set(self._changed_paths())
        if not changed or not set(checked_paths).issubset(changed):
            raise GitControlError(
                "path_scope_rejected",
                "every selected path must exactly identify a changed file",
            )
        pre_head = self._head()
        if self._git("diff", "--cached", "--quiet", check=False).returncode:
            raise GitControlError(
                "index_not_clean", "broker requires an initially unstaged Git index"
            )
        modes = self._git(
            "ls-files", "--stage", "--", *checked_paths
        ).stdout.splitlines()
        if any(line.startswith("160000 ") for line in modes):
            raise GitControlError(
                "submodule_rejected", "submodule changes are not permitted"
            )
        try:
            self._git("add", "-A", "--", *checked_paths)
            staged = [
                item
                for item in self._git(
                    "diff",
                    "--cached",
                    "--name-only",
                    "-z",
                    "--diff-filter=ACDMRTUXB",
                ).stdout.split("\0")
                if item
            ]
            if not staged:
                raise GitControlError(
                    "nothing_to_commit", "no selected changes were staged"
                )
            if not set(staged).issubset(set(checked_paths)):
                raise GitControlError(
                    "staging_scope_changed",
                    "staged paths exceeded the explicit commit selection",
                )
            expected_tree = self._git("write-tree").stdout.strip()
        except GitControlError:
            self._restore_clean_index()
            raise
        except _InjectedAmbiguity as exc:
            self._restore_clean_index()
            raise UnknownGitResult(
                "staging_unknown",
                "staging timed out and was restored without replay; operator review required",
            ) from exc
        receipt = {
            "schema_version": 1,
            "kind": "commit",
            "state": "pending",
            "operation_id": operation_id,
            "issue_identifier": identity.issue_identifier,
            "branch": identity.branch,
            "pre_head": pre_head,
            "expected_tree": expected_tree,
            "paths": staged,
            "message_sha256": hashlib.sha256(message.encode()).hexdigest(),
            "request_sha256": request_hash,
        }
        _atomic_private_json(receipt_path, receipt)
        try:
            result = self._git(
                "-c",
                "user.name=Sanctum Symphony",
                "-c",
                "user.email=symphony@localhost",
                "commit",
                "--no-gpg-sign",
                "--message",
                message,
                check=False,
            )
            self._fault("after_commit")
        except _InjectedAmbiguity:
            return self._reconcile_commit(receipt_path, receipt)
        if result.returncode:
            if self._commit_matches(receipt):
                return self._reconcile_commit(receipt_path, receipt)
            receipt["state"] = "failed"
            _atomic_private_json(receipt_path, receipt)
            self._restore_clean_index()
            raise GitControlError(
                "commit_failed",
                f"bounded commit failed with exit code {result.returncode}",
            )
        receipt.update({"state": "applied", "head": self._head(), "reconciled": False})
        _atomic_private_json(receipt_path, receipt)
        return {"status": "applied", "commit": receipt["head"], "paths": staged}

    def _remote_branch_head(self, identity: WorkspaceIdentity) -> str | None:
        result = self._git(
            "ls-remote",
            "--heads",
            "origin",
            f"refs/heads/{identity.branch}",
            check=False,
            credentialed=True,
        )
        if result.returncode:
            raise UnknownGitResult(
                "remote_state_unknown", "remote branch state could not be reconciled"
            )
        fields = result.stdout.strip().split()
        if not fields:
            return None
        if len(fields) != 2 or fields[1] != f"refs/heads/{identity.branch}":
            raise UnknownGitResult(
                "remote_state_unknown", "remote returned an unexpected branch identity"
            )
        return fields[0]

    def _reconcile_push(
        self, path: Path, receipt: dict[str, Any], identity: WorkspaceIdentity
    ) -> dict[str, Any]:
        remote_head = self._remote_branch_head(identity)
        if remote_head == receipt.get("local_head"):
            receipt.update({"state": "applied", "reconciled": True})
            _atomic_private_json(path, receipt)
            return {"status": "reconciled", "remote_head": remote_head}
        if remote_head == receipt.get("remote_head_before"):
            raise UnknownGitResult(
                "push_unknown",
                "push result is unknown and was not replayed; operator review required",
            )
        raise UnknownGitResult(
            "push_diverged", "remote branch changed; operator review required"
        )

    def push(self, operation_id: Any) -> dict[str, Any]:
        identity = self._require_issue_branch()
        if not isinstance(operation_id, str):
            raise GitControlError("operation_id_invalid", "operation id is required")
        if not self._clean():
            raise GitControlError("push_dirty", "push requires a clean issue workspace")
        receipt_path = self._receipt_path(identity, "push", operation_id)
        existing = self._load_receipt(receipt_path)
        if existing:
            if existing.get("state") == "applied":
                return {
                    "status": "already_applied",
                    "remote_head": existing.get("local_head"),
                }
            return self._reconcile_push(receipt_path, existing, identity)
        local_head = self._head()
        remote_head = self._remote_branch_head(identity)
        if remote_head == local_head:
            return {"status": "already_applied", "remote_head": remote_head}
        receipt = {
            "schema_version": 1,
            "kind": "push",
            "state": "pending",
            "operation_id": operation_id,
            "issue_identifier": identity.issue_identifier,
            "branch": identity.branch,
            "local_head": local_head,
            "remote_head_before": remote_head,
        }
        _atomic_private_json(receipt_path, receipt)
        try:
            result = self._git(
                "push",
                "--porcelain",
                "--set-upstream",
                "origin",
                f"refs/heads/{identity.branch}:refs/heads/{identity.branch}",
                check=False,
                timeout=120,
                credentialed=True,
            )
            self._fault("after_push")
        except _InjectedAmbiguity:
            return self._reconcile_push(receipt_path, receipt, identity)
        if result.returncode:
            try:
                return self._reconcile_push(receipt_path, receipt, identity)
            except UnknownGitResult as exc:
                if exc.code == "push_unknown":
                    receipt["state"] = "failed"
                    _atomic_private_json(receipt_path, receipt)
                    raise GitControlError(
                        "push_failed",
                        f"bounded push failed with exit code {result.returncode}",
                    ) from exc
                raise
        receipt.update({"state": "applied", "reconciled": False})
        _atomic_private_json(receipt_path, receipt)
        return {"status": "applied", "remote_head": local_head}

    def reconcile(self, kind: Any, operation_id: Any) -> dict[str, Any]:
        identity = self._require_issue_branch()
        if kind not in {"commit", "push"} or not isinstance(operation_id, str):
            raise GitControlError(
                "reconcile_invalid",
                "reconcile requires commit or push operation identity",
            )
        path = self._receipt_path(identity, kind, operation_id)
        receipt = self._load_receipt(path)
        if not receipt:
            raise GitControlError(
                "operation_missing", "operation receipt does not exist"
            )
        if receipt.get("state") == "applied":
            return {"status": "already_applied"}
        if kind == "commit":
            return self._reconcile_commit(path, receipt)
        return self._reconcile_push(path, receipt, identity)

    def _open_pull_request(self, identity: WorkspaceIdentity) -> dict[str, Any] | None:
        result = self._gh(
            "pr",
            "list",
            "--repo",
            CANONICAL_GITHUB_REPOSITORY,
            "--state",
            "open",
            "--head",
            identity.branch,
            "--json",
            "number,url,baseRefName,headRefName,headRefOid,headRepository,headRepositoryOwner,isDraft,title,body",
        )
        try:
            values = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GitControlError(
                "pull_request_response_invalid",
                "GitHub returned an invalid PR response",
            ) from exc
        if not isinstance(values, list):
            raise GitControlError(
                "pull_request_state_invalid", "GitHub PR state is ambiguous"
            )
        matching = [
            value
            for value in values
            if isinstance(value, dict)
            and value.get("baseRefName") == INTEGRATION_BASE
            and value.get("headRefName") == identity.branch
            and value.get("headRefOid") == self._head()
            and isinstance(value.get("headRepository"), dict)
            and value["headRepository"].get("nameWithOwner")
            == CANONICAL_GITHUB_REPOSITORY
            and isinstance(value.get("headRepositoryOwner"), dict)
            and value["headRepositoryOwner"].get("login") == CANONICAL_GITHUB_OWNER
        ]
        if len(matching) > 1:
            raise GitControlError(
                "pull_request_state_invalid", "GitHub PR state is ambiguous"
            )
        if not matching:
            return None
        value = matching[0]
        if type(value.get("number")) is not int or not isinstance(
            value.get("url"), str
        ):
            raise GitControlError(
                "pull_request_state_invalid", "open PR does not match the issue handoff"
            )
        return value

    def ensure_pull_request(self, title: Any, body: Any) -> dict[str, Any]:
        identity = self._require_issue_branch()
        if (
            not isinstance(title, str)
            or not 8 <= len(title) <= 120
            or title.strip() != title
            or "\n" in title
            or "\r" in title
        ):
            raise GitControlError(
                "pull_request_title_invalid",
                "PR title must be one bounded summary line",
            )
        if (
            not isinstance(body, str)
            or not 20 <= len(body) <= 4000
            or "\x00" in body
            or identity.issue_identifier not in body
        ):
            raise GitControlError(
                "pull_request_body_invalid",
                "PR body must be bounded and reference the issue identifier",
            )
        if not self._clean():
            raise GitControlError(
                "pull_request_dirty", "PR handoff requires a clean workspace"
            )
        local_head = self._head()
        if self._remote_branch_head(identity) != local_head:
            raise GitControlError(
                "pull_request_unpushed", "PR handoff requires the pushed local HEAD"
            )
        existing = self._open_pull_request(identity)
        if existing:
            if existing.get("title") != title or existing.get("body") != body:
                try:
                    self._gh(
                        "pr",
                        "edit",
                        str(existing["number"]),
                        "--repo",
                        CANONICAL_GITHUB_REPOSITORY,
                        "--title",
                        title,
                        "--body",
                        body,
                    )
                except _InjectedAmbiguity:
                    reconciled = self._open_pull_request(identity)
                    if (
                        not reconciled
                        or reconciled.get("title") != title
                        or reconciled.get("body") != body
                    ):
                        raise UnknownGitResult(
                            "pull_request_unknown",
                            "PR update result is unknown and was not replayed; operator review required",
                        )
            return {
                "status": "updated",
                "number": existing["number"],
                "url": existing["url"],
                "base": INTEGRATION_BASE,
                "head": identity.branch,
            }
        try:
            result = self._gh(
                "pr",
                "create",
                "--repo",
                CANONICAL_GITHUB_REPOSITORY,
                "--base",
                INTEGRATION_BASE,
                "--head",
                identity.branch,
                "--title",
                title,
                "--body",
                body,
                check=False,
            )
            if result.returncode:
                reconciled = self._open_pull_request(identity)
                if not reconciled:
                    raise GitControlError(
                        "pull_request_create_failed",
                        f"bounded PR creation failed with exit code {result.returncode}",
                    )
            else:
                reconciled = self._open_pull_request(identity)
        except _InjectedAmbiguity:
            reconciled = self._open_pull_request(identity)
        if not reconciled:
            raise UnknownGitResult(
                "pull_request_unknown",
                "PR creation result is unknown and was not replayed; operator review required",
            )
        return {
            "status": "created",
            "number": reconciled["number"],
            "url": reconciled["url"],
            "base": INTEGRATION_BASE,
            "head": identity.branch,
        }
