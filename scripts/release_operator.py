"""Isolated, owner-operated release configuration and local gateway lifecycle."""

import argparse
import errno
import hashlib
import json
import os
import platform
import plistlib
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATEWAY_PROCESS_SCHEMA = "sanctum-gateway-process/v1"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def private(p):
    for item in [p, *p.parents]:
        if item.is_symlink():
            raise ValueError("Symlink in install path")
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    if p.stat().st_mode & 0o077:
        raise ValueError("Install directory must have permissions 0700")
    return p


def write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def verify():
    manifest = json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())
    for name, expected in manifest.items():
        p = ROOT / name
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT) or sha(p) != expected:
            raise ValueError("Source drift: " + name)
    pins = json.loads((ROOT / "reliability/runtime-pins.json").read_text())
    for name, expected in pins.items():
        p = ROOT / name
        if p.is_symlink() or sha(p) != expected:
            raise ValueError("Runtime drift: " + name)


def receipt(prefix):
    return json.loads((prefix / "receipt.json").read_text())


def verify_install(prefix):
    r = receipt(prefix)
    if r["source"] != str(ROOT):
        raise ValueError("Source moved; rebuild and reconfigure a new prefix")
    for name, h in r["files"].items():
        p = prefix / name
        if p.is_symlink() or sha(p) != h:
            raise ValueError("Installed configuration drift: " + name)
    return r


