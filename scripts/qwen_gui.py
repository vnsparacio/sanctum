"""Launch the Qwen Code VS Code GUI with Sanctum's supervised model bridge.

The extension bundles its own Qwen CLI.  It inherits the one-session bridge
token from this launcher; opening VS Code directly cannot start a private GPU.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

import qwen_interactive as bridge

EXTENSION = "qwenlm.qwen-code-vscode-ide-companion"
VERSION = bridge.QWEN_VERSION
GUI_DIRECTORY = "qwen-gui"


def code_binary() -> str:
    code = shutil.which("code")
    if not code:
        raise ValueError("VS Code is unavailable; install it before Qwen GUI setup")
    result = subprocess.run(
        [code, "--version"], capture_output=True, text=True, timeout=20
    )
    if result.returncode:
        raise ValueError("VS Code could not report its version")
    try:
        major, minor = (
            int(part) for part in result.stdout.splitlines()[0].split(".")[:2]
        )
    except (ValueError, IndexError) as error:
        raise ValueError("VS Code reported an invalid version") from error
    if (major, minor) < (1, 96):
        raise ValueError("Qwen Code requires VS Code 1.96 or newer")
    return code


def gui_paths(prefix: Path) -> tuple[Path, Path]:
    root = prefix / GUI_DIRECTORY
    if root.is_symlink():
        raise ValueError("Qwen GUI directory is a symlink")
    return root / "user-data", root / "extensions"


def installed_extension(code: str, user_data: Path, extensions: Path) -> bool:
    result = subprocess.run(
        [
            code,
            "--user-data-dir",
            str(user_data),
            "--extensions-dir",
            str(extensions),
            "--list-extensions",
            "--show-versions",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    matches = [
        line for line in result.stdout.splitlines() if line.startswith(EXTENSION + "@")
    ]
    if matches and matches != [f"{EXTENSION}@{VERSION}"]:
        raise ValueError("Qwen GUI extension differs from the reviewed version")
    return bool(matches)


def install_profile(prefix: Path, code: str) -> tuple[Path, Path]:
    """Pin the GUI extension and its update policy in private owner state."""
    user_data, extensions = gui_paths(prefix)
    for directory in (user_data, extensions):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or directory.stat().st_mode & 0o077:
            raise ValueError("Qwen GUI profile directory is not owner-only")
    settings_path = user_data / "User/settings.json"
    settings_path.parent.mkdir(mode=0o700, exist_ok=True)
    if settings_path.is_symlink():
        raise ValueError("Qwen GUI VS Code settings are a symlink")
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
        if not isinstance(settings, dict):
            raise ValueError("Qwen GUI VS Code settings are invalid")
    else:
        settings = {}
    settings["extensions.autoUpdate"] = False
    settings["extensions.autoCheckUpdates"] = False
    temporary = settings_path.with_name("settings.json.new")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("Qwen GUI settings temporary path already exists")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(settings, output, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, settings_path)
    if not installed_extension(code, user_data, extensions):
        subprocess.run(
            [
                code,
                "--user-data-dir",
                str(user_data),
                "--extensions-dir",
                str(extensions),
                "--install-extension",
                f"{EXTENSION}@{VERSION}",
            ],
            check=True,
            timeout=180,
        )
    if not installed_extension(code, user_data, extensions):
        raise ValueError("Pinned Qwen GUI extension was not installed")
    return user_data, extensions


def install(prefix: Path) -> Path:
    """Install the pinned extension and canonical GUI launcher."""
    prefix = prefix.expanduser().resolve(strict=True)
    settings = bridge.installed_settings(prefix)
    source = Path(__file__).resolve().parents[1]
    receipt = json.loads((prefix / "receipt.json").read_text())
    if receipt.get("source") != str(source):
        raise ValueError("Install the GUI launcher from the canonical Sanctum checkout")
    install_profile(prefix, code_binary())
    launcher = Path.home() / ".local/bin/qwen-gui"
    content = (
        "#!/bin/sh\nexec "
        + shlex.quote(settings["python"])
        + " -B "
        + shlex.quote(str(source / "scripts/qwen_gui.py"))
        + ' "$@"\n'
    )
    if launcher.exists() or launcher.is_symlink():
        if launcher.is_symlink() or launcher.read_text() != content:
            raise ValueError("An existing qwen-gui launcher needs manual review")
    else:
        launcher.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        fd = os.open(launcher, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o755)
        with os.fdopen(fd, "w") as output:
            output.write(content)
    return launcher


def run(prefix: Path, project: Path) -> int:
    prefix = prefix.expanduser().resolve(strict=True)
    project = project.expanduser().resolve(strict=True)
    if not project.is_dir():
        raise ValueError("Choose a project directory for Qwen Code")
    settings = bridge.installed_settings(prefix)
    code = code_binary()
    user_data, extensions = gui_paths(prefix)
    if not installed_extension(code, user_data, extensions):
        raise ValueError("Run qwen_gui.py --install to install the pinned Qwen GUI")
    bridge.configure_qwen(
        Path.home() / ".qwen/settings.json", settings["private_lead"]["alias"]
    )
    python = settings["python"]
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
        raise ValueError("Private model lifecycle cannot be resumed")
    token = secrets.token_urlsafe(32)
    hold = bridge.ModelHold(
        prefix,
        python,
        settings["private_lead"]["alias"],
        settings["private_lead"]["local_port"],
    )
    server = bridge.ModelServer(("127.0.0.1", bridge.MODEL_PORT), hold, token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    environment = os.environ.copy()
    environment["SANCTUM_QWEN_LOCAL_KEY"] = token
    environment["QWEN_CODE_DISABLE_TELEMETRY"] = "1"
    environment["QWEN_CODE_DISABLE_AUTO_UPDATE"] = "1"
    child = None
    previous_term = signal.getsignal(signal.SIGTERM)

    def terminate(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        print(
            "Qwen Code GUI is opening. The GPU starts on the first private-model message.",
            flush=True,
        )
        child = subprocess.Popen(
            [
                code,
                "--new-window",
                "--wait",
                "--user-data-dir",
                str(user_data),
                "--extensions-dir",
                str(extensions),
                str(project),
            ],
            cwd=project,
            env=environment,
        )
        try:
            return child.wait()
        except KeyboardInterrupt:
            return 130
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        hold.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="qwen-gui")
    parser.add_argument("project", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument(
        "--sanctum-prefix", type=Path, default=Path.home() / ".local/share/sanctum-v1"
    )
    parser.add_argument("--install", action="store_true")
    options = parser.parse_args(argv)
    if options.install:
        print(
            "Installed Qwen Code GUI launcher: " + str(install(options.sanctum_prefix))
        )
        return 0
    return run(options.sanctum_prefix, options.project)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
    ) as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        raise SystemExit(1) from error
