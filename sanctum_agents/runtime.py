"""Run IDs, private state, exclusive locks, budgets, and structured logs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import json
import os
from pathlib import Path
import time
from typing import Any, Callable
import uuid


class RunMode(StrEnum):
    DRY_RUN = "dry-run"
    SHADOW = "shadow"
    LIVE = "live"


class BudgetExceeded(RuntimeError):
    def __init__(self, reason: str, observed: int | float, limit: int | float):
        super().__init__(f"budget exceeded: {reason} observed={observed} limit={limit}")
        self.reason = reason
        self.observed = observed
        self.limit = limit


@dataclass
class Budget:
    wall_clock_seconds: int
    max_items: int
    max_sources: int
    max_retries: int
    max_turns: int
    max_tokens: int
    clock: Callable[[], float] = time.monotonic
    started_at: float = field(init=False)
    counters: dict[str, int] = field(default_factory=lambda: {
        "items": 0,
        "sources": 0,
        "retries": 0,
        "turns": 0,
        "tokens": 0,
    })

    def __post_init__(self) -> None:
        self.started_at = self.clock()

    @property
    def deadline(self) -> float:
        return self.started_at + self.wall_clock_seconds

    def check_time(self) -> None:
        elapsed = self.clock() - self.started_at
        if elapsed > self.wall_clock_seconds:
            raise BudgetExceeded("wall_clock_seconds", elapsed, self.wall_clock_seconds)

    def consume(self, counter: str, amount: int = 1) -> int:
        if counter not in self.counters or type(amount) is not int or amount < 0:
            raise ValueError("unknown counter or invalid amount")
        self.check_time()
        self.counters[counter] += amount
        limit = getattr(self, f"max_{counter}")
        if self.counters[counter] > limit:
            raise BudgetExceeded(counter, self.counters[counter], limit)
        return self.counters[counter]


def new_run_id(role: str, now: float | None = None) -> str:
    timestamp = time.time() if now is None else now
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(timestamp))
    return f"{role}-{stamp}-{uuid.uuid4().hex[:12]}"


def ensure_private_prefix(path: Path) -> None:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    if current.is_symlink():
        raise RuntimeError("agent runtime prefix may not traverse a symlink")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise RuntimeError("agent runtime prefix may not be a symlink")
    path.chmod(0o700)
    for name in ("locks", "logs", "state", "shadow"):
        child = path / name
        child.mkdir(exist_ok=True, mode=0o700)
        child.chmod(0o700)


class ExclusiveRoleLock:
    def __init__(self, path: Path, stale_seconds: int, clock: Callable[[], float] = time.time):
        self.path = path
        self.stale_seconds = stale_seconds
        self.clock = clock
        self.acquired = False

    @staticmethod
    def _alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def acquire(self, run_id: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {"pid": os.getpid(), "run_id": run_id, "created_at": self.clock()}
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                try:
                    current = json.loads(self.path.read_text())
                    age = self.clock() - float(current["created_at"])
                    pid = int(current["pid"])
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"invalid existing lock {self.path}: {exc}") from exc
                if age <= self.stale_seconds or self._alive(pid):
                    raise RuntimeError(f"role already running: {self.path.name}")
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                continue
            with os.fdopen(fd, "w") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
            self.acquired = True
            return
        raise RuntimeError(f"could not acquire role lock: {self.path}")

    def release(self) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self.acquired = False

    def __enter__(self) -> "ExclusiveRoleLock":
        if not self.acquired:
            raise RuntimeError("acquire the role lock before entering")
        return self

    def acquired_for(self, run_id: str) -> "ExclusiveRoleLock":
        self.acquire(run_id)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()


class JsonlRunLog:
    def __init__(self, path: Path, run_id: str, role: str, mode: RunMode):
        self.path = path
        self.run_id = run_id
        self.role = role
        self.mode = mode
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    def emit(self, event: str, **fields: Any) -> None:
        record = {
            **fields,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": self.run_id,
            "role": self.role,
            "mode": self.mode.value,
            "event": event,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
        self.path.chmod(0o600)
