"""Bounded bridge from a scoped Linear issue to host-owned Qwen Work Mode."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from .work_linear import WORKPAD_HEADING, WorkLinearOperations
from .work_workspaces import TaskWorkspace, WorkWorkspaceManager


class WorkModeBridgeError(RuntimeError):
    """The issue packet, checkpoint, or host binding failed closed."""


PACKET_SCHEMA = "sanctum-qwen-work-mode-issue-packet/v1"
CHECKPOINT_SCHEMA = "sanctum-qwen-work-mode-checkpoint/v1"
MAX_PACKET_BYTES = 65_536
_OPERATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
_COMMIT = re.compile(r"[a-f0-9]{40}")


@dataclass(frozen=True)
class WorkModeBudget:
    """Host-selected limits supplied to Qwen as facts, never task instructions."""

    worker_class: str
    model: str
    reasoning_effort: str
    wall_clock_seconds: int
    max_turns: int
    max_tokens: int

    def __post_init__(self) -> None:
        if self.worker_class not in {"standard", "deep"}:
            raise WorkModeBridgeError("invalid Work Mode worker class")
        if (
            type(self.model) is not str
            or not self.model.strip()
            or self.model.strip() != self.model
            or len(self.model) > 128
            or any(ord(character) < 32 for character in self.model)
        ):
            raise WorkModeBridgeError("invalid Work Mode model")
        if self.reasoning_effort not in {
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
            "ultra",
        }:
            raise WorkModeBridgeError("invalid Work Mode reasoning effort")
        for name in ("wall_clock_seconds", "max_turns", "max_tokens"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise WorkModeBridgeError(f"invalid Work Mode {name}")


@dataclass(frozen=True)
class WorkModeAuthority:
    """Fixed host authority facts; issue/model content cannot alter these values."""

    owner: str = "MAC_HOST"
    issue_scope_fixed: bool = True
    branch_scope_fixed: bool = True
    may_set_execution_gate: bool = False
    may_change_worker_class: bool = False
    may_merge: bool = False
    may_move_to_done: bool = False
    human_review_required: bool = True


@dataclass(frozen=True)
class WorkModeInvocation:
    packet: Mapping[str, Any]
    resumed: bool
    completed_operations: tuple[str, ...]


class QwenWorkModeBackend(Protocol):
    """Proposal-only Qwen adapter implemented by the private Work Mode runtime."""

    def invoke(self, invocation: WorkModeInvocation) -> Mapping[str, Any]: ...


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _text(value: Any, label: str, maximum: int) -> str:
    if (
        type(value) is not str
        or not value.strip()
        or value.strip() != value
        or len(value) > maximum
        or any(ord(character) < 32 and character not in "\n\r\t" for character in value)
    ):
        raise WorkModeBridgeError(f"invalid or oversized {label}")
    return value


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


class WorkModeCheckpoint:
    """Private durable idempotency state for one immutable issue run."""

    def __init__(self, state_root: Path, task_id: str, binding: Mapping[str, Any]):
        if (
            not state_root.is_absolute()
            or state_root.is_symlink()
            or not state_root.is_dir()
            or state_root.resolve(strict=True) != state_root
            or not _OPERATION_ID.fullmatch(task_id)
        ):
            raise WorkModeBridgeError("invalid Work Mode checkpoint location")
        self.root = state_root / "work-mode-checkpoints"
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.root.chmod(0o700)
        if (
            self.root.is_symlink()
            or self.root.resolve(strict=True).parent != state_root
        ):
            raise WorkModeBridgeError("Work Mode checkpoint root escaped private state")
        self.path = self.root / f"{task_id}.json"
        self.binding = json.loads(json.dumps(binding))
        self.binding_digest = _digest(self.binding)
        self.resumed = self.path.exists() or self.path.is_symlink()
        if self.resumed:
            self._load()
        else:
            self._save({})

    def _load(self) -> dict[str, Any]:
        if (
            self.path.is_symlink()
            or not self.path.is_file()
            or self.path.stat().st_mode & 0o077
        ):
            raise WorkModeBridgeError("Work Mode checkpoint is unsafe")
        try:
            value = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkModeBridgeError("Work Mode checkpoint is unreadable") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema") != CHECKPOINT_SCHEMA
            or value.get("binding") != self.binding
            or value.get("binding_digest") != self.binding_digest
            or not isinstance(value.get("operations"), dict)
        ):
            raise WorkModeBridgeError("Work Mode checkpoint binding changed")
        return value

    def _save(self, operations: Mapping[str, Any]) -> None:
        _atomic_private_json(
            self.path,
            {
                "schema": CHECKPOINT_SCHEMA,
                "binding": self.binding,
                "binding_digest": self.binding_digest,
                "operations": operations,
            },
        )

    @property
    def completed_operations(self) -> tuple[str, ...]:
        operations = self._load()["operations"]
        return tuple(
            sorted(
                operation_id
                for operation_id, operation in operations.items()
                if isinstance(operation, dict) and operation.get("state") == "completed"
            )
        )

    def perform(
        self,
        operation_id: str,
        kind: str,
        intent: Mapping[str, Any],
        invoke: Callable[[], Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Run once; pending replay uses the same identity for host reconciliation."""

        if not _OPERATION_ID.fullmatch(operation_id):
            raise WorkModeBridgeError("invalid Work Mode operation ID")
        checked_kind = _text(kind, "Work Mode operation kind", 80)
        intent_digest = _digest(intent)
        value = self._load()
        operations = value["operations"]
        existing = operations.get(operation_id)
        if existing is not None:
            if (
                not isinstance(existing, dict)
                or existing.get("kind") != checked_kind
                or existing.get("intent_digest") != intent_digest
            ):
                raise WorkModeBridgeError(
                    "Work Mode operation ID was reused for different intent"
                )
            if existing.get("state") == "completed":
                receipt = existing.get("receipt")
                if not isinstance(receipt, dict):
                    raise WorkModeBridgeError(
                        "Work Mode operation receipt is malformed"
                    )
                return receipt
            if existing.get("state") != "pending":
                raise WorkModeBridgeError("Work Mode operation state is malformed")
        else:
            operations[operation_id] = {
                "state": "pending",
                "kind": checked_kind,
                "intent_digest": intent_digest,
            }
            self._save(operations)
        receipt = invoke()
        if not isinstance(receipt, Mapping):
            raise WorkModeBridgeError("Work Mode host operation returned no receipt")
        serializable = json.loads(json.dumps(dict(receipt)))
        operations = self._load()["operations"]
        current = operations.get(operation_id)
        if (
            not isinstance(current, dict)
            or current.get("kind") != checked_kind
            or current.get("intent_digest") != intent_digest
            or current.get("state") != "pending"
        ):
            raise WorkModeBridgeError("Work Mode operation checkpoint changed")
        operations[operation_id] = {
            **current,
            "state": "completed",
            "receipt": serializable,
        }
        self._save(operations)
        return serializable


