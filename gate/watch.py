"""Mac-only compute janitor. Single process, no allocation or inference capability."""

import argparse
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "src"))
from common import atomic, canonical, load_settings, private_dir, verify_release
from experiment import ExperimentLedger
from lifecycle import Private80BLifecycle, PrivateLeadLifecycle


def main():
    args = argparse.ArgumentParser()
    args.add_argument(
        "--release", choices=["PRIVATE_80B", "PRIVATE_LEAD"], default="PRIVATE_80B"
    )
    release = args.parse_args()
    os.umask(0o077)
    verify_release()
    settings = load_settings()
    root = (
        private_dir(Path(settings["state_directory"]) / "private-lead")
        if release.release == "PRIVATE_LEAD"
        else private_dir(settings["state_directory"])
    )
    fd = os.open(root / "watch.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return
    awake = None
    try:
        awake = subprocess.Popen(
            ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        lc = (
            PrivateLeadLifecycle(settings)
            if release.release == "PRIVATE_LEAD"
            else Private80BLifecycle(settings)
        )
        lc.experiment_supervisor = True
        while True:
            if awake.poll() is not None:
                raise RuntimeError("sleep_guard_unavailable")
            atomic(
                root / "watch.ready",
                canonical({"pid": os.getpid(), "heartbeat": time.time()}).encode(),
            )
            try:
                lc.sweep()
                s = lc.state()
                status = lc.status()
                if (
                    s.get("phase") in ("OFFLINE", "RETIRED")
                    and not s.get("pod_id")
                    and not s.get("allocation_uncertain")
                    and not status["leases"]
                    and not (
                        release.release == "PRIVATE_LEAD"
                        and ExperimentLedger(root).current()
                    )
                ):
                    return
            except Exception:
                # Never infer deletion from a failed provider read; next sweep retries
                # only reconciliation/cleanup, never allocation or prompt delivery.
                pass
            time.sleep(15)
    finally:
        (root / "watch.ready").unlink(missing_ok=True)
        if awake:
            awake.terminate()
            awake.wait(timeout=5)
        os.close(fd)


if __name__ == "__main__":
    main()
