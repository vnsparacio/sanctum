"""Owner-operated local maintenance. Never sends prompts to hosted models."""

import argparse
import json
import os
import shutil
import subprocess
import sys
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


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["prepare", "status", "stop", "resume", "sweep"])
    p.add_argument("files", nargs="*")
    p.add_argument("--release", choices=RELEASES)
    args = p.parse_args()
    verify_release()
    settings = load_settings()
    if args.command == "prepare":
        return prepare(args.files, settings)
    if args.files:
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
