"""Install pinned optional host runtimes into a verified private prefix."""

import argparse
import importlib.util
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "release_operator", ROOT / "scripts/release_operator.py"
)
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("component", choices=["mlx", "webui", "web"])
    p.add_argument("--prefix", type=Path, default=ROOT / ".local")
    a = p.parse_args()
    prefix = a.prefix.absolute()
    op.verify()
    op.verify_install(prefix)
    if a.component == "mlx" and (
        platform.system() != "Darwin" or platform.machine() != "arm64"
    ):
        raise SystemExit("MLX requires an Apple Silicon Mac")
    runtime = prefix / "runtime" / a.component
    if runtime.exists():
        raise SystemExit(
            "Runtime already exists; inspect it or use a new prefix. Nothing overwritten."
        )
    op.private(prefix / "runtime")
    if a.component == "web":
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
            "Installed pinned optional web plugins; configure web integration and credentials separately."
        )
        return
    subprocess.run(
        [
            "uv",
            "venv",
            "--python",
            "3.12" if a.component == "mlx" else "3.11",
            str(runtime),
        ],
        check=True,
    )
    requirements = (
        ROOT
        / "host"
        / (
            "requirements-macos.txt"
            if a.component == "mlx"
            else "requirements-webui.txt"
        )
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
    print("Installed isolated runtime:", a.component)


if __name__ == "__main__":
    main()