def setup(prefix, gateway_port=28789, mlx_port=28080):
    verify()
    private(prefix)
    if (prefix / "receipt.json").exists():
        verify_install(prefix)
        print("Configuration already complete; unchanged.")
        return
    if list(prefix.iterdir()):
        raise ValueError("Partial/nonempty prefix: inspect it; choose a fresh prefix")
    for name in (
        "config",
        "state",
        "cache",
        "logs",
        "state/openclaw",
        "state/workspace",
    ):
        private(prefix / name)
    for name in (
        "benchmark-dataset-v1.schema.json",
        "benchmark-replay-v1.schema.json",
        "content-telemetry-v1.schema.json",
        "quality-annotation-v1.schema.json",
    ):
        write(
            prefix / "config/schemas" / name,
            (ROOT / "config/schemas" / name).read_text(),
        )
    python = str(ROOT / ".venv/bin/python")
    node = shutil.which("node")
    if not Path(python).exists() or not node:
        raise ValueError("Install pinned Python and Node dependencies first")
    tokens = {
        "@PYTHON@": python,
        "@STATE@": str(prefix / "state"),
        "@CONFIG@": str(prefix / "config"),
        "@GATE@": str(prefix / "gate"),
        "@OPENCLAW@": str(ROOT / "node_modules/openclaw"),
        "@SANCTUM_PACKAGE@": str(ROOT / "package.json"),
        "@NODE@": node,
    }
    # These values are inserted into reviewed JSON/Python/JS string literals.
    if any(any(c in v for c in "'\"\\\n\r") for v in tokens.values()):
        raise ValueError("Unsupported quote/backslash in installation path")
    for p in (ROOT / "gate").rglob("*"):
        if not p.is_file() or any(
            x in p.relative_to(ROOT / "gate").parts
            for x in ("tests", "__pycache__", "state")
        ):
            continue
        if p.name in ("FREEZE.json",):
            continue
        text = p.read_text()
        for token, value in tokens.items():
            text = text.replace(token, value)
        write(prefix / "gate" / p.relative_to(ROOT / "gate"), text)
    private(prefix / "state/gate")
    write(prefix / "state/gate/authority.key", secrets.token_hex(32))
    # Gate expects arbitrary private key bytes; 64 hex characters provide 256 bits entropy.
    write(prefix / "config/contacts.json", "{}\n")
    roots = {
        name: str(private(prefix / "files" / name))
        for name in ["desktop", "downloads", "documents", "vinceai", "pictures"]
    }
    write(prefix / "config/file-roots.json", json.dumps(roots, indent=2) + "\n")
    private(prefix / "mcp-input")
    write(
        prefix / "config/mcp-profile.json",
        (ROOT / "mcp-integration/config/profile.json")
        .read_text()
        .replace("@MCP_INPUT@", str(prefix / "mcp-input")),
    )
    model = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
    paths = [
        str(ROOT / "plugins" / n)
        for n in [
            "browser-guard",
            "messages-read-tools",
            "gmail-read-tools",
            "calendar-read-tools",
            "local-markdown-tools",
            "file-steward",
        ]
    ] + [
        str(ROOT / "reliability"),
        str(ROOT / "mcp-integration/guard"),
        str(prefix / "gate/plugin"),
    ]
    entries = {
        n: {"enabled": True}
        for n in [
            "browser-guard",
            "messages-read-tools",
            "gmail-read-tools",
            "calendar-read-tools",
            "local-markdown-tools",
            "file-steward",
            "vinceai-mcp-guard",
            "hybrid-ai-prompt-gate",
        ]
    }
    entries["vinceai-reliability"] = {
        "enabled": True,
        "hooks": {"allowConversationAccess": True},
    }
    cfg = {
        "gateway": {
            "mode": "local",
            "bind": "loopback",
            "port": gateway_port,
            "auth": {"mode": "token", "token": secrets.token_hex(32)},
            "http": {"endpoints": {"chatCompletions": {"enabled": True}}},
        },
        "agents": {
            "defaults": {
                "workspace": str(prefix / "state/workspace"),
                "model": {"primary": "mlx-local/" + model},
                "modelPolicy": {"allow": ["mlx-local/" + model]},
                "experimental": {"localModelLean": True},
                "skills": [],
                "heartbeat": {"every": "0m"},
                "compaction": {"keepRecentTokens": 2048},
            },
            "entries": {
                "main": {
                    "thinkingDefault": "off",
                    "params": {"chat_template_kwargs": {"enable_thinking": False}},
                }
            },
        },
        "models": {
            "providers": {
                "mlx-local": {
                    "baseUrl": f"http://127.0.0.1:{mlx_port}/v1",
                    "api": "openai-completions",
                    "apiKey": "local-only",
                    "models": [
                        {
                            "id": model,
                            "name": "Local Qwen 4B",
                            "contextWindow": 24576,
                            "maxTokens": 4096,
                        }
                    ],
                }
            }
        },
        "plugins": {"load": {"paths": paths}, "entries": entries},
        "tools": {
            "profile": "minimal",
            "toolSearch": False,
            "deny": ["exec", "process", "write", "edit", "apply_patch", "canvas"],
            "alsoAllow": ["calc", "date_math", "unit_convert", "structured_parse"],
            "byProvider": {
                "openrouter": {
                    "deny": [
                        "steward_*",
                        "calendar_*",
                        "messages_*",
                        "gmail_*",
                        "browser",
                        "save_local_markdown",
                    ]
                }
            },
        },
        "browser": {
            "enabled": True,
            "defaultProfile": "openclaw",
            "evaluateEnabled": False,
        },
    }
    cfg["plugins"]["allow"] = list(entries) + ["browser"]
    cfg["plugins"]["entries"]["memory-core"] = {"enabled": False}
    cfg["update"] = {"checkOnStart": False, "auto": {"enabled": False}}
    cfg["discovery"] = {"mdns": {"mode": "off"}}
    cfg["logging"] = {"file": str(prefix / "logs/openclaw.log")}
    write(prefix / "config/openclaw.json", json.dumps(cfg, indent=2) + "\n")
    env = {
        "OPENCLAW_HOME": str(prefix),
        "OPENCLAW_STATE_DIR": str(prefix / "state/openclaw"),
        "OPENCLAW_CONFIG_PATH": str(prefix / "config/openclaw.json"),
        "VINCEAI_CONFIG_DIR": str(prefix / "config"),
        "VINCEAI_STATE_DIR": str(prefix / "state"),
        "VINCEAI_CACHE_DIR": str(prefix / "cache"),
        "VINCEAI_CONTACTS_FILE": str(prefix / "config/contacts.json"),
        "VINCEAI_FILE_ROOTS_FILE": str(prefix / "config/file-roots.json"),
        "VINCEAI_OPENCLAW_DATABASE": str(
            prefix / "state/openclaw/state/openclaw.sqlite"
        ),
        "VINCEAI_GATEWAY_PORT": str(gateway_port),
        "VINCEAI_MLX_PORT": str(mlx_port),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env["VINCEAI_MCP_INPUT_DIR"] = str(prefix / "mcp-input")
    write(prefix / "config/environment.json", json.dumps(env, indent=2) + "\n")
    label = (
        "org.sanctum."
        + hashlib.sha256(str(prefix).encode()).hexdigest()[:12]
        + ".gpu-janitor"
    )
    service = {
        "Label": label,
        "ProgramArguments": [python, "-B", str(prefix / "gate/manage.py"), "sweep"],
        "RunAtLoad": True,
        "StartInterval": 30,
        "ProcessType": "Background",
        "EnvironmentVariables": {**env, "USER": os.environ.get("USER", "vinceai")},
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
    }
    write(prefix / "config/gpu-janitor.plist", plistlib.dumps(service).decode())
    # Freeze only the newly rendered candidate, after source/build verification.
    freeze = {
        str(p.relative_to(prefix / "gate")): sha(p)
        for p in (prefix / "gate").rglob("*")
        if p.is_file()
    }
    write(prefix / "gate/FREEZE.json", json.dumps(freeze, indent=2) + "\n")
    files = {
        str(p.relative_to(prefix)): sha(p)
        for p in prefix.rglob("*")
        if p.is_file() and "state" not in p.relative_to(prefix).parts
    }
    write(
        prefix / "receipt.json",
        json.dumps(
            {
                "source": str(ROOT),
                "files": files,
                "created": time.time(),
                "gateway_port": gateway_port,
                "mlx_port": mlx_port,
            },
            indent=2,
        )
        + "\n",
    )
    print(
        "Isolated configuration created. Optional sources and remote credentials require local setup. No service started."
    )


def environment(prefix):
    return {
        **os.environ,
        **json.loads((prefix / "config/environment.json").read_text()),
    }


def process_record(prefix):
    p = prefix / "state/gateway-process.json"
    return json.loads(p.read_text()) if p.exists() else None


def expected_gateway_identity(prefix, r=None):
    r = r or receipt(prefix)
    node = Path(shutil.which("node") or "").resolve()
    entry = (ROOT / "node_modules/openclaw/dist/index.js").resolve()
    if not node.is_file() or not entry.is_file():
        raise ValueError("Pinned gateway runtime unavailable")
    return {
        "schema": GATEWAY_PROCESS_SCHEMA,
        "node_path": str(node),
        "entrypoint_path": str(entry),
        "entrypoint_sha256": sha(entry),
        "gateway_port": r["gateway_port"],
        "install_receipt_sha256": sha(prefix / "receipt.json"),
        "gate_freeze_sha256": sha(prefix / "gate/FREEZE.json"),
        "openclaw_config_sha256": sha(prefix / "config/openclaw.json"),
        "source_manifest_sha256": sha(ROOT / "SOURCE-MANIFEST.json"),
    }


def gateway_identity_matches(prefix, record, r=None):
    if type(record) is not dict:
        return False
    try:
        expected = expected_gateway_identity(prefix, r)
    except (ValueError, OSError, KeyError):
        return False
    return all(record.get(key) == value for key, value in expected.items())


def owns_process(record):
    if not record:
        return False
    try:
        p = subprocess.run(
            ["ps", "-p", str(record["pid"]), "-o", "command="],
            capture_output=True,
            text=True,
        )
    except (KeyError, TypeError, ValueError):
        return False
    return (
        p.returncode == 0
        and type(record.get("identity")) is list
        and all(type(x) is str and x in p.stdout for x in record["identity"])
    )


def gateway_socket_ready(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def gateway_command(prefix, receipt_value, expected, env):
    args = [expected["node_path"]]
    bootstrap = prefix / "gate/plugin/observability-bootstrap.mjs"
    if (
        env.get("SANCTUM_O11Y_ENABLED") == "1"
        and bootstrap.is_file()
        and not bootstrap.is_symlink()
    ):
        args.extend(["--import", str(bootstrap)])
    args.extend(
        [
            expected["entrypoint_path"],
            "gateway",
            "run",
            "--port",
            str(receipt_value["gateway_port"]),
        ]
    )
    return args


def up(prefix):
    verify()
    r = verify_install(prefix)
    if platform.system() != "Darwin":
        raise ValueError(
            "Host gateway acceptance is supported on macOS; offline tests work on Linux"
        )
    current = process_record(prefix)
    if owns_process(current):
        if not gateway_identity_matches(prefix, current, r):
            raise ValueError(
                "Running gateway identity is stale; refusing adoption or replacement"
            )
        if not gateway_socket_ready(r["gateway_port"]):
            raise ValueError("Candidate gateway process is not healthy")
        print("Candidate gateway already running with current installed identity.")
        return
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", r["gateway_port"]))
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                raise ValueError(
                    "Gateway port occupied; refusing adoption or replacement"
                )
            raise ValueError("Cannot bind loopback gateway socket: " + str(e))
    expected = expected_gateway_identity(prefix, r)
    gateway_env = environment(prefix)
    args = gateway_command(prefix, r, expected, gateway_env)
    with open(prefix / "logs/gateway.log", "ab") as log:
        p = subprocess.Popen(
            args,
            env=gateway_env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    marker = prefix / "state/gateway-process.json"
    if marker.exists():
        marker.unlink()  # stale record only, never a running process
    write(
        marker,
        json.dumps(
            {
                **expected,
                "pid": p.pid,
                "identity": [
                    args[0],
                    expected["entrypoint_path"],
                    str(r["gateway_port"]),
                    *(
                        [str(prefix / "gate/plugin/observability-bootstrap.mjs")]
                        if "--import" in args
                        else []
                    ),
                ],
            }
        ),
    )
    for _ in range(240):
        if p.poll() is not None:
            raise ValueError("Gateway exited; inspect private log")
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", r["gateway_port"])) == 0:
                print(
                    "Candidate gateway listening on loopback. Run doctor for configuration checks."
                )
                return
        time.sleep(0.25)
    raise ValueError(
        "Gateway startup still pending; inspect status/logs, do not launch duplicate"
    )


def down(prefix):
    verify_install(prefix)
    # Never kill cleanup if a configured GPU could still be owned.
    cfg = json.loads((prefix / "gate/SETTINGS.json").read_text())
    state = prefix / "state/gate/gpu.json"
    if cfg["gpu"]["auto_start"]:
        result = subprocess.run(
            [cfg["python"], "-B", str(prefix / "gate/manage.py"), "stop"],
            env=environment(prefix),
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise ValueError("GPU stop unconfirmed; cleanup remains running")
        status = json.loads(result.stdout)
        if (
            status.get("phase") not in ("OFFLINE", "RETIRED")
            or status.get("leases")
            or status.get("pod_id")
        ):
            raise ValueError("GPU cleanup still pending")
    if state.exists():
        if state.is_symlink():
            raise ValueError("Unsafe GPU state")
        gpu = json.loads(state.read_text())
        if gpu.get("phase") not in ("OFFLINE", "RETIRED") or any(
            gpu.get(k) for k in ["pod_id", "pod_name", "allocation_uncertain"]
        ):
            raise ValueError("Unresolved GPU ownership; preserve cleanup")
    db = prefix / "state/gate/control.sqlite"
    if db.exists():
        if db.is_symlink():
            raise ValueError("Unsafe GPU database")
        with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as c:
            if c.execute("select count(*) from leases").fetchone()[0]:
                raise ValueError("Close gate leases before shutdown")
    r = process_record(prefix)
    if owns_process(r):
        os.kill(r["pid"], signal.SIGTERM)
        for _ in range(60):
            if not owns_process(r):
                print("Candidate gateway stopped.")
                return
            time.sleep(0.25)
        raise ValueError(
            "Candidate gateway shutdown still pending; inspect status/logs"
        )
    else:
        print("No matching candidate gateway running.")


def doctor(prefix):
    verify()
    r = verify_install(prefix)
    record = process_record(prefix)
    running = owns_process(record)
    identity = (
        "match"
        if running and gateway_identity_matches(prefix, record, r)
        else ("stale" if running else "stopped")
    )
    health = (
        "pass"
        if identity == "match" and gateway_socket_ready(r["gateway_port"])
        else ("stopped" if not running else "fail")
    )
    report = {
        "source_integrity": "pass",
        "runtime_pins": "pass",
        "configuration_integrity": "pass",
        "platform": platform.system() + "/" + platform.machine(),
        "gateway_running": running,
        "gateway_identity": identity,
        "gateway_health": health,
        "optional_integrations": "unconfigured; no credential or provider probe performed",
        "ports": {"gateway": r["gateway_port"], "mlx": r["mlx_port"]},
    }
    print(json.dumps(report, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "command",
        choices=["setup", "doctor", "up", "down", "status", "logs", "uninstall"],
    )
    p.add_argument("--prefix", type=Path, default=ROOT / ".local")
    p.add_argument("--gateway-port", type=int, default=28789)
    p.add_argument("--mlx-port", type=int, default=28080)
    a = p.parse_args()
    prefix = a.prefix.absolute()
    if (
        not all(1024 <= n <= 65535 for n in (a.gateway_port, a.mlx_port))
        or a.gateway_port == a.mlx_port
    ):
        raise ValueError("Distinct unprivileged ports required")
    if a.command == "setup":
        setup(prefix, a.gateway_port, a.mlx_port)
    elif a.command == "doctor":
        doctor(prefix)
    elif a.command == "up":
        up(prefix)
    elif a.command == "down":
        down(prefix)
    elif a.command == "status":
        record = process_record(prefix)
        running = owns_process(record)
        state = (
            "running-current"
            if running and gateway_identity_matches(prefix, record)
            else ("running-stale" if running else "stopped")
        )
        print("Candidate gateway: " + state)
    elif a.command == "logs":
        print("Private gateway log: " + str(prefix / "logs/gateway.log"))
    elif a.command == "uninstall":
        down(prefix)
        print(
            "No system services installed. Private configuration, state and receipts retained for rollback."
        )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as e:
        raise SystemExit("REFUSED: " + str(e))
