"""Recover only a proven local-key failure before any Runpod create request.

Run from the reviewed source tree against its stopped, receipt-verified prefix.
This never deletes a pod or volume and refuses any ambiguous provider result.
"""

import argparse
import hashlib
import importlib.util
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# This adapter reads the public key before its first provider mutation.
PRECALL_ADAPTER_SHA256 = (
    "0011c9c8c87306c75de4061d177f745d001e8cae28962b0f17a17a80a5597531"
)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


op = module("release_operator", ROOT / "scripts/release_operator.py")
configure = module("configure_recovery_guard", ROOT / "scripts/configure.py")


def eligible(state, summary, key_missing):
    return (
        state.get("phase") == "DEGRADED"
        and state.get("error") == "allocation_unresolved"
        and state.get("allocation_uncertain") is True
        and state.get("pod_id") is None
        and state.get("allocation_id") is None
        and state.get("manual_stop") is True
        and type(state.get("pod_name")) is str
        and state["pod_name"].startswith("sanctum-private-lead-stage-")
        and summary.get("status") == "ENVIRONMENT_FAILURE"
        and summary.get("reason") == "PRIVATE_LEAD_UNAVAILABLE"
        and summary.get("metrics", {}).get("modelCalls") == 0
        and summary.get("cleanup", {}).get("workspaceCleaned") is True
        and key_missing
    )


def empty_leases(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("Private-lead lease database unavailable")
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
        if conn.execute("select count(*) from leases").fetchone()[0]:
            raise ValueError("Private-lead leases remain")
        if conn.execute(
            "select count(*) from sqlite_master where type='table' and name='experiments'"
        ).fetchone()[0]:
            if any(
                json.loads(row[0]).get("state") != "COMPLETE"
                for row in conn.execute("select record from experiments")
            ):
                raise ValueError("Private-lead experiment remains")


def recover(prefix, task_id):
    op.verify()
    op.verify_install(prefix)
    if op.owns_process(op.process_record(prefix)):
        raise ValueError("Stop candidate gateway before recovery")
    if not configure.active_janitor(prefix):
        raise ValueError("Independent GPU janitor must remain loaded")
    if not re.fullmatch(r"[0-9a-f]{32}", task_id):
        raise ValueError("Exact Work Mode task ID required")
    if op.sha(prefix / "gate/src/runpod.py") != PRECALL_ADAPTER_SHA256:
        raise ValueError("Installed provider adapter does not prove pre-call key read")
    summary_path = (
        prefix / "state/gate/private-lead/work-mode/tasks" / task_id / "summary.json"
    )
    if not summary_path.is_file() or summary_path.is_symlink():
        raise ValueError("Terminal Work Mode receipt required")
    summary = json.loads(summary_path.read_text())
    if summary.get("taskId") != task_id:
        raise ValueError("Work Mode receipt identity mismatch")
    settings = json.loads((prefix / "gate/SETTINGS.json").read_text())
    key = Path(settings["private_lead"]["ssh_private_key"])
    if not key.is_absolute() or Path(str(key) + ".pub").exists():
        raise ValueError("Configured public key is present; failure cause differs")
    retired = json.loads((prefix / "state/gate/gpu.json").read_text())
    if retired.get("phase") != "RETIRED" or not retired.get("retired_confirmed_at"):
        raise ValueError("Legacy GPU retirement unconfirmed")
    empty_leases(prefix / "state/gate/private-lead/control.sqlite")
    sys.path.insert(0, str(prefix / "gate/src"))
    try:
        from lifecycle import PrivateLeadLifecycle

        lc = PrivateLeadLifecycle(settings)
        with lc.lock():
            state = lc.state()
            if not eligible(state, summary, key_missing=True):
                raise ValueError("State does not match pre-allocation key failure")
            if (lc.root / "manual-stop").is_symlink():
                raise ValueError("Unsafe manual stop marker")
            empty_leases(prefix / "state/gate/private-lead/control.sqlite")
            for attempt in range(2):
                rows = lc.provider.pods()
                if any(type(row) is not dict for row in rows):
                    raise ValueError("Runpod pod list has unknown shape")
                if any(
                    str(row.get("name", "")).startswith("sanctum-private-lead-")
                    for row in rows
                ):
                    raise ValueError("Managed Runpod pod still exists")
                if attempt == 0:
                    time.sleep(2)
            # Preserve the exact state and receipt before changing local ownership.
            record = op.private(
                prefix / "state/amendments" / ("preallocation-" + str(time.time_ns()))
            )
            op.write(record / "gpu-before.json", (lc.root / "gpu.json").read_text())
            op.write(
                record / "evidence.json",
                json.dumps(
                    {
                        "schema": "sanctum-private-lead-preallocation-recovery/v1",
                        "task_id": task_id,
                        "task_summary_sha256": hashlib.sha256(
                            summary_path.read_bytes()
                        ).hexdigest(),
                        "configured_public_key_missing": True,
                        "managed_pod_absent_twice": True,
                        "lease_count": 0,
                        "time": time.time(),
                    },
                    indent=2,
                )
                + "\n",
            )
            lc.save(
                state,
                phase="OFFLINE",
                error=None,
                pod_name=None,
                allocation_uncertain=False,
                started_at=None,
                hourly_usd=None,
                absent_confirmed_at=time.time(),
            )
            op.write(record / "complete", "complete\n")
            return record
    finally:
        sys.path.pop(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    try:
        record = recover(args.prefix.resolve(), args.task_id)
        print("Recovered confirmed pre-allocation state. Evidence: " + str(record))
    except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
        raise SystemExit("REFUSED: " + str(exc)) from None
