"""Installed owner-only diagnostic control; commands are never run on import.

No operation reads tasks, prompts, model responses or arbitrary provider bodies.
The only allocation path requires the separate live authorization flag.
"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "src"))
from common import Refused, canonical, load_settings, strict_json, verify_release
from experiment import (
    ExperimentLedger,
    installed_identity,
    process_identity,
    validate_binding,
)
from experiment_lifecycle import DiagnosticLifecycle, ExperimentSupervisor
from lifecycle import PrivateLeadLifecycle
from retirement import require_reconciled


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser()
    p.add_argument(
        "command",
        choices=["identity", "create", "status", "allocate", "ready", "stop", "sweep"],
    )
    p.add_argument("--binding", type=Path)
    p.add_argument("--owner-pid", type=int)
    p.add_argument("--hourly-ceiling", type=float, default=0)
    p.add_argument("--owner-authorized-one-allocation", action="store_true")
    p.add_argument(
        "--outcome",
        choices=["CANCELLED", "PROBE_FAILED", "PROBES_COMPLETE"],
        default="CANCELLED",
    )
    a = p.parse_args()
    verify_release()
    settings = load_settings()
    identity = installed_identity()
    if a.command == "identity":
        return identity
    if not a.binding or a.binding.is_symlink() or a.binding.stat().st_mode & 0o077:
        raise Refused("experiment_binding_file")
    b = validate_binding(strict_json(a.binding.read_text()))
    if any(b[k] != identity[k] for k in identity):
        raise Refused("experiment_identity")
    ledger = ExperimentLedger(Path(settings["state_directory"]) / "private-lead")
    if a.command == "create":
        require_reconciled(settings["state_directory"], confirmed=True)
        # Creating metadata does not allocate or infer and cannot grant spending.
        return ledger.create(
            b,
            owner_pid=a.owner_pid,
            owner_process=process_identity(a.owner_pid),
            ordinary_root=Path(settings["state_directory"]),
        )
    if a.command == "status":
        return ledger.snapshot(b)
    if a.command == "stop":
        ledger.stop(b, a.outcome)
        return ledger.snapshot(b)
    lc = PrivateLeadLifecycle(settings)
    if a.command == "sweep":
        return ExperimentSupervisor(ledger, lc).tick()
    if not a.owner_authorized_one_allocation:
        raise Refused("experiment_live_authorization_required")
    diagnostic = DiagnosticLifecycle(lc, b, identity, ledger)

    def stop(*_):
        ledger.stop(
            b, "DEADLINE" if time.time() >= b["deadline"] - 120 else "CANCELLED"
        )
        raise Refused("experiment_cancelled")

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, diagnostic.dispatch.timeout(900))
    with ledger.transaction() as c:
        r = ledger._bound(c, b)
        ledger._admit(r)
        r.update(control_pid=os.getpid(), control_process=process_identity(os.getpid()))
        ledger._write(c, r)
    try:
        if a.command == "allocate":
            diagnostic.allocate(a.hourly_ceiling)
        elif a.command == "ready":
            diagnostic.ready()
    except BaseException:
        ledger.stop(
            b, "ALLOCATION_FAILED" if a.command == "allocate" else "READINESS_FAILED"
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        with ledger.transaction() as c:
            r = ledger._bound(c, b)
            r.update(control_pid=None, control_process=None)
            ledger._write(c, r)
    return ledger.snapshot(b)


if __name__ == "__main__":
    try:
        print(canonical(main()))
    except Exception as error:
        code = (
            str(error)
            if type(error) is Refused and str(error).replace("_", "").isalnum()
            else "experiment_control_failed"
        )
        print(canonical({"status": "REFUSED", "code": code}))
        sys.exit(1)
