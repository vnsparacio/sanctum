"""Interactive Qwen Code with a Mac-owned, demand-started private model.

Qwen's coding tools run in the owner's project directory.  Only model traffic
for the configured private-lead alias goes through this local bridge.  The
bridge starts the existing bounded PRIVATE_LEAD hold on the first model call.
"""

from __future__ import annotations

import argparse
import hmac
import http.client
import json
import os
import queue
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODEL_PORT = 38081
MAX_BODY = 2 * 1024 * 1024
WINDOW_SECONDS = 45 * 60
MAX_COMPUTE_USD = 5.0
STARTUP_SECONDS = 12 * 60
QWEN_VERSION = "0.24.6"


def installed_settings(prefix: Path) -> dict:
    settings_path = prefix / "gate/SETTINGS.json"
    if settings_path.is_symlink() or not settings_path.is_file():
        raise ValueError("Installed Sanctum settings are unavailable")
    settings = json.loads(settings_path.read_text())
    lead = settings.get("private_lead", {})
    if (
        lead.get("logical_profile") != "PRIVATE_LEAD"
        or lead.get("enabled") is not True
        or lead.get("auto_start") is not False
        or settings.get("gpu", {}).get("auto_start") is not False
        or not isinstance(lead.get("local_port"), int)
        or not isinstance(lead.get("alias"), str)
    ):
        raise ValueError("Private model configuration is not qualified")
    return settings


def qwen_binary(prefix: Path) -> Path:
    path = prefix / "tools" / f"qwen-code-{QWEN_VERSION}" / "node_modules/.bin/qwen"
    if not path.is_file():
        raise ValueError("Qwen Code is not installed; run the private setup first")
    result = subprocess.run(
        [str(path), "--version"], capture_output=True, text=True, timeout=10
    )
    if result.returncode or result.stdout.strip() != QWEN_VERSION:
        raise ValueError("Qwen Code version differs from the reviewed pin")
    return path


def install(prefix: Path) -> Path:
    """Install the pinned Mac CLI and its single local model picker entry."""
    prefix = prefix.expanduser().resolve(strict=True)
    settings = installed_settings(prefix)
    source = Path(__file__).resolve().parents[1]
    receipt = json.loads((prefix / "receipt.json").read_text())
    if receipt.get("source") != str(source):
        raise ValueError("Use the reviewed canonical Sanctum checkout for installation")
    launcher = Path.home() / ".local/bin/qwen"
    python = settings["python"]
    content = (
        "#!/bin/sh\nexec "
        + shlex.quote(python)
        + " -B "
        + shlex.quote(str(source / "scripts/qwen_interactive.py"))
        + ' "$@"\n'
    )
    if launcher.exists() or launcher.is_symlink():
        if launcher.is_symlink() or launcher.read_text() != content:
            raise ValueError("An existing qwen launcher needs manual review")
    tools = prefix / "tools"
    tools.mkdir(mode=0o700, exist_ok=True)
    if tools.is_symlink() or tools.stat().st_mode & 0o077:
        raise ValueError("Private Qwen tools directory is unsafe")
    package = tools / f"qwen-code-{QWEN_VERSION}"
    if not package.exists():
        package.mkdir(mode=0o700)
    if package.is_symlink() or package.stat().st_mode & 0o077:
        raise ValueError("Private Qwen package directory is unsafe")
    if not (package / "node_modules/.bin/qwen").is_file():
        recipe = source / "gate/runtime/qwen-code-image"
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(recipe / name, package / name)
        subprocess.run(
            ["npm", "ci", "--prefix", str(package), "--omit=dev"], check=True
        )
    qwen_binary(prefix)
    settings_path = Path.home() / ".qwen/settings.json"
    if settings_path.is_symlink() or settings_path.parent.is_symlink():
        raise ValueError("Qwen settings path is a symlink")
    if settings_path.exists():
        backup_dir = prefix / "state/qwen-interactive"
        backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if backup_dir.is_symlink() or backup_dir.stat().st_mode & 0o077:
            raise ValueError("Private Qwen backup directory is unsafe")
        backup = backup_dir / f"settings-before-{time.time_ns()}.json"
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(settings_path.read_bytes())
    configure_qwen(settings_path, settings["private_lead"]["alias"])
    launcher.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    if not launcher.exists():
        fd = os.open(launcher, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o755)
        with os.fdopen(fd, "w") as output:
            output.write(content)
    return launcher


