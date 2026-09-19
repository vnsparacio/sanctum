"""Narrow authenticated integration adapters with no credential persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import subprocess
import time
from typing import Any
from urllib import error, request


class ExternalCallError(RuntimeError):
    """An external tool or service failed with a sanitized reason."""


class MissingAuth(ExternalCallError):
    """Required host-side authentication is unavailable."""


class CodexCatalogClient:
    """Read the authenticated Codex model catalog through app-server v2."""

    def __init__(self, command: tuple[str, ...] = ("codex", "app-server", "--stdio")):
        self.command = command

    def list_models(self, timeout_seconds: float = 10) -> list[dict[str, Any]]:
        try:
            process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise ExternalCallError("codex app-server is unavailable") from exc
        assert process.stdin is not None and process.stdout is not None
        messages = (
            {"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "sanctum-agents", "version": "1"},
                "capabilities": {"experimentalApi": True},
            }},
            {"method": "initialized", "params": {}},
            {"id": 2, "method": "model/list", "params": {"includeHidden": True, "limit": 100}},
        )
        for message in messages:
            process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + timeout_seconds
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while time.monotonic() < deadline:
                events = selector.select(max(0, deadline - time.monotonic()))
                if not events:
                    break
                line = process.stdout.readline()
                if not line:
                    break
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("id") == 2:
                    if "error" in payload:
                        raise ExternalCallError("Codex model catalog request failed")
                    data = payload.get("result", {}).get("data")
                    if not isinstance(data, list):
                        raise ExternalCallError("Codex model catalog response was malformed")
                    return data
            raise ExternalCallError("Codex model catalog request timed out")
        finally:
            selector.close()
            try:
                process.stdin.close()
            except OSError:
                pass
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


class LinearGraphQLClient:
    """Minimal Linear GraphQL client using one host-side environment token."""

    def __init__(
        self,
        token_env: str = "LINEAR_API_KEY",
        endpoint: str = "https://api.linear.app/graphql",
        environ: dict[str, str] | None = None,
    ):
        self.token_env = token_env
        self.endpoint = endpoint
        self.environ = os.environ if environ is None else environ

    def query(self, query: str, variables: dict[str, Any] | None = None, timeout: float = 15) -> dict[str, Any]:
        token = self.environ.get(self.token_env)
        if not token:
            raise MissingAuth(f"Linear authentication is unavailable in {self.token_env}")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Linear query must be non-empty")
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        outbound = request.Request(
            self.endpoint,
            data=body,
            headers={"Authorization": token, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(outbound, timeout=timeout) as response:
                payload = json.loads(response.read())
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ExternalCallError("Linear request failed") from exc
        if not isinstance(payload, dict):
            raise ExternalCallError("Linear response was malformed")
        if payload.get("errors"):
            raise ExternalCallError("Linear returned GraphQL errors")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ExternalCallError("Linear response did not contain data")
        return data


class GitHubClient:
    """Read GitHub state through the already-authenticated GitHub CLI."""

    def __init__(self, repository: str, command: str = "gh"):
        self.repository = repository
        self.command = command

    def run_json(self, args: list[str], timeout: float = 20) -> Any:
        if any(not isinstance(item, str) or not item for item in args):
            raise ValueError("GitHub arguments must be non-empty strings")
        try:
            completed = subprocess.run(
                [self.command, *args, "--repo", self.repository],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExternalCallError("GitHub CLI request failed") from exc
        if completed.returncode:
            raise MissingAuth("GitHub CLI is unavailable or not authorized")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ExternalCallError("GitHub CLI returned malformed JSON") from exc

    def pull_request(self, number: int) -> dict[str, Any]:
        if type(number) is not int or number <= 0:
            raise ValueError("pull request number must be positive")
        result = self.run_json([
            "pr", "view", str(number),
            "--json", "number,title,state,baseRefName,headRefName,url,mergeable,statusCheckRollup",
        ])
        if not isinstance(result, dict):
            raise ExternalCallError("GitHub PR response was malformed")
        return result


def repository_status(repository: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout
