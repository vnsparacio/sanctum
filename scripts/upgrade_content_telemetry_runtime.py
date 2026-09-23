"""Stopped-gateway, reversible content telemetry runtime closure repair."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "release_operator", ROOT / "scripts/release_operator.py"
)
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)

GATE_FILES = (
    "content-telemetry/ajv.mjs",
    "content-telemetry/benchmark.mjs",
    "content-telemetry/contract.mjs",
    "content-telemetry/quality.mjs",
)
SCHEMA_FILES = (
    "benchmark-dataset-v1.schema.json",
    "benchmark-replay-v1.schema.json",
    "content-telemetry-v1.schema.json",
    "quality-annotation-v1.schema.json",
)
SCHEMA = "sanctum-content-telemetry-runtime-amendment/v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, data):
    temporary = path.with_name(path.name + ".content-telemetry-tmp")
    op.write(temporary, data)
    os.replace(temporary, path)


def render(name):
    text = (ROOT / "gate" / name).read_text()
    return text.replace("@SANCTUM_PACKAGE@", str(ROOT / "package.json"))


def targets(prefix):
    return [
        *(("gate/" + name, prefix / "gate" / name) for name in GATE_FILES),
        *(
            ("config/schemas/" + name, prefix / "config/schemas" / name)
            for name in SCHEMA_FILES
        ),
    ]


def apply(prefix):
    op.verify()
    receipt = op.verify_install(prefix)
    if op.owns_process(op.process_record(prefix)):
        raise ValueError("Stop candidate gateway before runtime amendment")
    record = (
        prefix
        / "state/amendments"
        / ("content-telemetry-runtime-" + str(time.time_ns()))
    )
    op.private(record)
    before = {}
    for name, target in targets(prefix):
        before[name] = "present" if target.exists() else "absent"
        if target.exists():
            if target.is_symlink():
                raise ValueError("Unsafe amendment target")
            backup = record / name
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(target, backup)
    shutil.copy2(prefix / "gate/FREEZE.json", record / "gate-FREEZE.json")
    shutil.copy2(prefix / "receipt.json", record / "receipt.json")

    for name in GATE_FILES:
        target = prefix / "gate" / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic(target, render(name))
    for name in SCHEMA_FILES:
        target = prefix / "config/schemas" / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic(target, (ROOT / "config/schemas" / name).read_text())

    freeze = json.loads((prefix / "gate/FREEZE.json").read_text())
    for name in GATE_FILES:
        freeze[name] = sha(prefix / "gate" / name)
    atomic(prefix / "gate/FREEZE.json", json.dumps(freeze, indent=2) + "\n")
    after = {}
    for name, target in targets(prefix):
        receipt["files"][name] = sha(target)
        after[name] = receipt["files"][name]
    receipt["files"]["gate/FREEZE.json"] = sha(prefix / "gate/FREEZE.json")
    receipt["content_telemetry_source_manifest_sha256"] = sha(
        ROOT / "SOURCE-MANIFEST.json"
    )
    atomic(prefix / "receipt.json", json.dumps(receipt, indent=2) + "\n")

    transaction = {
        "schema": SCHEMA,
        "before": before,
        "after": after,
        "source_manifest_sha256": sha(ROOT / "SOURCE-MANIFEST.json"),
        "source_commit": subprocess.run(
            ["/usr/bin/git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
    }
    atomic(record / "transaction.json", json.dumps(transaction, indent=2) + "\n")
    op.write(record / "complete", "complete\n")
    print(
        "Applied content telemetry runtime amendment. Private rollback record: "
        + str(record)
    )
    return record


def rollback(prefix, record):
    op.verify_install(prefix)
    if op.owns_process(op.process_record(prefix)):
        raise ValueError("Stop candidate gateway before rollback")
    record = record.absolute()
    if not record.is_relative_to((prefix / "state/amendments").absolute()):
        raise ValueError("Rollback record must belong to prefix")
    transaction = json.loads((record / "transaction.json").read_text())
    if transaction.get("schema") != SCHEMA or not (record / "complete").is_file():
        raise ValueError("Wrong or incomplete rollback transaction")
    for name, expected in transaction["after"].items():
        target = prefix / name
        if not target.is_file() or target.is_symlink() or sha(target) != expected:
            raise ValueError("Installed runtime changed after amendment: " + name)
    for name, state in transaction["before"].items():
        target = prefix / name
        if state == "present":
            atomic(target, (record / name).read_text())
        else:
            target.unlink()
    atomic(prefix / "gate/FREEZE.json", (record / "gate-FREEZE.json").read_text())
    atomic(prefix / "receipt.json", (record / "receipt.json").read_text())
    op.write(record / "rolled-back", "rolled-back\n")
    print("Restored content telemetry runtime; private state preserved.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--rollback", type=Path)
    args = parser.parse_args()
    if args.rollback:
        rollback(args.prefix.absolute(), args.rollback)
    else:
        apply(args.prefix.absolute())


if __name__ == "__main__":
    main()
