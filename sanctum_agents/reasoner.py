"""Authenticated, schema-constrained Codex invocation for management roles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ModelConfig
from .integrations import ExternalCallError
from .runtime import Budget
from .supervisor import BoundedProcess, ProcessResult


class CodexReasoner:
    def __init__(
        self, command: str = "codex", supervisor: BoundedProcess | None = None
    ):
        self.command = command
        self.supervisor = supervisor or BoundedProcess()

    @staticmethod
    def _final_message(output: str) -> dict[str, Any]:
        messages: list[str] = []
        for line in output.splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("type") != "item.completed":
                continue
            item = payload.get("item")
            if (
                isinstance(item, dict)
                and item.get("type") == "agent_message"
                and isinstance(item.get("text"), str)
            ):
                messages.append(item["text"])
        if not messages:
            raise ExternalCallError("Codex returned no final agent message")
        try:
            result = json.loads(messages[-1])
        except json.JSONDecodeError as exc:
            raise ExternalCallError("Codex final response was not valid JSON") from exc
        if not isinstance(result, dict):
            raise ExternalCallError("Codex final response was not a JSON object")
        return result

    def run(
        self,
        prompt: str,
        model: ModelConfig,
        schema: Path,
        cwd: Path,
        budget: Budget,
        output_limit_bytes: int,
        *,
        enable_search: bool = False,
    ) -> tuple[dict[str, Any], ProcessResult]:
        command = [self.command]
        if enable_search:
            command.append("--search")
        command.extend(
            [
                "exec",
                "--json",
                "--ephemeral",
                "--ignore-user-config",
                "--skip-git-repo-check",
                "--strict-config",
                "-m",
                model.model,
                "-c",
                f'model_reasoning_effort="{model.reasoning}"',
                "-s",
                "read-only",
                "-C",
                str(cwd),
                "--output-schema",
                str(schema),
                prompt,
            ]
        )
        result = self.supervisor.run(
            command,
            cwd,
            budget,
            stall_seconds=None,
            output_limit_bytes=output_limit_bytes,
        )
        if result.reason != "completed" or result.returncode != 0:
            diagnostic = result.output[-2000:].strip()
            detail = f": {diagnostic}" if diagnostic else ""
            raise ExternalCallError(
                f"Codex stopped with {result.reason} (exit {result.returncode}){detail}"
            )
        return self._final_message(result.output), result
