"""Hard total-runtime and workload supervisor for child processes."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from typing import Any, Callable

from .runtime import Budget, BudgetExceeded


@dataclass(frozen=True)
class ProcessResult:
    returncode: int | None
    reason: str
    output: str
    runtime_seconds: float
    counters: dict[str, int]


def _usage_value(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    method = payload.get("method")
    if method == "thread/tokenUsage/updated":
        node = payload.get("params", {}).get("tokenUsage", {}).get("total", {})
        value = node.get("totalTokens") if isinstance(node, dict) else None
        return value if type(value) is int and value >= 0 else None
    return None


def _is_turn(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("method") == "turn/started"


class BoundedProcess:
    def __init__(self, grace_seconds: float = 5, clock: Callable[[], float] = time.monotonic):
        self.grace_seconds = grace_seconds
        self.clock = clock

    @staticmethod
    def _stop(process: subprocess.Popen[bytes], grace_seconds: float) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()

    def run(
        self,
        command: list[str],
        cwd: Path,
        budget: Budget,
        *,
        env: dict[str, str] | None = None,
        stall_seconds: float | None = None,
        output_limit_bytes: int = 262144,
    ) -> ProcessResult:
        if not command or any(not isinstance(item, str) or not item for item in command):
            raise ValueError("command must contain non-empty strings")
        if output_limit_bytes <= 0:
            raise ValueError("output_limit_bytes must be positive")
        started = self.clock()
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            return ProcessResult(None, "spawn_failed", str(exc), 0, dict(budget.counters))
        assert process.stdout is not None
        os.set_blocking(process.stdout.fileno(), False)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        chunks: list[bytes] = []
        size = 0
        pending = b""
        last_activity = started
        highest_tokens = 0
        reason = "completed"
        try:
            while process.poll() is None:
                now = self.clock()
                try:
                    budget.check_time()
                except BudgetExceeded:
                    reason = "wall_clock_budget"
                    break
                if stall_seconds is not None and stall_seconds > 0 and now - last_activity > stall_seconds:
                    reason = "stall_budget"
                    break
                events = selector.select(0.1)
                if not events:
                    continue
                block = os.read(process.stdout.fileno(), 65536)
                if not block:
                    continue
                last_activity = now
                if size + len(block) > output_limit_bytes:
                    allowed = max(0, output_limit_bytes - size)
                    if allowed:
                        chunks.append(block[:allowed])
                    reason = "output_budget"
                    break
                chunks.append(block)
                size += len(block)
                pending += block
                lines = pending.split(b"\n")
                pending = lines.pop()
                for line in lines:
                    try:
                        payload = json.loads(line)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    try:
                        if _is_turn(payload):
                            budget.consume("turns")
                        tokens = _usage_value(payload)
                        if tokens is not None and tokens > highest_tokens:
                            budget.consume("tokens", tokens - highest_tokens)
                            highest_tokens = tokens
                    except BudgetExceeded as exc:
                        reason = f"{exc.reason}_budget"
                        break
                if reason != "completed":
                    break
        finally:
            selector.close()
            if reason != "completed":
                self._stop(process, self.grace_seconds)
            else:
                process.wait()
            if pending and size < output_limit_bytes:
                chunks.append(pending[: output_limit_bytes - size])
            process.stdout.close()
        return ProcessResult(
            process.returncode,
            reason,
            b"".join(chunks).decode("utf-8", errors="replace"),
            self.clock() - started,
            dict(budget.counters),
        )
