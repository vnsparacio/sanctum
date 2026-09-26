"""Owner-operated local maintenance. Never sends prompts to hosted models."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "src"))
from common import Refused, canonical, load_settings, verify_release
from lifecycle import Private80BLifecycle, PrivateLeadLifecycle
from media import prepare

RELEASES = ("PRIVATE_80B", "PRIVATE_LEAD")


def work_intent_preflight():
    node = "@NODE@"
    if node.startswith("@"):
        node = shutil.which("node")
    if not node:
        raise Refused("structured_schema_preflight")
    result = subprocess.run(
        [node, str(BASE / "preflight-work-intent.mjs")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise Refused("structured_schema_preflight") from None
    if (
        result.returncode
        or value.get("ok") is not True
        or value.get("schema") != "sanctum-work-intent-preflight/v1"
    ):
        raise Refused("structured_schema_preflight")
    return value


def lifecycle(settings, release):
    return (
        PrivateLeadLifecycle(settings)
        if release == "PRIVATE_LEAD"
        else Private80BLifecycle(settings)
    )


def sweep_all(settings):
    """Let the independent janitor reconcile both mutually exclusive releases."""
    result = {}
    succeeded = 0
    for release in RELEASES:
        try:
            lc = lifecycle(settings, release)
            lc.sweep()
            result[release] = lc.status()
            succeeded += 1
        except Exception as error:
            result[release] = {
                "phase": "UNAVAILABLE",
                "error": (
                    str(error) if type(error) is Refused else "local_operation_failed"
                ),
            }
    if not succeeded:
        raise Refused("janitor_all_releases_failed")
    return result


def hold_private_lead(
    lc, deadline, max_usd, *, now=time.time, wait=None, stopped=None, report=None
):
    """Keep an explicit owner lease alive within time, spend and pod-runtime caps."""
    stopped = stopped or threading.Event()
    wait = wait or stopped.wait
    report = report or (lambda _event: None)
    start = now()
    if (
        not isinstance(deadline, (int, float))
        or not start < deadline <= start + 10800
        or not isinstance(max_usd, (int, float))
        or not 0 < max_usd <= 9
        or lc.cfg.get("auto_start") is not False
        or lc.cfg.get("max_runtime_seconds", 0) <= 600
        or lc.cfg["max_hourly_usd"] * (deadline - start) / 3600 > max_usd
    ):
        raise Refused("hold_contract")
    initial = lc.status()
    if (
        initial["phase"] != "OFFLINE"
        or initial["leases"]
        or initial["active_requests"]
        or initial["manual_stop"]
    ):
        raise Refused("hold_requires_idle_provider")
    spent, allocations = 0.0, 0
    while now() < deadline and not stopped.is_set():
        remaining = deadline - now()
        if lc.cfg["max_hourly_usd"] * remaining / 3600 > max_usd - spent:
            raise Refused("hold_budget_insufficient")
        scope = uuid.uuid4().hex
        lc.acquire(scope)
        pulse_stop = threading.Event()
        pulse_error = []

        def pulse(pulse_stop=pulse_stop, scope=scope, pulse_error=pulse_error):
            while not pulse_stop.wait(10):
                try:
                    lc.heartbeat(scope)
                except Exception:
                    pulse_error.append(True)
                    stopped.set()
                    return

        thread = threading.Thread(target=pulse, daemon=True)
        thread.start()
        allocation_cost = 0.0
        try:
            lc.ensure_ready(scope, explicit=True)
            ready = lc.status()
            if (
                ready["phase"] != "READY"
                or not ready["started_at"]
                or not ready["hourly_usd"]
            ):
                raise Refused("hold_readiness_unconfirmed")
            allocations += 1
            report({"event": "READY", "allocation": allocations})
            cycle_end = min(
                deadline, ready["started_at"] + lc.cfg["max_runtime_seconds"] - 300
            )
            if cycle_end <= now():
                raise Refused("hold_runtime_window_exhausted")
            while now() < cycle_end and not stopped.is_set():
                lc.check_lease(scope)
                if pulse_error:
                    raise Refused("hold_heartbeat_failed")
                current = lc.status()
                allocation_cost = current["estimated_compute_usd"]
                if (
                    spent + allocation_cost + lc.cfg["max_hourly_usd"] * 10 / 3600
                    >= max_usd
                ):
                    report({"event": "BUDGET_LIMIT"})
                    stopped.set()
                    break
                wait(min(10, cycle_end - now()))
            if pulse_error:
                raise Refused("hold_heartbeat_failed")
            allocation_cost = lc.status()["estimated_compute_usd"]
        finally:
            pulse_stop.set()
            thread.join(timeout=1)
            try:
                allocation_cost = max(
                    allocation_cost, lc.status()["estimated_compute_usd"]
                )
            except Exception:
                pass
            cleanup_failed = False
            for close in (False, True):
                try:
                    lc.release(scope, close=close)
                except Exception:
                    cleanup_failed = True
            spent += allocation_cost
            if cleanup_failed:
                report({"event": "CLEANUP_FAILED", "allocation": allocations})
                raise Refused("hold_cleanup_failed")
        released = lc.status()
        if released["leases"]:
            report({"event": "SHARED_WITH_WORK_MODE", "allocation": allocations})
            break
        if released["phase"] != "OFFLINE":
            raise Refused("hold_release_unconfirmed")
        report({"event": "RELEASED", "allocation": allocations})
    return {
        "phase": lc.status()["phase"],
        "allocations": allocations,
        "estimated_compute_usd": round(spent, 4),
    }


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser()
    p.add_argument(
        "command", choices=["prepare", "status", "stop", "resume", "sweep", "hold"]
    )
    p.add_argument("files", nargs="*")
    p.add_argument("--release", choices=RELEASES)
    p.add_argument("--until-epoch", type=float)
    p.add_argument("--max-compute-usd", type=float)
    args = p.parse_args()
    verify_release()
    settings = load_settings()
    if args.command == "prepare":
        return prepare(args.files, settings)
    if args.files:
        raise Refused("unexpected_arguments")
    if args.command == "hold":
        if (
            args.release != "PRIVATE_LEAD"
            or args.until_epoch is None
            or args.max_compute_usd is None
        ):
            raise Refused("hold_contract")
        work_intent_preflight()
        stop = threading.Event()
        signal.signal(signal.SIGINT, lambda _signal, _frame: stop.set())
        signal.signal(signal.SIGTERM, lambda _signal, _frame: stop.set())
        return hold_private_lead(
            PrivateLeadLifecycle(settings),
            args.until_epoch,
            args.max_compute_usd,
            stopped=stop,
            report=lambda event: print(canonical(event), flush=True),
        )
    if args.until_epoch is not None or args.max_compute_usd is not None:
        raise Refused("unexpected_arguments")
    if args.command == "sweep" and args.release is None:
        return sweep_all(settings)
    lc = lifecycle(settings, args.release or "PRIVATE_80B")
    if args.command == "stop":
        lc.sweep(immediate=True, manual=True)
    elif args.command == "resume":
        if args.release == "PRIVATE_LEAD":
            work_intent_preflight()
        lc.resume()
    elif args.command == "sweep":
        lc.sweep()
    return lc.status()


if __name__ == "__main__":
    try:
        print(canonical(main()))
    except Exception as e:
        raise SystemExit(
            "REFUSED: " + (str(e) if type(e) is Refused else "local_operation_failed")
        )