def managed_model_entry(alias: str) -> dict:
    return {
        "id": alias,
        "name": "Sanctum private 122B (Runpod on demand)",
        "description": "Starts the private GPU on the first message; stops when Qwen exits",
        "envKey": "SANCTUM_QWEN_LOCAL_KEY",
        "baseUrl": f"http://127.0.0.1:{MODEL_PORT}/v1",
        "wireApi": "chat-completions",
        "generationConfig": {
            "timeout": 900000,
            "streamIdleTimeoutMs": 300000,
            "maxRetries": 0,
            "contextWindowSize": 32768,
            "samplingParams": {"max_tokens": 6144},
        },
    }


def configure_qwen(settings_path: Path, alias: str) -> bool:
    """Add one user model without changing other Qwen providers or settings."""
    if settings_path.is_symlink() or settings_path.parent.is_symlink():
        raise ValueError("Qwen settings path is a symlink")
    settings_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fresh = not settings_path.exists()
    if not fresh:
        settings = json.loads(settings_path.read_text())
        if not isinstance(settings, dict):
            raise ValueError("Qwen settings are not a JSON object")
    else:
        settings = {}
    providers = settings.setdefault("modelProviders", {})
    protocols = settings.setdefault("providerProtocol", {})
    if not isinstance(providers, dict) or not isinstance(protocols, dict):
        raise ValueError("Qwen provider settings are invalid")
    if protocols.get("sanctum") not in (None, "openai"):
        raise ValueError("Existing Sanctum provider uses another protocol")
    current = providers.get("sanctum", [])
    if not isinstance(current, list) or any(
        not isinstance(item, dict) for item in current
    ):
        raise ValueError("Existing Sanctum models are invalid")
    desired = managed_model_entry(alias)
    others = [item for item in current if item.get("id") != alias]
    if others:
        raise ValueError(
            "Existing Sanctum provider has other models; inspect it manually"
        )
    if current == [desired] and protocols.get("sanctum") == "openai":
        return False
    providers["sanctum"] = [desired]
    protocols["sanctum"] = "openai"
    if fresh:
        settings["security"] = {"auth": {"selectedType": "openai"}}
        settings["model"] = {"name": alias}
    temporary = settings_path.with_name(settings_path.name + ".new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(settings, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, settings_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return True


class ModelHold:
    def __init__(self, prefix: Path, python: str, alias: str, port: int):
        self.prefix, self.python, self.alias, self.port = prefix, python, alias, port
        self.process: subprocess.Popen | None = None
        self.events: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        self.deadline = None

    def _reader(self, stream):
        for line in stream:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                value = {"event": "INVALID_OUTPUT"}
            self.events.put(value)

    def ensure_ready(self):
        with self.lock:
            if self.process is not None:
                if self.process.poll() is not None or time.time() >= self.deadline:
                    raise ValueError(
                        "Private model session has ended; restart Qwen Code"
                    )
                return
            self.deadline = time.time() + WINDOW_SECONDS
            command = [
                self.python,
                "-B",
                str(self.prefix / "gate/manage.py"),
                "hold",
                "--release",
                "PRIVATE_LEAD",
                "--until-epoch",
                str(self.deadline),
                "--max-compute-usd",
                str(MAX_COMPUTE_USD),
            ]
            self.process = subprocess.Popen(
                command,
                cwd=self.prefix,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
            threading.Thread(
                target=self._reader, args=(self.process.stdout,), daemon=True
            ).start()
            end = time.monotonic() + STARTUP_SECONDS
            try:
                while time.monotonic() < end:
                    if self.process.poll() is not None and self.events.empty():
                        raise ValueError(
                            "Private model startup failed; inspect the local lifecycle status"
                        )
                    try:
                        event = self.events.get(timeout=1)
                    except queue.Empty:
                        continue
                    if event.get("event") == "READY":
                        return
                    if event.get("event") == "INVALID_OUTPUT":
                        raise ValueError("Private model hold returned invalid output")
                raise ValueError("Private model startup exceeded 12 minutes")
            except Exception:
                self.close()
                raise

    def close(self):
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            raise ValueError(
                "Private model cleanup is pending; independent janitor remains active"
            )
        if process.stdout:
            process.stdout.close()
        if process.returncode:
            raise ValueError("Private model hold did not confirm clean release")


class ModelServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, hold: ModelHold, token: str):
        super().__init__(address, ModelHandler)
        self.hold, self.token = hold, token


class ModelHandler(BaseHTTPRequestHandler):
    server: ModelServer

    def log_message(self, _format, *_args):
        # Request bodies and authorization values never enter a local log.
        pass

    def authorized(self) -> bool:
        return hmac.compare_digest(
            self.headers.get("Authorization", ""), "Bearer " + self.server.token
        )

    def reply(self, status: int, value: dict):
        body = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.authorized():
            return self.reply(401, {"error": "local_auth_required"})
        if self.path != "/v1/models":
            return self.reply(404, {"error": "route_not_found"})
        self.reply(
            200,
            {
                "object": "list",
                "data": [{"id": self.server.hold.alias, "object": "model"}],
            },
        )

    def do_POST(self):
        if not self.authorized():
            return self.reply(401, {"error": "local_auth_required"})
        if self.path != "/v1/chat/completions":
            return self.reply(404, {"error": "route_not_found"})
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > MAX_BODY:
                return self.reply(413, {"error": "request_too_large"})
            body = self.rfile.read(length)
            request = json.loads(body)
            if (
                not isinstance(request, dict)
                or request.get("model") != self.server.hold.alias
            ):
                return self.reply(400, {"error": "unknown_model"})
            self.server.hold.ensure_ready()
            connection = http.client.HTTPConnection(
                "127.0.0.1", self.server.hold.port, timeout=900
            )
            connection.request(
                "POST",
                "/v1/chat/completions",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            upstream = connection.getresponse()
            self.send_response(upstream.status)
            self.send_header(
                "Content-Type", upstream.getheader("Content-Type", "application/json")
            )
            self.send_header("Connection", "close")
            self.end_headers()
            while chunk := upstream.read(65536):
                self.wfile.write(chunk)
                self.wfile.flush()
            connection.close()
        except (
            ValueError,
            OSError,
            json.JSONDecodeError,
            http.client.HTTPException,
        ) as error:
            if not self.headers_sent:
                self.reply(503, {"error": str(error)[:160]})

    @property
    def headers_sent(self):
        return self._headers_buffer == [] if hasattr(self, "_headers_buffer") else False


def run(prefix: Path, args: list[str], *, cwd: Path | None = None) -> int:
    prefix = prefix.expanduser().resolve(strict=True)
    settings = installed_settings(prefix)
    qwen = qwen_binary(prefix)
    alias = settings["private_lead"]["alias"]
    qwen_settings = Path.home() / ".qwen/settings.json"
    configure_qwen(qwen_settings, alias)
    python = settings["python"]
    if not Path(python).is_file():
        raise ValueError("Installed Sanctum Python is unavailable")
    resume = subprocess.run(
        [
            python,
            "-B",
            str(prefix / "gate/manage.py"),
            "resume",
            "--release",
            "PRIVATE_LEAD",
        ],
        cwd=prefix,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if resume.returncode:
        raise ValueError(
            "Private model lifecycle cannot be resumed; inspect Sanctum status"
        )
    token = secrets.token_urlsafe(32)
    hold = ModelHold(prefix, python, alias, settings["private_lead"]["local_port"])
    server = ModelServer(("127.0.0.1", MODEL_PORT), hold, token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    environment = os.environ.copy()
    environment["SANCTUM_QWEN_LOCAL_KEY"] = token
    environment["QWEN_CODE_DISABLE_TELEMETRY"] = "1"
    environment["QWEN_CODE_DISABLE_AUTO_UPDATE"] = "1"
    print("Qwen Code is ready. Select 'Sanctum private 122B' with /model.")
    print(
        "The GPU starts on the first message to that model, then stops when Qwen exits."
    )
    child = None
    try:
        child = subprocess.Popen(
            [str(qwen), "--approval-mode", "default", *args],
            cwd=cwd or Path.cwd(),
            env=environment,
        )
        try:
            return child.wait()
        except KeyboardInterrupt:
            return 130
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        hold.close()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--install":
        installer = argparse.ArgumentParser(prog="qwen --install")
        installer.add_argument("--install", action="store_true")
        installer.add_argument(
            "--sanctum-prefix",
            type=Path,
            default=Path.home() / ".local/share/sanctum-v1",
        )
        options = installer.parse_args(argv)
        print(
            "Installed interactive Qwen Code launcher: "
            + str(install(options.sanctum_prefix))
        )
        return 0
    parser = argparse.ArgumentParser(prog="qwen", add_help=False)
    parser.add_argument(
        "--sanctum-prefix", type=Path, default=Path.home() / ".local/share/sanctum-v1"
    )
    known, qwen_args = parser.parse_known_args(argv)
    return run(known.sanctum_prefix, qwen_args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        raise SystemExit(1) from error
