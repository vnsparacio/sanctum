"""Foreground host components with fixed commands and isolated environment."""

import argparse
import importlib.util
import json
import os
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "release_operator", ROOT / "scripts/release_operator.py"
)
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)
BROKERS = {
    "messages": "messages-read-broker.py",
    "gmail": "gmail-read-broker.py",
    "calendar": "calendar-read-broker.py",
    "markdown": "local-markdown-broker.py",
    "files": "file-steward-broker.py",
}
OPTIONAL_BROKERS = ("messages", "gmail", "calendar")
LOCAL_BROKERS = ("markdown", "files")


def integration_enabled(prefix, name):
    marker = prefix / "config" / (name + ".enabled")
    return marker.is_file() and marker.read_text().strip() == "enabled"


def selected_brokers(prefix):
    return [
        *[name for name in OPTIONAL_BROKERS if integration_enabled(prefix, name)],
        *LOCAL_BROKERS,
    ]


def stop_children(children):
    for child in children:
        if child.poll() is None:
            child.terminate()
    deadline = time.monotonic() + 5
    for child in children:
        if child.poll() is not None:
            continue
        try:
            child.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            child.kill()
    for child in children:
        if child.poll() is None:
            child.wait()


def run_brokers(prefix, python, env):
    names = selected_brokers(prefix)
    children = []
    requested_signal = None

    def request_stop(signum, _frame):
        nonlocal requested_signal
        requested_signal = signum

    previous = {
        signum: signal.signal(signum, request_stop)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        print("Starting broker group:", ", ".join(names), flush=True)
        for name in names:
            child = subprocess.Popen(
                [python, "-B", str(ROOT / "host/macos" / BROKERS[name])],
                cwd=prefix,
                env=env,
            )
            children.append(child)
            print(f"  {name}: pid {child.pid}", flush=True)
        while requested_signal is None:
            for name, child in zip(names, children, strict=True):
                code = child.poll()
                if code is not None:
                    print(
                        f"Broker {name} exited with status {code}; stopping the group.",
                        flush=True,
                    )
                    return code if code else 1
            time.sleep(0.25)
        return 128 + requested_signal
    finally:
        stop_children(children)
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "component",
        choices=["mlx", *BROKERS, "brokers", "webui"],
    )
    parser.add_argument("--prefix", type=Path, default=ROOT / ".local")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args(argv)
    prefix = args.prefix.absolute()
    op.verify()
    receipt = op.verify_install(prefix)
    env = op.environment(prefix)
    if args.health:
        if args.component not in ("mlx", "webui"):
            raise SystemExit("Health probe is supported for mlx/webui only")
        url = (
            f"http://127.0.0.1:{receipt['mlx_port']}/v1/models"
            if args.component == "mlx"
            else "http://127.0.0.1:28000/health"
        )
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                result = json.load(response)
            if (
                args.component == "mlx"
                and "mlx-community/Qwen3-4B-Instruct-2507-4bit"
                not in [x.get("id") for x in result.get("data", [])]
            ):
                raise ValueError("Unexpected local model identity")
            if args.component == "webui" and result.get("status") is not True:
                raise ValueError("WebUI not healthy")
        except Exception:
            raise SystemExit(
                "Component unavailable or identity mismatch; inspect its private log and start the candidate component. No fallback was used."
            )
        print("Healthy:", args.component)
        return 0
    env.setdefault("VINCEAI_NOTES_DIR", str(prefix / "notes"))
    env["VINCEAI_GOOGLE_HOME"] = str(prefix / "state/google-readonly")
    python = str(ROOT / ".venv/bin/python")
    if args.component == "brokers":
        return run_brokers(prefix, python, env)
    if args.component in BROKERS:
        if args.component in OPTIONAL_BROKERS and not integration_enabled(
            prefix, args.component
        ):
            raise SystemExit(
                "Configure the read-only integration and create config/"
                + args.component
                + ".enabled first; see docs/guides/installation.md"
            )
        command = [
            python,
            "-B",
            str(ROOT / "host/macos" / BROKERS[args.component]),
        ]
    elif args.component == "mlx":
        exe = str(prefix / "runtime/mlx/bin/mlx_lm.server")
        if not Path(exe).is_file():
            raise SystemExit(
                "Run scripts/bootstrap.py mlx with the same --prefix first"
            )
        if args.cache_only:
            env["HF_HUB_OFFLINE"] = "1"
        command = [
            exe,
            "--model",
            "mlx-community/Qwen3-4B-Instruct-2507-4bit",
            "--host",
            "127.0.0.1",
            "--port",
            str(receipt["mlx_port"]),
            "--max-tokens",
            "4096",
            "--decode-concurrency",
            "1",
            "--prompt-concurrency",
            "1",
            "--prefill-step-size",
            "512",
            "--prompt-cache-size",
            "2",
            "--prompt-cache-bytes",
            "4294967296",
        ]
    else:
        exe = str(prefix / "runtime/webui/bin/open-webui")
        if not Path(exe).is_file():
            raise SystemExit(
                "Run scripts/bootstrap.py webui with the same --prefix first"
            )
        for name in (
            "ENABLE_OLLAMA_API",
            "ENABLE_OPENAI_API",
            "ENABLE_MEMORIES",
            "ENABLE_WEB_SEARCH",
            "ENABLE_VERSION_UPDATE_CHECK",
            "ENABLE_EVALUATION_ARENA_MODELS",
            "ENABLE_AUTOMATIONS",
            "ENABLE_MEMORY_SYSTEM_CONTEXT",
            "ENABLE_MEMORY_BACKGROUND_REVIEW",
        ):
            env[name] = "False"
        env["OFFLINE_MODE"] = "True"
        env["CORS_ALLOW_ORIGIN"] = "http://127.0.0.1:28000;http://localhost:28000"
        env["DO_NOT_TRACK"] = "True"
        env["ANONYMIZED_TELEMETRY"] = "False"
        env["SCARF_NO_ANALYTICS"] = "True"
        env["DATA_DIR"] = str(prefix / "state/webui")
        command = [exe, "serve", "--host", "127.0.0.1", "--port", "28000"]
    return subprocess.call(command, cwd=prefix, env=env)


if __name__ == "__main__":
    os.umask(0o077)
    raise SystemExit(main())
