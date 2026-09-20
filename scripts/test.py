"""Credential-free test groups; no provider or real-source calls."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GATE_NODE_TESTS = (
    "tests/core.test.mjs",
    "tests/observability.test.mjs",
    "tests/local-agent.test.mjs",
    "tests/source-retrieval.test.mjs",
    "tests/work-mode.test.mjs",
    "tests/worktree-edit.test.mjs",
    "tests/task-evidence.test.mjs",
    "tests/protocol-repair.test.mjs",
    "tests/protocol-targeted.test.mjs",
    "tests/prelive.test.mjs",
)


def run(args: list[str], directory: str, env: dict[str, str]) -> None:
    subprocess.run(args, cwd=ROOT / directory, env=env, check=True)


def node_tests(directory: str, tests: tuple[str, ...], env: dict[str, str]) -> None:
    run(["node", "--test", "--test-reporter=tap", *tests], directory, env)


def python_discovery(directory: str, env: dict[str, str]) -> None:
    run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ],
        directory,
        env,
    )


def gate_js(env: dict[str, str]) -> None:
    node_tests("gate", GATE_NODE_TESTS, env)


def gate_python(env: dict[str, str]) -> None:
    python_discovery("gate", env)


def reliability(env: dict[str, str]) -> None:
    tests = tuple(
        str(path.relative_to(ROOT / "reliability"))
        for path in sorted((ROOT / "reliability/tests").glob("*.test.mjs"))
    )
    node_tests("reliability", tests, env)
    python_discovery("reliability", env)


def mcp(env: dict[str, str]) -> None:
    node_tests("mcp-integration", ("tests/guard.test.mjs",), env)


def plugins(env: dict[str, str]) -> None:
    for plugin in sorted((ROOT / "plugins").iterdir()):
        if list((plugin / "src").glob("*.test.ts")):
            run(
                ["vitest", "run", "--config", "vitest.config.ts"],
                str(plugin.relative_to(ROOT)),
                env,
            )


def release(env: dict[str, str]) -> None:
    run([sys.executable, "-B", "-m", "unittest", "tests.test_release"], ".", env)


def agents(env: dict[str, str]) -> None:
    run(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "tests.test_agent_system",
            "tests.test_rework_workflow",
        ],
        ".",
        env,
    )


GROUPS: dict[str, Callable[[dict[str, str]], None]] = {
    "gate-js": gate_js,
    "gate-python": gate_python,
    "reliability": reliability,
    "mcp": mcp,
    "plugins": plugins,
    "release": release,
    "agents": agents,
}


def environment(temp_dir: str) -> dict[str, str]:
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "OPENCLAW_HOME": temp_dir,
        "OPENCLAW_STATE_DIR": temp_dir,
        "OPENCLAW_CONFIG_PATH": f"{temp_dir}/openclaw.json",
        "VINCEAI_STATE_DIR": temp_dir,
        "SANCTUM_O11Y_ENABLED": "0",
        "SANCTUM_TELEMETRY_DISABLE": "1",
        "PATH": str(ROOT / "node_modules/.bin") + os.pathsep + os.environ["PATH"],
    }
    for key in ("VINCEAI_GATEWAY_PORT", "VINCEAI_MLX_PORT", "VINCEAI_CONTACTS_FILE"):
        env.pop(key, None)
    return env


def main() -> None:
    group = sys.argv[1] if len(sys.argv) == 2 else "all"
    if group not in {*GROUPS, "gate", "all"}:
        choices = ", ".join([*GROUPS, "gate", "all"])
        raise SystemExit(f"unknown test group {group!r}; choose one of: {choices}")

    selected = list(GROUPS) if group == "all" else [group]
    if group == "gate":
        selected = ["gate-js", "gate-python"]

    with tempfile.TemporaryDirectory(prefix="sanctum-tests-") as temp_dir:
        env = environment(temp_dir)
        for name in selected:
            GROUPS[name](env)


if __name__ == "__main__":
    main()
