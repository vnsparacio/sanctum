"""Install pinned optional host runtimes into a verified private prefix."""

import argparse
import importlib.util
import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "release_operator", ROOT / "scripts/release_operator.py"
)
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)
MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"


def runtime_ready(prefix, component):
    runtime = prefix / "runtime" / component
    if component == "web":
        plugins = (
            runtime / "node_modules/@openclaw/parallel-plugin/package.json",
            runtime / "node_modules/@openclaw/firecrawl-plugin/package.json",
        )
        openclaw = runtime / "node_modules/openclaw"
        return (
            runtime.is_dir()
            and not runtime.is_symlink()
            and all(path.is_file() and not path.is_symlink() for path in plugins)
            and openclaw.is_symlink()
            and openclaw.resolve() == (ROOT / "node_modules/openclaw").resolve()
        )
    launcher = {
        "mlx": runtime / "bin/mlx_lm.server",
        "webui": runtime / "bin/open-webui",
    }[component]
    python = runtime / "bin/python"
    return (
        runtime.is_dir()
        and not runtime.is_symlink()
        and launcher.is_file()
        and not launcher.is_symlink()
        and python.is_file()
        and python.resolve().is_file()
    )


def validate_runtime(prefix, component):
    runtime = prefix / "runtime" / component
    if not runtime_ready(prefix, component):
        raise SystemExit("Runtime is partial or unexpected; nothing overwritten")
    if component in ("mlx", "webui"):
        subprocess.run(
            ["uv", "pip", "check", "--python", str(runtime / "bin/python")],
            check=True,
        )
    else:
        for name in ("package.json", "package-lock.json"):
            if (runtime / name).read_bytes() != (
                ROOT / "host/web-runtime" / name
            ).read_bytes():
                raise SystemExit("Optional web runtime package identity drift")


def bootstrap(component, prefix):
    prefix = prefix.absolute()
    op.verify()
    op.verify_install(prefix)
    if component == "mlx" and (
        platform.system() != "Darwin" or platform.machine() != "arm64"
    ):
        raise SystemExit("MLX requires an Apple Silicon Mac")
    runtime = prefix / "runtime" / component
    if runtime.exists():
        if runtime_ready(prefix, component):
            validate_runtime(prefix, component)
            print("Runtime already complete; unchanged:", component)
            return
        raise SystemExit(
            "Runtime is partial or unexpected; inspect it or use a new prefix. "
            "Nothing overwritten."
        )
    op.private(prefix / "runtime")
    if component == "web":
        op.private(runtime)
        for name in ("package.json", "package-lock.json"):
            op.write(runtime / name, (ROOT / "host/web-runtime" / name).read_text())
        subprocess.run(
            [
                "npm",
                "ci",
                "--prefix",
                str(runtime),
                "--ignore-scripts",
                "--legacy-peer-deps",
                "--no-audit",
                "--no-fund",
            ],
            check=True,
        )
        (runtime / "node_modules/openclaw").symlink_to(
            ROOT / "node_modules/openclaw", target_is_directory=True
        )
        print(
            "Installed pinned optional web plugins; configure web integration "
            "and credentials separately."
        )
        return
    subprocess.run(
        [
            "uv",
            "venv",
            "--python",
            "3.12" if component == "mlx" else "3.11",
            str(runtime),
        ],
        check=True,
    )
    requirements = (
        ROOT
        / "host"
        / ("requirements-macos.txt" if component == "mlx" else "requirements-webui.txt")
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(runtime / "bin/python"),
            "-r",
            str(requirements),
        ],
        check=True,
    )
    subprocess.run(
        ["uv", "pip", "check", "--python", str(runtime / "bin/python")], check=True
    )
    print("Installed isolated runtime:", component)


def ensure_model(prefix, cache_only=False):
    prefix = prefix.absolute()
    if not runtime_ready(prefix, "mlx"):
        raise SystemExit("Bootstrap the MLX runtime before preparing model weights")
    code = "from mlx_lm.utils import _download; " f"print(_download({MODEL!r}))"
    env = {**os.environ, "HF_HUB_DISABLE_XET": "1"}
    if cache_only:
        env["HF_HUB_OFFLINE"] = "1"
    try:
        subprocess.run(
            [str(prefix / "runtime/mlx/bin/python"), "-c", code],
            cwd=prefix,
            env=env,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        message = (
            "Pinned local model is not present in the existing Hugging Face cache"
            if cache_only
            else "Pinned local model download failed"
        )
        raise SystemExit(message) from exc
    print("Pinned local model is cached:", MODEL)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("component", choices=["mlx", "webui", "web"])
    p.add_argument("--prefix", type=Path, default=ROOT / ".local")
    p.add_argument(
        "--prepare-model",
        action="store_true",
        help="download the pinned local model after installing MLX",
    )
    p.add_argument(
        "--cache-only",
        action="store_true",
        help="require existing model weights instead of downloading them",
    )
    a = p.parse_args()
    bootstrap(a.component, a.prefix)
    if a.prepare_model:
        if a.component != "mlx":
            raise SystemExit("--prepare-model is supported for mlx only")
        ensure_model(a.prefix, a.cache_only)


if __name__ == "__main__":
    main()
