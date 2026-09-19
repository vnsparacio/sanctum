"""Isolated pinned Docker MCP profile; only three reviewed tools, no arbitrary args."""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location(
    "release_operator", ROOT / "scripts/release_operator.py"
)
op = importlib.util.module_from_spec(s)
s.loader.exec_module(op)


def signature(profile):
    return (
        profile.get("id"),
        profile.get("secrets"),
        [
            (
                v.get("secrets"),
                v.get("type"),
                v.get("image"),
                v.get("endpoint"),
                v.get("tools"),
                v.get("snapshot", {}).get("server", {}),
            )
            for v in profile["servers"]
        ],
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["install", "run"])
    p.add_argument("--prefix", type=Path, required=True)
    a = p.parse_args()
    prefix = a.prefix.absolute()
    op.verify()
    op.verify_install(prefix)
    profile = json.loads((prefix / "config/mcp-profile.json").read_text())
    if not profile["id"].startswith("sanctum-"):
        raise SystemExit("Configure the isolated MCP integration first")
    docker = (
        shutil.which("docker")
        or "/Applications/Docker.app/Contents/Resources/bin/docker"
    )
    env = op.environment(prefix)
    env["MCP_GATEWAY_DOCKER_BIND_ALLOWED_PATHS"] = str(prefix / "mcp-input")
    result = subprocess.run(
        [docker, "mcp", "profile", "show", profile["id"], "--format", "json"],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode and a.action == "install":
        result = subprocess.run(
            [
                docker,
                "mcp",
                "profile",
                "import",
                str(prefix / "config/mcp-profile.json"),
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise SystemExit(
                "MCP profile import failed; no existing profile was overwritten"
            )
        result = subprocess.run(
            [docker, "mcp", "profile", "show", profile["id"], "--format", "json"],
            env=env,
            capture_output=True,
            text=True,
        )
    if result.returncode:
        raise SystemExit("Install the isolated MCP profile first")
    actual = json.loads(result.stdout)
    if signature(actual) != signature(profile):
        raise SystemExit("MCP profile drift; refusing changed transport or authority")
    if a.action == "install":
        print("Isolated MCP profile verified.")
        return
    args = [
        docker,
        "mcp",
        "gateway",
        "run",
        "--profile",
        profile["id"],
        "--transport",
        "stdio",
        "--watch=false",
        "--log-calls=false",
        "--memory",
        "512Mb",
        "--cpus",
        "1",
        "--block-secrets=true",
        "--block-network",
        "--tools",
        "get_current_time,convert_to_markdown,hub_repo_search",
    ]
    os.execve(docker, args, env)


if __name__ == "__main__":
    main()
