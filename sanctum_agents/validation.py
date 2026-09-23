"""Host-owned, profile-bounded validation for Symphony issue workspaces."""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .git_control_plane import GitControlError, GitControlPlane


class ValidationError(ValueError):
    """A validation request is malformed or outside the reviewed contract."""


ISSUE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*-[1-9][0-9]*$")
OPERATION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


@dataclass(frozen=True)
class ValidationCommand:
    name: str
    arguments: tuple[str, ...]
    timeout_seconds: int


_SOURCE = ValidationCommand("verify_source", ("/usr/bin/make", "verify-source"), 600)

_COMMON = (
    ValidationCommand("git_diff_check", ("/usr/bin/git", "diff", "--check"), 300),
    ValidationCommand("audit", ("/usr/bin/make", "audit"), 1200),
)

VALIDATION_PROFILES: dict[str, tuple[ValidationCommand, ...]] = {
    "docs-config": (_SOURCE, *_COMMON),
    "normal-code": (
        _SOURCE,
        ValidationCommand("build", ("/usr/bin/make", "build"), 1800),
        ValidationCommand("test", ("/usr/bin/make", "test"), 7200),
        *_COMMON,
    ),
    "architecture-security": (
        _SOURCE,
        ValidationCommand("deps", ("/usr/bin/make", "deps"), 1800),
        ValidationCommand("build", ("/usr/bin/make", "build"), 1800),
        ValidationCommand("test", ("/usr/bin/make", "test"), 7200),
        *_COMMON,
    ),
}

OPERATOR_BLOCKER_CODES = {
    "owner_prerequisite_missing",
    "environment_prerequisite_missing",
    "control_plane_reconciliation_required",
}


def _atomic_private_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


class HostValidationRunner:
    """Execute only reviewed validation profiles in a leased issue workspace."""

    def __init__(
        self,
        workspace: Path,
        workspace_root: Path,
        git_state_root: Path,
        validation_state_root: Path,
        *,
        expected_remote: str = "https://github.com/vnsparacio/sanctum.git",
    ) -> None:
        self.workspace = workspace.resolve(strict=False)
        self.workspace_root = workspace_root.resolve(strict=False)
        self.validation_state_root = validation_state_root.resolve(strict=False)
        if (
            self.validation_state_root == self.workspace_root
            or self.validation_state_root.is_relative_to(self.workspace_root)
            or self.validation_state_root.is_symlink()
        ):
            raise ValidationError(
                "validation state must remain outside issue workspaces"
            )
        self.validation_state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.validation_state_root.chmod(0o700)
        self.git = GitControlPlane(
            self.workspace,
            self.workspace_root,
            git_state_root,
            expected_remote=expected_remote,
        )

    def _identity(self, issue_id: Any, workspace_id: Any) -> dict[str, Any]:
        if not isinstance(issue_id, str) or not ISSUE_PATTERN.fullmatch(issue_id):
            raise ValidationError("issue_id is invalid")
        if workspace_id != issue_id:
            raise ValidationError("workspace_id must exactly match issue_id")
        try:
            status = self.git.status()
        except GitControlError as exc:
            raise ValidationError(f"leased workspace rejected: {exc}") from exc
        if status["issue_identifier"] != issue_id:
            raise ValidationError("workspace does not belong to the requested issue")
        return status

    def _workspace_fingerprint(self, status: dict[str, Any]) -> str:
        changed_files = status["changed_files"]
        if not isinstance(changed_files, list) or len(changed_files) > 500:
            raise ValidationError("workspace changed-file set is not bounded")
        result = subprocess.run(
            ["/usr/bin/git", "diff", "--raw", "-z", "HEAD"],
            cwd=self.workspace,
            env={
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "HOME": "/var/empty",
                "LANG": "C",
                "PATH": "/usr/bin:/bin",
            },
            text=False,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode:
            raise ValidationError("workspace fingerprint could not be computed")
        path_state: list[dict[str, str]] = []
        total_bytes = 0
        for relative in changed_files:
            path = PurePosixPath(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValidationError("workspace fingerprint path is invalid")
            candidate = self.workspace / relative
            try:
                metadata = candidate.lstat()
            except FileNotFoundError:
                path_state.append({"path": relative, "kind": "deleted"})
                continue
            if stat.S_ISLNK(metadata.st_mode):
                path_state.append(
                    {
                        "path": relative,
                        "kind": "symlink",
                        "sha256": hashlib.sha256(
                            os.readlink(candidate).encode()
                        ).hexdigest(),
                    }
                )
            elif stat.S_ISREG(metadata.st_mode):
                total_bytes += metadata.st_size
                if total_bytes > 256 * 1024 * 1024:
                    raise ValidationError("workspace fingerprint content is too large")
                digest = hashlib.sha256()
                with candidate.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                path_state.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "sha256": digest.hexdigest(),
                    }
                )
            else:
                path_state.append({"path": relative, "kind": "other"})
        value = {
            "head": status["head"],
            "changed_files": changed_files,
            "diff_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "path_state": path_state,
        }
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _environment(self, issue_id: str) -> dict[str, str]:
        runtime_home = self.validation_state_root / "runtime" / issue_id
        cache = runtime_home / "cache"
        runtime_home.mkdir(parents=True, exist_ok=True, mode=0o700)
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        return {
            "HOME": str(runtime_home),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "UV_CACHE_DIR": str(cache / "uv"),
            "XDG_CACHE_HOME": str(cache / "xdg"),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
        }

    def _run_command(
        self, command: ValidationCommand, environment: dict[str, str]
    ) -> dict[str, Any]:
        started = time.monotonic()
        process = subprocess.Popen(
            command.arguments,
            cwd=self.workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=command.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
        limit = 65536
        return {
            "name": command.name,
            "arguments": list(command.arguments),
            "exit_code": process.returncode,
            "timed_out": timed_out,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "stdout": stdout[-limit:].decode("utf-8", errors="replace"),
            "stderr": stderr[-limit:].decode("utf-8", errors="replace"),
            "output_truncated": len(stdout) > limit or len(stderr) > limit,
        }

    def run(
        self,
        issue_id: Any,
        workspace_id: Any,
        profile: Any,
        operation_id: Any,
    ) -> dict[str, Any]:
        if profile not in VALIDATION_PROFILES:
            raise ValidationError("profile is not approved")
        if not isinstance(operation_id, str) or not OPERATION_PATTERN.fullmatch(
            operation_id
        ):
            raise ValidationError("operation_id is invalid")
        status = self._identity(issue_id, workspace_id)
        fingerprint = self._workspace_fingerprint(status)
        receipt_path = (
            self.validation_state_root
            / "receipts"
            / issue_id
            / f"{profile}-{operation_id}.json"
        )
        intent = {
            "issue_id": issue_id,
            "workspace_id": workspace_id,
            "profile": profile,
            "operation_id": operation_id,
            "workspace_fingerprint": fingerprint,
        }
        if receipt_path.exists():
            try:
                existing = json.loads(receipt_path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise ValidationError("validation receipt is unreadable") from exc
            if any(existing.get(key) != value for key, value in intent.items()):
                raise ValidationError(
                    "operation_id cannot be reused for different validation intent"
                )
            return {
                "status": "already_completed",
                "passed": existing.get("passed", False),
                "receipt_id": existing.get("receipt_id"),
                "profile": profile,
                "commands": [
                    {
                        "name": item["name"],
                        "exit_code": item["exit_code"],
                        "timed_out": item["timed_out"],
                        "duration_ms": item["duration_ms"],
                    }
                    for item in existing.get("commands", [])
                ],
            }
        receipt_id = hashlib.sha256(
            f"{issue_id}:{profile}:{operation_id}".encode()
        ).hexdigest()[:24]
        receipt: dict[str, Any] = {
            "schema_version": 1,
            "receipt_id": receipt_id,
            **intent,
            "branch": status["branch"],
            "head": status["head"],
            "changed_files": status["changed_files"],
            "requested_at": datetime.now(UTC).isoformat(),
            "events": ["validation_requested"],
            "state": "running",
            "commands": [],
        }
        _atomic_private_json(receipt_path, receipt)
        environment = self._environment(issue_id)
        preflight = ValidationCommand(
            "process_inspection_preflight",
            ("/bin/ps", "-p", str(os.getpid()), "-o", "pid="),
            10,
        )
        commands = (
            (preflight, *VALIDATION_PROFILES[profile])
            if profile != "docs-config"
            else VALIDATION_PROFILES[profile]
        )
        for command in commands:
            result = self._run_command(command, environment)
            receipt["commands"].append(result)
            if result["exit_code"] != 0 or result["timed_out"]:
                if command.name == preflight.name:
                    receipt["events"].append("environment_preflight_failed")
                break
        completed_status = self._identity(issue_id, workspace_id)
        completed_fingerprint = self._workspace_fingerprint(completed_status)
        workspace_stable = completed_fingerprint == fingerprint
        receipt["passed"] = (
            len(receipt["commands"]) == len(commands)
            and all(
                item["exit_code"] == 0 and not item["timed_out"]
                for item in receipt["commands"]
            )
            and workspace_stable
        )
        receipt["completed_workspace_fingerprint"] = completed_fingerprint
        receipt["workspace_stable"] = workspace_stable
        receipt["state"] = "completed"
        receipt["completed_at"] = datetime.now(UTC).isoformat()
        if not workspace_stable:
            receipt["events"].append("workspace_changed_during_validation")
        receipt["events"].append("validation_completed")
        _atomic_private_json(receipt_path, receipt)
        return {
            "status": "completed",
            "passed": receipt["passed"],
            "receipt_id": receipt_id,
            "profile": profile,
            "workspace_fingerprint": fingerprint,
            "workspace_stable": workspace_stable,
            "commands": [
                {
                    "name": item["name"],
                    "exit_code": item["exit_code"],
                    "timed_out": item["timed_out"],
                    "duration_ms": item["duration_ms"],
                }
                for item in receipt["commands"]
            ],
        }

    def report_operator_blocker(
        self,
        issue_id: Any,
        workspace_id: Any,
        blocker_code: Any,
        operation_id: Any,
    ) -> dict[str, Any]:
        """Emit a bounded private signal for a deterministic owner checkpoint."""
        if blocker_code not in OPERATOR_BLOCKER_CODES:
            raise ValidationError("blocker_code is not approved")
        if not isinstance(operation_id, str) or not OPERATION_PATTERN.fullmatch(
            operation_id
        ):
            raise ValidationError("operation_id is invalid")
        status = self._identity(issue_id, workspace_id)
        receipt_path = (
            self.validation_state_root / "blockers" / issue_id / f"{operation_id}.json"
        )
        intent = {
            "issue_id": issue_id,
            "workspace_id": workspace_id,
            "blocker_code": blocker_code,
            "operation_id": operation_id,
        }
        receipt_id = hashlib.sha256(
            f"{issue_id}:{blocker_code}:{operation_id}".encode()
        ).hexdigest()[:24]
        if receipt_path.exists():
            try:
                receipt = json.loads(receipt_path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                raise ValidationError("operator blocker receipt is unreadable") from exc
            if any(receipt.get(key) != value for key, value in intent.items()):
                raise ValidationError(
                    "operation_id cannot be reused for a different operator blocker"
                )
        else:
            receipt = {
                "schema_version": 1,
                "receipt_id": receipt_id,
                **intent,
                "event": "operator_action_required",
                "state": "reported",
            }
        receipt.update(
            {
                "branch": status["branch"],
                "head": status["head"],
                "reported_at": datetime.now(UTC).isoformat(),
            }
        )
        _atomic_private_json(receipt_path, receipt)
        return {
            "status": "reported",
            "receipt_id": receipt_id,
            "blocker_code": blocker_code,
        }