class WorkModeBridge:
    """Compose fixed Linear/workspace scopes into one bounded Qwen invocation."""

    def __init__(
        self,
        linear: WorkLinearOperations,
        workspaces: WorkWorkspaceManager,
        state_root: Path,
        project_id: str,
        task_id: str,
        budget: WorkModeBudget,
    ) -> None:
        if not isinstance(linear, WorkLinearOperations):
            raise WorkModeBridgeError("scoped Work Mode Linear operations required")
        if not isinstance(workspaces, WorkWorkspaceManager):
            raise WorkModeBridgeError("host Work Mode workspace manager required")
        self.linear = linear
        self.workspaces = workspaces
        self.project_id = _text(project_id, "Work Mode project ID", 64)
        self.task_id = _text(task_id, "Work Mode task ID", 64)
        self.budget = budget
        self.authority = WorkModeAuthority()
        expected_branch = f"symphony/{linear.scope.identifier.lower()}"
        self.binding = {
            "issue_id": linear.scope.issue_id,
            "issue_identifier": linear.scope.identifier,
            "linear_project_id": linear.scope.project_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "repository": linear.scope.repository,
            "branch": expected_branch,
            "budget": asdict(budget),
            "authority": asdict(self.authority),
        }
        self.checkpoint = WorkModeCheckpoint(state_root, task_id, self.binding)

    @staticmethod
    def _workspace_receipt(workspace: TaskWorkspace) -> Mapping[str, Any]:
        return {
            "project_id": workspace.project_id,
            "task_id": workspace.task_id,
            "root": str(workspace.root),
            "repository": workspace.repository,
            "base_branch": workspace.base_branch,
            "base_commit": workspace.base_commit,
        }

    @staticmethod
    def _workspace_from_receipt(
        receipt: Mapping[str, Any], resumed: bool
    ) -> TaskWorkspace:
        try:
            return TaskWorkspace(
                project_id=receipt["project_id"],
                task_id=receipt["task_id"],
                root=Path(receipt["root"]),
                repository=receipt["repository"],
                base_branch=receipt["base_branch"],
                base_commit=receipt["base_commit"],
                resumed=resumed,
            )
        except (KeyError, TypeError) as exc:
            raise WorkModeBridgeError(
                "workspace checkpoint receipt is malformed"
            ) from exc

    def _issue_packet(
        self,
        issue: Mapping[str, Any],
        workspace: TaskWorkspace,
        branch: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        state = issue.get("state")
        project = issue.get("project")
        labels = issue.get("labels")
        comments = issue.get("comments")
        if not all(
            isinstance(value, Mapping) for value in (state, project, labels, comments)
        ):
            raise WorkModeBridgeError("scoped issue packet metadata is malformed")
        label_nodes = labels.get("nodes")
        comment_nodes = comments.get("nodes")
        if not isinstance(label_nodes, list) or len(label_nodes) > 32:
            raise WorkModeBridgeError("issue label packet is unbounded")
        label_names = []
        for item in label_nodes:
            if not isinstance(item, Mapping):
                raise WorkModeBridgeError("issue label packet is malformed")
            label_names.append(_text(item.get("name"), "issue label", 80))
        expected_route = f"agent-{self.budget.worker_class}"
        routes = set(label_names) & {"agent-standard", "agent-deep"}
        if (
            state.get("name") != "In Progress"
            or "symphony" not in label_names
            or routes != {expected_route}
        ):
            raise WorkModeBridgeError(
                "issue is outside the active host-authorized scope"
            )
        if not isinstance(comment_nodes, list) or len(comment_nodes) > 100:
            raise WorkModeBridgeError("issue Workpad packet is unbounded")
        workpads = [
            item
            for item in comment_nodes
            if isinstance(item, Mapping)
            and type(item.get("body")) is str
            and item["body"].splitlines()[:1] == [WORKPAD_HEADING]
        ]
        if len(workpads) != 1:
            raise WorkModeBridgeError("one stable Codex Workpad is required")
        workpad = workpads[0]
        workpad_id = _text(workpad.get("id"), "Workpad ID", 128)
        workpad_body = _text(workpad.get("body"), "Workpad body", 32_000)
        title = _text(issue.get("title"), "issue title", 500)
        description = _text(issue.get("description"), "issue description", 16_000)
        if project.get("id") != self.linear.scope.project_id:
            raise WorkModeBridgeError("issue project scope changed")
        packet = {
            "schema": PACKET_SCHEMA,
            "issue": {
                "id": self.linear.scope.issue_id,
                "identifier": self.linear.scope.identifier,
                "title": title,
                "description": description,
                "state": "In Progress",
                "labels": sorted(label_names),
                "project_id": self.linear.scope.project_id,
                "workpad": {
                    "comment_id": workpad_id,
                    "body": workpad_body,
                    "digest": hashlib.sha256(workpad_body.encode()).hexdigest(),
                },
            },
            "workspace": {
                "project_id": workspace.project_id,
                "task_id": workspace.task_id,
                "repository": workspace.repository,
                "base_branch": workspace.base_branch,
                "base_commit": workspace.base_commit,
                "branch": branch.get("branch"),
                "head": branch.get("head"),
            },
            "budget": asdict(self.budget),
            "authority": asdict(self.authority),
            "resume": {
                "resumed": self.checkpoint.resumed,
                "completed_operations": list(self.checkpoint.completed_operations),
            },
        }
        if (
            workspace.project_id != self.project_id
            or workspace.task_id != self.task_id
            or workspace.repository != self.linear.scope.repository
            or branch.get("branch") != self.binding["branch"]
            or branch.get("base_commit") != workspace.base_commit
            or not _COMMIT.fullmatch(str(workspace.base_commit))
            or not _COMMIT.fullmatch(str(branch.get("head", "")))
        ):
            raise WorkModeBridgeError("workspace or branch scope changed")
        encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > MAX_PACKET_BYTES:
            raise WorkModeBridgeError("Qwen Work Mode issue packet exceeds its bound")
        return packet

    def prepare(self) -> WorkModeInvocation:
        """Prepare or resume the exact issue/workspace without replaying completed steps."""

        begin = self.checkpoint.perform(
            "linear-begin",
            "linear_begin_implementation",
            {"worker_class": self.budget.worker_class},
            lambda: self.linear.begin_implementation(self.budget.worker_class),
        )
        if begin.get("state_id") is None:
            raise WorkModeBridgeError("Linear begin checkpoint lacks state evidence")
        workspace_receipt = self.checkpoint.perform(
            "workspace-create",
            "workspace_create_or_resume",
            {"project_id": self.project_id, "task_id": self.task_id},
            lambda: self._workspace_receipt(
                self.workspaces.create(self.project_id, self.task_id)
            ),
        )
        workspace = self._workspace_from_receipt(
            workspace_receipt, self.checkpoint.resumed
        )
        branch = self.checkpoint.perform(
            "branch-establish",
            "workspace_establish_issue_branch",
            {"issue_identifier": self.linear.scope.identifier},
            lambda: self.workspaces.establish_branch(
                workspace, self.linear.scope.identifier
            ),
        )
        issue = self.linear.fetch_issue()
        packet = self._issue_packet(issue, workspace, branch)
        return WorkModeInvocation(
            packet=packet,
            resumed=self.checkpoint.resumed,
            completed_operations=self.checkpoint.completed_operations,
        )

    def invoke(self, backend: QwenWorkModeBackend) -> Mapping[str, Any]:
        """Send only the bounded packet/resume facts to the configured Qwen backend."""

        if not callable(getattr(backend, "invoke", None)):
            raise WorkModeBridgeError("Qwen Work Mode backend is unavailable")
        result = backend.invoke(self.prepare())
        if not isinstance(result, Mapping):
            raise WorkModeBridgeError("Qwen Work Mode backend returned no result")
        return result
