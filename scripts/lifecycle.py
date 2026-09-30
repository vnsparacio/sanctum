"""One-command setup and owner-scoped lifecycle supervision for Sanctum."""

from __future__ import annotations

import argparse
import errno
import getpass
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACK_SCHEMA = "sanctum-stack-process/v1"
STACK_STATE = "state/stack-process.json"


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


op = load("release_operator", "scripts/release_operator.py")
bootstrap_tools = load("bootstrap_tools", "scripts/bootstrap.py")
component_tools = load("component_tools", "scripts/component.py")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_path(prefix):
    return prefix / STACK_STATE


def read_state(prefix):
    path = state_path(prefix)
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def write_state(prefix, value):
    path = state_path(prefix)
    temporary = path.with_name(path.name + ".new")
    temporary.unlink(missing_ok=True)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def process_matches(record):
    if not isinstance(record, dict) or not isinstance(record.get("pid"), int):
        return False
    identity = record.get("identity")
    if not isinstance(identity, list) or not identity:
        return False
    try:
        result = subprocess.run(
            ["ps", "-p", str(record["pid"]), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and all(
        isinstance(item, str) and item in result.stdout for item in identity
    )


def expected_identity(prefix):
    receipt = op.verify_install(prefix)
    return {
        "schema": STACK_SCHEMA,
        "source_manifest_sha256": digest(ROOT / "SOURCE-MANIFEST.json"),
        "install_receipt_sha256": digest(prefix / "receipt.json"),
        "supervisor_sha256": digest(Path(__file__)),
        "gateway_port": receipt["gateway_port"],
        "mlx_port": receipt["mlx_port"],
    }


def identity_current(prefix, record):
    try:
        expected = expected_identity(prefix)
    except (ValueError, OSError, KeyError):
        return False
    return isinstance(record, dict) and all(
        record.get(name) == value for name, value in expected.items()
    )


def tcp_ready(port):
    with socket.socket() as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def http_ready(url, validator):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            value = json.load(response)
        return validator(value)
    except Exception:
        return False


def broker_socket(prefix, name):
    return (
        prefix
        / "cache"
        / {
            "messages": "messages-read.sock",
            "gmail": "gmail-read.sock",
            "calendar": "calendar-read.sock",
            "markdown": "local-markdown.sock",
            "files": "file-steward.sock",
        }[name]
    )


def broker_ready(prefix, name):
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(1)
            connection.connect(str(broker_socket(prefix, name)))
            connection.sendall(
                b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
            )
            response = b""
            while len(response) < 8192:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                response += chunk
        header, separator, body = response.partition(b"\r\n\r\n")
        if not separator or b" 200 " not in header.splitlines()[0]:
            return False
        return json.loads(body).get("ok") is True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def unix_socket_listener(path):
    """Return True for a live listener and False only for a refused connection."""
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(0.5)
            connection.connect(str(path))
        return True
    except FileNotFoundError:
        return None
    except ConnectionRefusedError:
        return False
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return None
        if exc.errno == errno.ECONNREFUSED:
            return False
        raise ValueError(
            f"Cannot prove broker socket is stale: {path.name} ({exc.strerror})"
        ) from exc


def recover_stale_broker_sockets(prefix):
    """Quarantine exact, owner-controlled broker sockets with no listener."""
    stale = []
    for name in component_tools.selected_brokers(prefix):
        path = broker_socket(prefix, name)
        try:
            before = path.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISSOCK(before.st_mode):
            raise ValueError(
                f"Broker socket path is not a socket; inspect it manually: {path}"
            )
        if before.st_uid != os.getuid() or before.st_mode & 0o077:
            raise ValueError(
                f"Broker socket ownership or permissions are unsafe: {path}"
            )
        first = unix_socket_listener(path)
        if first is None:
            continue
        if first:
            raise ValueError(
                f"Broker socket has a live listener; refusing adoption: {path}"
            )
        if time.time() - before.st_mtime < 2:
            raise ValueError(
                f"Broker socket is too new to prove stale; retry shortly: {path}"
            )
        time.sleep(0.05)
        if unix_socket_listener(path) is not False:
            raise ValueError(
                f"Broker socket changed while checking it; inspect manually: {path}"
            )
        try:
            after = path.lstat()
        except FileNotFoundError:
            continue
        if (before.st_dev, before.st_ino, before.st_uid, before.st_mode) != (
            after.st_dev,
            after.st_ino,
            after.st_uid,
            after.st_mode,
        ):
            raise ValueError(
                f"Broker socket changed while checking it; inspect manually: {path}"
            )
        stale.append(path)
    if not stale:
        return None
    recovery = prefix / "state/amendments" / f"stale-broker-sockets-{time.time_ns()}"
    recovery.mkdir(parents=True, mode=0o700)
    os.chmod(recovery, 0o700)
    for path in stale:
        path.replace(recovery / path.name)
    return recovery


def wait_until(predicate, seconds, message, process=None):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise ValueError(message + "; process exited")
        if predicate():
            return
        time.sleep(0.25)
    raise ValueError(message + "; startup is still pending")


def child_record(process, command):
    return {
        "pid": process.pid,
        "identity": [str(command[0]), *[str(item) for item in command[1:3]]],
    }


def stop_process(process, seconds=15):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def terminate_record(record, seconds=15):
    if not process_matches(record):
        return
    os.kill(record["pid"], signal.SIGTERM)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not process_matches(record):
            return
        time.sleep(0.25)
    raise ValueError("Owned component shutdown is still pending")


def ensure_dependencies():
    expected = (
        ROOT / ".venv/bin/python",
        ROOT / "node_modules/openclaw/dist/index.js",
    )
    if all(path.is_file() for path in expected):
        return
    if not shutil.which("uv") or not shutil.which("npm"):
        raise ValueError("Install uv, Node 26.8.1 and npm, then rerun setup")
    subprocess.run(["make", "deps"], cwd=ROOT, check=True)


def proposal_value(path):
    if path is None:
        return None
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Setup proposal must be a JSON object")
    return value


def configured_integrations(prefix):
    return {
        name
        for name in ("messages", "gmail", "calendar")
        if component_tools.integration_enabled(prefix, name)
    }


def web_enabled(prefix):
    try:
        config = json.loads((prefix / "config/openclaw.json").read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return (
        config.get("tools", {}).get("web", {}).get("search", {}).get("enabled") is True
    )


def openclaw_command(prefix, *arguments):
    return [
        shutil.which("node") or "node",
        str(ROOT / "node_modules/openclaw/dist/index.js"),
        *arguments,
    ], op.environment(prefix)


def web_authorized(prefix):
    if not web_enabled(prefix):
        return True
    command, env = openclaw_command(prefix, "secrets", "store", "list", "--json")
    try:
        result = subprocess.run(
            command,
            cwd=prefix,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        entries = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    return any(
        item.get("name") == "PARALLEL_API_KEY" and item.get("kind") == "secret"
        for item in entries
        if isinstance(item, dict)
    )


def google_authorized(prefix, name):
    account_path = prefix / "config" / f"{name}-read/account"
    if not account_path.is_file() or not shutil.which("gog"):
        return False
    try:
        result = subprocess.run(
            [
                "gog",
                "--home",
                str(prefix / "state/google-readonly"),
                "--readonly",
                "--gmail-no-send",
                "auth",
                "list",
                "--json",
            ],
            cwd=prefix,
            capture_output=True,
            text=True,
            timeout=10,
        )
        accounts = json.loads(result.stdout).get("accounts", [])
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    expected = account_path.read_text().strip()
    return any(
        item.get("email") == expected and name in item.get("services", [])
        for item in accounts
        if isinstance(item, dict)
    )


def openrouter_authorized(prefix):
    try:
        environment = op.environment(prefix)
    except (OSError, ValueError, json.JSONDecodeError):
        environment = {}
    database = Path(
        environment.get(
            "VINCEAI_OPENCLAW_DATABASE",
            prefix / "state/openclaw/state/openclaw.sqlite",
        )
    )
    if not database.is_file() or database.is_symlink():
        return False
    try:
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            row = connection.execute(
                "select value_json from config_machine_state where state_key=?",
                ("authProfiles.store",),
            ).fetchone()
        value = json.loads(row[0]) if row else {}
        value = json.loads(value) if isinstance(value, str) else value
    except (OSError, sqlite3.Error, json.JSONDecodeError, TypeError):
        return False
    profiles = [
        item
        for item in value.get("profiles", {}).values()
        if isinstance(item, dict)
        and item.get("provider") == "openrouter"
        and item.get("type") == "api_key"
        and item.get("key")
    ]
    return len(profiles) == 1


def authorize(prefix):
    integrations = configured_integrations(prefix)
    if web_enabled(prefix) and not web_authorized(prefix):
        secret = getpass.getpass("Parallel API key (hidden; blank to defer): ")
        if secret:
            command, env = openclaw_command(
                prefix,
                "secrets",
                "store",
                "set",
                "PARALLEL_API_KEY",
                "--kind",
                "secret",
                "--value-file",
                "-",
            )
            subprocess.run(
                command,
                cwd=prefix,
                env=env,
                input=secret,
                text=True,
                check=True,
            )
    services = {"gmail": "gmail", "calendar": "calendar"}
    accounts = {}
    for name in sorted(integrations & services.keys()):
        if google_authorized(prefix, name):
            print(f"Read-only {name} OAuth already enrolled; unchanged.")
            continue
        account_path = prefix / "config" / f"{name}-read/account"
        if not account_path.is_file():
            print(
                f"CHECKPOINT: add the {name} account to the private proposal, then rerun."
            )
            continue
        account = account_path.read_text().strip()
        accounts.setdefault(account, []).append(services[name])
    for account, account_services in accounts.items():
        command = [
            "gog",
            "--home",
            str(prefix / "state/google-readonly"),
            "--readonly",
            "--gmail-no-send",
            "auth",
            "add",
            account,
            "--services",
            ",".join(sorted(account_services)),
        ]
        subprocess.run(command, cwd=prefix, check=True)


def setup(prefix, proposal_path=None, authorize_now=False, cache_only=False):
    ensure_dependencies()
    op.verify()
    op.setup(prefix)
    bootstrap_tools.bootstrap("mlx", prefix)
    bootstrap_tools.bootstrap("webui", prefix)
    proposal = proposal_value(proposal_path)
    if proposal and "web" in set(proposal.get("integrations", [])):
        bootstrap_tools.bootstrap("web", prefix)
    proposal_digest = digest(proposal_path) if proposal_path else None
    applied_path = prefix / "state/setup-proposal.sha256"
    already_applied = (
        proposal_digest is not None
        and applied_path.is_file()
        and applied_path.read_text().strip() == proposal_digest
    )
    if proposal and not already_applied:
        subprocess.run(
            [
                str(ROOT / ".venv/bin/python"),
                "-B",
                str(ROOT / "scripts/configure.py"),
                "--prefix",
                str(prefix),
                "--proposal",
                str(proposal_path.absolute()),
            ],
            cwd=ROOT,
            check=True,
        )
        temporary = applied_path.with_name(applied_path.name + ".new")
        temporary.unlink(missing_ok=True)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(proposal_digest + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, applied_path)
    elif already_applied:
        print("Private setup proposal already applied; unchanged.")
    bootstrap_tools.ensure_model(prefix, cache_only=cache_only)
    if authorize_now:
        authorize(prefix)
    op.verify_install(prefix)
    integrations = configured_integrations(prefix)
    print("\nSetup complete for the local model, gateway, brokers and Open WebUI.")
    if "messages" in integrations:
        print(
            "CHECKPOINT: confirm macOS System Settings grants your terminal Full "
            "Disk Access for read-only Messages history."
        )
    missing_google = {
        name
        for name in integrations & {"gmail", "calendar"}
        if not google_authorized(prefix, name)
    }
    if missing_google and not authorize_now:
        print(
            "CHECKPOINT: rerun this setup command with --authorize for read-only "
            "Google OAuth."
        )
    if not web_authorized(prefix) and not authorize_now:
        print(
            "CHECKPOINT: rerun this setup command with --authorize to enroll the "
            "web API key securely."
        )
    if not openrouter_authorized(prefix):
        print(
            "OPTIONAL CHECKPOINT: hosted Qwen/frontier routes require one "
            "OpenRouter credential in the isolated OpenClaw auth store. Local "
            "operation requires no hosted API key."
        )
    if (
        webui_owner_enrollment(prefix) == "pass"
        and op.webui_function_sync(prefix) == "pass"
    ):
        print("WebUI owner and reviewed functions are already enrolled; unchanged.")
    else:
        print(
            "CHECKPOINT after first start: create the local WebUI owner, import "
            "gate/webui/guard.py and gate/webui/pipe.py, and select Mac prompt gate."
        )
    print("Start everything with: ./sanctum start --prefix " + str(prefix))
    print("Then verify owner readiness with: ./sanctum ready --prefix " + str(prefix))


def supervise(prefix):
    op.verify()
    expected = expected_identity(prefix)
    record = {
        **expected,
        "pid": os.getpid(),
        "identity": [str(Path(__file__).resolve()), "_supervise", str(prefix)],
        "phase": "starting",
        "children": {},
    }
    write_state(prefix, record)
    children = {}
    stopping = False

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, request_stop)
    try:
        receipt = op.verify_install(prefix)
        mlx_command, mlx_env = component_tools.component_command(
            prefix, "mlx", cache_only=True
        )
        with open(prefix / "logs/mlx.log", "ab") as log:
            children["mlx"] = subprocess.Popen(
                mlx_command,
                cwd=prefix,
                env=mlx_env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
            )
        record["children"]["mlx"] = child_record(children["mlx"], mlx_command)
        write_state(prefix, record)
        wait_until(
            lambda: http_ready(
                f"http://127.0.0.1:{receipt['mlx_port']}/v1/models",
                lambda value: bootstrap_tools.MODEL
                in [item.get("id") for item in value.get("data", [])],
            ),
            300,
            "MLX model server unavailable",
            children["mlx"],
        )
        op.up(prefix)
        brokers_command, brokers_env = component_tools.component_command(
            prefix, "brokers"
        )
        with open(prefix / "logs/brokers.log", "ab") as log:
            children["brokers"] = subprocess.Popen(
                brokers_command,
                cwd=prefix,
                env=brokers_env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
            )
        record["children"]["brokers"] = child_record(
            children["brokers"], brokers_command
        )
        write_state(prefix, record)
        names = component_tools.selected_brokers(prefix)
        wait_until(
            lambda: all(broker_ready(prefix, name) for name in names),
            30,
            "Broker group unavailable",
            children["brokers"],
        )
        webui_command, webui_env = component_tools.component_command(prefix, "webui")
        with open(prefix / "logs/webui.log", "ab") as log:
            children["webui"] = subprocess.Popen(
                webui_command,
                cwd=prefix,
                env=webui_env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
            )
        record["children"]["webui"] = child_record(children["webui"], webui_command)
        write_state(prefix, record)
        wait_until(
            lambda: http_ready(
                "http://127.0.0.1:28000/health",
                lambda value: value.get("status") is True,
            ),
            180,
            "Open WebUI unavailable",
            children["webui"],
        )
        record["phase"] = "ready"
        write_state(prefix, record)
        while not stopping:
            failed = [
                name for name, child in children.items() if child.poll() is not None
            ]
            if failed:
                raise ValueError("Component exited unexpectedly: " + ", ".join(failed))
            time.sleep(0.5)
    except Exception as exc:
        record["phase"] = "failed"
        record["error"] = str(exc)
        write_state(prefix, record)
    finally:
        try:
            op.down(prefix)
        except Exception as exc:
            record["shutdown_error"] = str(exc)
            write_state(prefix, record)
        for name in ("webui", "brokers", "mlx"):
            if name in children:
                stop_process(children[name])
        record["phase"] = "stopped" if "error" not in record else "failed"
        write_state(prefix, record)


def start(prefix):
    op.verify()
    receipt = op.verify_install(prefix)
    for component in ("mlx", "webui"):
        if not bootstrap_tools.runtime_ready(prefix, component):
            raise ValueError("Run ./sanctum setup before start")
    current = read_state(prefix)
    if current and process_matches(current):
        if not identity_current(prefix, current):
            raise ValueError("A stale Sanctum supervisor is running; stop it first")
        print("Sanctum is already " + current.get("phase", "running") + ".")
        return
    if op.owns_process(op.process_record(prefix)):
        raise ValueError(
            "A separately managed gateway is running; stop it before stack start"
        )
    for port, name in (
        (receipt["mlx_port"], "MLX"),
        (receipt["gateway_port"], "gateway"),
        (28000, "Open WebUI"),
    ):
        if tcp_ready(port):
            raise ValueError(f"{name} port {port} is occupied; refusing adoption")
    recovery = recover_stale_broker_sockets(prefix)
    if recovery:
        print("Recovered stale broker sockets to: " + str(recovery))
    command = [
        str(Path(sys.executable).resolve()),
        "-B",
        str(Path(__file__).resolve()),
        "_supervise",
        "--prefix",
        str(prefix),
    ]
    with open(prefix / "logs/stack.log", "ab") as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    deadline = time.monotonic() + 480
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError("Stack supervisor exited; inspect logs/stack.log")
        state = read_state(prefix)
        if state and state.get("pid") == process.pid:
            if state.get("phase") == "ready" and http_ready(
                "http://127.0.0.1:28000/health",
                lambda value: value.get("status") is True,
            ):
                print("Sanctum is ready: http://127.0.0.1:28000")
                report = readiness_report(prefix)
                print("Startup readiness: " + report["readiness"])
                for action in report["next_actions"]:
                    print("NEXT: " + action)
                for check in report["owner_checks"]:
                    print("CHECK: " + check)
                return
            if state.get("phase") == "failed":
                raise ValueError(
                    "Stack startup failed: " + state.get("error", "unknown error")
                )
        time.sleep(0.5)
    raise ValueError(
        "Stack startup is still pending; run status and inspect private logs"
    )


def stop(prefix):
    op.verify_install(prefix)
    record = read_state(prefix)
    if not record:
        op.down(prefix)
        print("No managed Sanctum stack is recorded.")
        return
    if process_matches(record):
        op.down(prefix)
        terminate_record(record, seconds=45)
    else:
        op.down(prefix)
        children = record.get("children", {})
        for name in ("webui", "brokers", "mlx"):
            if name in children:
                terminate_record(children[name])
        record["phase"] = "stopped"
        write_state(prefix, record)
    print("Sanctum stopped. Private state and model cache were retained.")


def service_status(prefix):
    receipt = op.verify_install(prefix)
    record = read_state(prefix)
    supervisor = "stopped"
    if record and process_matches(record):
        supervisor = "current" if identity_current(prefix, record) else "stale"
    names = component_tools.selected_brokers(prefix)
    report = {
        "supervisor": supervisor,
        "phase": record.get("phase") if record else "not-started",
        "mlx": http_ready(
            f"http://127.0.0.1:{receipt['mlx_port']}/v1/models",
            lambda value: bootstrap_tools.MODEL
            in [item.get("id") for item in value.get("data", [])],
        ),
        "gateway": op.gateway_socket_ready(receipt["gateway_port"]),
        "brokers": {name: broker_ready(prefix, name) for name in names},
        "webui": http_ready(
            "http://127.0.0.1:28000/health",
            lambda value: value.get("status") is True,
        ),
        "url": "http://127.0.0.1:28000",
    }
    if record and record.get("error"):
        report["error"] = record["error"]
    return report


def status(prefix):
    report = service_status(prefix)
    print(json.dumps(report, indent=2))


def webui_owner_enrollment(prefix):
    database = prefix / "state/webui/webui.db"
    if not database.exists():
        return "not-enrolled"
    if database.is_symlink() or not database.is_file():
        return "unsafe"
    try:
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            admins = connection.execute(
                "select count(*) from user where role = 'admin'"
            ).fetchone()[0]
    except sqlite3.Error:
        return "unavailable"
    return "pass" if admins == 1 else ("not-enrolled" if admins == 0 else "unsafe")


def readiness_report(prefix):
    services = service_status(prefix)
    owner = webui_owner_enrollment(prefix)
    function_sync = op.webui_function_sync(prefix)
    integrations = {}
    for name in ("messages", "gmail", "calendar"):
        configured = component_tools.integration_enabled(prefix, name)
        value = {
            "configured": configured,
            "broker_healthy": services["brokers"].get(name) if configured else None,
        }
        if not configured:
            value["authorization"] = "not-configured"
        elif name == "messages":
            value["authorization"] = "owner-permission-check-required"
        else:
            value["authorization"] = (
                "pass" if google_authorized(prefix, name) else "missing"
            )
        integrations[name] = value
    web_configured = web_enabled(prefix)
    integrations["web"] = {
        "configured": web_configured,
        "authorization": (
            "pass"
            if web_configured and web_authorized(prefix)
            else ("missing" if web_configured else "not-configured")
        ),
    }
    integrations["hosted_models"] = {
        "required": False,
        "authorization": (
            "pass" if openrouter_authorized(prefix) else "not-configured"
        ),
    }
    service_ready = (
        services["supervisor"] == "current"
        and services["phase"] == "ready"
        and services["mlx"]
        and services["gateway"]
        and services["webui"]
        and all(services["brokers"].values())
    )
    required_authorization = all(
        item["authorization"] != "missing"
        for item in integrations.values()
        if item.get("required", True)
    )
    owner_ready = owner == "pass" and function_sync == "pass"
    actions = []
    if not service_ready:
        actions.append("Run ./sanctum status and inspect the private component logs.")
    if owner != "pass":
        actions.append("Open the local WebUI and create its first owner account.")
    if function_sync != "pass":
        actions.append(
            "Import or replace gate/webui/guard.py and gate/webui/pipe.py "
            "in Open WebUI Functions."
        )
    missing_google = [
        name
        for name in ("gmail", "calendar")
        if integrations[name]["authorization"] == "missing"
    ]
    if missing_google:
        actions.append(
            "Stop the stack, then rerun setup with --authorize for read-only "
            + " and ".join(missing_google)
            + " OAuth."
        )
    if integrations["web"]["authorization"] == "missing":
        actions.append(
            "Stop the stack, then rerun setup with --authorize for the web API key."
        )
    owner_checks = []
    if owner_ready:
        owner_checks.append(
            "Select Mac prompt gate in the saved chat; model selection remains "
            "owner-controlled per conversation."
        )
    if integrations["messages"]["configured"]:
        owner_checks.append(
            "Confirm the launching terminal has Full Disk Access before using Messages."
        )
    return {
        "readiness": (
            "ready"
            if service_ready and owner_ready and required_authorization
            else "owner-action-required"
        ),
        "services": services,
        "webui": {"owner_enrollment": owner, "function_sync": function_sync},
        "integrations": integrations,
        "next_actions": actions,
        "owner_checks": owner_checks,
    }


def ready(prefix):
    op.verify_install(prefix)
    print(json.dumps(readiness_report(prefix), indent=2))


def default_prefix():
    configured = os.environ.get("SANCTUM_PREFIX")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local/share/sanctum-v1"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_supervise":
        internal = argparse.ArgumentParser(add_help=False)
        internal.add_argument("_command")
        internal.add_argument("--prefix", type=Path, required=True)
        args = internal.parse_args(argv)
        supervise(args.prefix.absolute())
        return
    parser = argparse.ArgumentParser(prog="sanctum")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "status", "ready", "stop", "logs"):
        command = commands.add_parser(name)
        command.add_argument("--prefix", type=Path, default=default_prefix())
    setup_command = commands.add_parser("setup")
    setup_command.add_argument("--prefix", type=Path, default=default_prefix())
    setup_command.add_argument("--proposal", type=Path)
    setup_command.add_argument("--authorize", action="store_true")
    setup_command.add_argument(
        "--cache-only",
        action="store_true",
        help="refuse model download and require existing cached weights",
    )
    args = parser.parse_args(argv)
    prefix = args.prefix.absolute()
    if args.command == "setup":
        setup(prefix, args.proposal, args.authorize, args.cache_only)
    elif args.command == "start":
        start(prefix)
    elif args.command == "status":
        status(prefix)
    elif args.command == "ready":
        ready(prefix)
    elif args.command == "stop":
        stop(prefix)
    elif args.command == "logs":
        print(prefix / "logs")
    else:
        raise ValueError("Unknown lifecycle command")


def entrypoint():
    os.umask(0o077)
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        raise SystemExit("REFUSED: " + str(exc)) from exc


if __name__ == "__main__":
    entrypoint()
