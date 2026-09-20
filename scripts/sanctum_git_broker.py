#!/usr/bin/env python3
"""CLI/MCP entry point for the Sanctum Symphony Git control plane."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sanctum_agents.git_control_plane import (  # noqa: E402
    GitControlError,
    GitControlPlane,
)


def control_plane() -> GitControlPlane:
    workspace_root = os.environ.get("SYMPHONY_WORKSPACE_ROOT")
    state_root = os.environ.get("SANCTUM_GIT_BROKER_STATE")
    if not workspace_root or not state_root:
        raise GitControlError(
            "broker_environment_invalid", "reviewed broker environment is unavailable"
        )
    return GitControlPlane(
        Path.cwd(),
        Path(workspace_root),
        Path(state_root),
        credential_helper=os.environ.get("SANCTUM_GIT_CREDENTIAL_HELPER"),
        github_config_dir=os.environ.get("SANCTUM_GIT_GH_CONFIG_DIR"),
    )


TOOLS = [
    {
        "name": "git_workspace_status",
        "description": "Read the validated current issue branch and changed-file status.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "git_commit_issue_changes",
        "description": "Commit explicitly selected files on the deterministic issue branch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "minLength": 8, "maxLength": 120},
                "paths": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 100,
                    "items": {"type": "string"},
                },
                "operation_id": {"type": "string", "minLength": 1, "maxLength": 80},
            },
            "required": ["message", "paths", "operation_id"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    },
    {
        "name": "git_push_issue_branch",
        "description": "Normally push only the deterministic issue branch to origin.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation_id": {"type": "string", "minLength": 1, "maxLength": 80}
            },
            "required": ["operation_id"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    },
    {
        "name": "git_reconcile_operation",
        "description": "Reconcile an uncertain commit or push receipt without replaying it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["commit", "push"]},
                "operation_id": {"type": "string", "minLength": 1, "maxLength": 80},
            },
            "required": ["kind", "operation_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "github_ensure_issue_pull_request",
        "description": "Create or update the unmerged issue PR targeting v1.3-dev.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "minLength": 8, "maxLength": 120},
                "body": {"type": "string", "minLength": 20, "maxLength": 4000},
            },
            "required": ["title", "body"],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    },
]


def call_tool(name: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise GitControlError("arguments_invalid", "tool arguments must be an object")
    broker = control_plane()
    if name == "git_workspace_status" and not arguments:
        return broker.status()
    if name == "git_commit_issue_changes":
        return broker.commit(
            arguments.get("message"),
            arguments.get("paths"),
            arguments.get("operation_id"),
        )
    if name == "git_push_issue_branch":
        return broker.push(arguments.get("operation_id"))
    if name == "git_reconcile_operation":
        return broker.reconcile(arguments.get("kind"), arguments.get("operation_id"))
    if name == "github_ensure_issue_pull_request":
        return broker.ensure_pull_request(arguments.get("title"), arguments.get("body"))
    raise GitControlError("tool_unsupported", "unsupported Git control-plane operation")


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
            method = request.get("method")
            identifier = request.get("id")
            if method == "initialize":
                response(
                    identifier,
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "sanctum-git", "version": "1.0.0"},
                    },
                )
            elif method == "notifications/initialized":
                continue
            elif method == "ping":
                response(identifier, {})
            elif method == "tools/list":
                response(identifier, {"tools": TOOLS})
            elif method == "tools/call":
                params = request.get("params", {})
                try:
                    value = call_tool(params.get("name"), params.get("arguments", {}))
                    response(
                        identifier,
                        {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(value, sort_keys=True),
                                }
                            ],
                            "structuredContent": value,
                            "isError": False,
                        },
                    )
                except GitControlError as exc:
                    value = {"error": {"code": exc.code, "message": str(exc)}}
                    response(
                        identifier,
                        {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(value, sort_keys=True),
                                }
                            ],
                            "structuredContent": value,
                            "isError": True,
                        },
                    )
            elif identifier is not None:
                response(
                    identifier,
                    error={"code": -32601, "message": "method not supported"},
                )
        except (json.JSONDecodeError, AttributeError):
            response(None, error={"code": -32700, "message": "invalid request"})
    return 0


def main() -> int:
    if sys.argv[1:] == ["prepare"]:
        print(json.dumps(control_plane().prepare(), sort_keys=True))
        return 0
    if sys.argv[1:] == ["mcp"]:
        return serve_mcp()
    raise SystemExit("usage: sanctum_git_broker.py prepare|mcp")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GitControlError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}))
        raise SystemExit(2) from None
