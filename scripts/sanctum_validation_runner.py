#!/usr/bin/env python3
"""MCP entry point for the bounded Sanctum host validation runner."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sanctum_agents.validation import (
    HostValidationRunner,
    ValidationError,
)  # noqa: E402

TOOL = {
    "name": "run_validation_profile",
    "description": "Run one reviewed validation profile in the leased issue workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "issue_id": {"type": "string", "pattern": "^[A-Z][A-Z0-9]*-[1-9][0-9]*$"},
            "workspace_id": {
                "type": "string",
                "pattern": "^[A-Z][A-Z0-9]*-[1-9][0-9]*$",
            },
            "profile": {
                "type": "string",
                "enum": ["docs-config", "normal-code", "architecture-security"],
            },
            "operation_id": {"type": "string", "minLength": 1, "maxLength": 80},
        },
        "required": ["issue_id", "workspace_id", "profile", "operation_id"],
        "additionalProperties": False,
    },
    "annotations": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
}


def runner() -> HostValidationRunner:
    workspace_root = os.environ.get("SYMPHONY_WORKSPACE_ROOT")
    git_state = os.environ.get("SANCTUM_GIT_BROKER_STATE")
    validation_state = os.environ.get("SANCTUM_VALIDATION_STATE")
    if not workspace_root or not git_state or not validation_state:
        raise ValidationError("reviewed validation environment is unavailable")
    return HostValidationRunner(
        Path.cwd(),
        Path(workspace_root),
        Path(git_state),
        Path(validation_state),
    )


def response(identifier: Any, result: Any = None, error: Any = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": identifier}
    if error is None:
        payload["result"] = result
    else:
        payload["error"] = error
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def serve_mcp() -> int:
    for raw in sys.stdin:
        try:
            request = json.loads(raw)
            identifier = request.get("id")
            method = request.get("method")
            if method == "initialize":
                response(
                    identifier,
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {
                            "name": "sanctum-validation",
                            "version": "1.0.0",
                        },
                    },
                )
            elif method == "notifications/initialized":
                continue
            elif method == "ping":
                response(identifier, {})
            elif method == "tools/list":
                response(identifier, {"tools": [TOOL]})
            elif method == "tools/call":
                params = request.get("params", {})
                if params.get("name") != TOOL["name"] or not isinstance(
                    params.get("arguments"), dict
                ):
                    raise ValidationError("unsupported validation tool request")
                arguments = params["arguments"]
                value = runner().run(
                    arguments.get("issue_id"),
                    arguments.get("workspace_id"),
                    arguments.get("profile"),
                    arguments.get("operation_id"),
                )
                response(
                    identifier,
                    {
                        "content": [
                            {"type": "text", "text": json.dumps(value, sort_keys=True)}
                        ],
                        "structuredContent": value,
                        "isError": False,
                    },
                )
            elif identifier is not None:
                response(
                    identifier,
                    error={"code": -32601, "message": "method not supported"},
                )
        except (json.JSONDecodeError, AttributeError):
            response(None, error={"code": -32700, "message": "invalid request"})
        except ValidationError as exc:
            response(
                locals().get("identifier"),
                {
                    "content": [{"type": "text", "text": str(exc)}],
                    "structuredContent": {"error": str(exc)},
                    "isError": True,
                },
            )
    return 0


def main() -> int:
    if sys.argv[1:] == ["mcp"]:
        return serve_mcp()
    raise SystemExit("usage: sanctum_validation_runner.py mcp")


if __name__ == "__main__":
    raise SystemExit(main())
