"""Single authenticated operation. Only local control-plane code can sign it."""

import os
import signal
import sys
from pathlib import Path

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "src"))
import task_evidence
import worktree_edit
from authority import authorize
from backends import LocalMultimodalBackend, Remote
from command_runner import run as run_command
from common import (
    Refused,
    atomic,
    canonical,
    load_settings,
    private_dir,
    strict_json,
    verify_release,
)
from dispatch import assess
from experiment import installed_identity
from experiment_lifecycle import DiagnosticLifecycle
from lifecycle import Private80BLifecycle, PrivateLeadLifecycle
from media import expand, load
from protocol_stream import safe_diagnostic
from source_policy import minimize_query
from workspace import (
    cleanup_worktree,
    create_worktree,
    inspect_worktree,
    list_entries,
)


def work_root(settings):
    return private_dir(
        Path(settings["state_directory"]) / "private-lead" / "work-mode" / "workspaces"
    )


def work_record(settings, task_id):
    path = work_root(settings) / (task_id + ".json")
    if path.is_symlink() or not path.exists():
        raise Refused("worktree_unavailable")
    value = strict_json(path.read_text())
    if value.get("workspace_id") != task_id:
        raise Refused("worktree_identity")
    return value


def work_profile(settings, name):
    path = Path(settings["work_mode"]["profile_file"])
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise Refused("work_profile_permissions")
    value = strict_json(path.read_text())
    profile = value.get("profiles", {}).get(name)
    if type(profile) is not dict:
        raise Refused("work_profile_unknown")
    return profile


def execute(b, settings, remote=None, lifecycle=None):
    # Reads/editor manage this same lock internally; serialize all other host
    # workspace routes, including internal patch and cleanup, against mutation.
    if b["operation"] in {
        "worktree_list",
        "worktree_command",
        "worktree_integrity",
        "worktree_acceptance",
        "worktree_cleanup",
    }:
        with worktree_edit.locked(settings, work_record(settings, b["scope"])):
            return _execute(b, settings, remote, lifecycle)
    return _execute(b, settings, remote, lifecycle)


def _execute(b, settings, remote=None, lifecycle=None):
    op = b["operation"]
    scope = b["scope"]
    if b.get("tier") == "PRIVATE_80B" and op not in (
        "status",
        "close",
        "stop",
        "sweep",
    ):
        raise Refused("private_80b_retired")
    if op == "worktree_create":
        p = b["packet"]
        profile = work_profile(settings, p["profile"])
        root = work_root(settings)
        record_path = root / (scope + ".json")
        if record_path.exists() or record_path.is_symlink():
            raise Refused("worktree_exists")
        workspace = create_worktree(
            profile["repository"], profile["staging_root"], scope, profile["disk_bytes"]
        )
        workspace["profile"] = p["profile"]
        atomic(record_path, canonical(workspace).encode())
        try:
            task_evidence.snapshot(settings, workspace, profile.get("task_protection"))
            atomic(record_path, canonical(workspace).encode())
        except Exception:
            cleanup_worktree(profile["repository"], workspace)
            record_path.unlink()
            raise
        return {
            "status": "OK",
            "workspace": {
                "workspace_id": scope,
                "base_commit": workspace["base_commit"],
                "initial_status": workspace["initial_status"],
                "disk_bytes": workspace["disk_bytes"],
            },
        }
    if op == "worktree_list":
        p = b["packet"]
        return {
            "status": "OK",
            "result": list_entries(
                work_record(settings, scope)["root"], p["path"], p["max_entries"]
            ),
        }
    if op == "worktree_read":
        p = b["packet"]
        return {
            "status": "OK",
            "result": worktree_edit.read(
                settings, work_record(settings, scope), p["path"], p["max_chars"]
            ),
        }
    if op == "worktree_observe":
        p = b["packet"]
        return {
            "status": "OK",
            "result": worktree_edit.observe(
                settings, work_record(settings, scope), p["path"], p["observation"]
            ),
        }
    if op == "worktree_edit":
        p = b["packet"]
        return {
            "status": "OK",
            "result": worktree_edit.apply(
                settings,
                work_record(settings, scope),
                {k: v for k, v in p.items() if k != "task_id"},
            ),
        }
    if op == "worktree_patch":
        p = b["packet"]
        record = work_record(settings, scope)
        return {
            "status": "OK",
            "result": worktree_edit.apply_patch(settings, record, p["patch"]),
        }
    if op == "worktree_command":
        p = b["packet"]
        record = work_record(settings, scope)
        if record["profile"] != p["profile"]:
            raise Refused("worktree_profile_mismatch")
        if p["operation"] in {"status", "diff"}:
            return {
                "status": "OK",
                "result": inspect_worktree(record["root"], p["operation"]),
            }
        return {
            "status": "OK",
            "result": run_command(
                settings, p["profile"], record["root"], p["operation"]
            ),
        }
    if op in ("worktree_integrity", "worktree_acceptance"):
        p = b["packet"]
        record = work_record(settings, scope)
        if record["profile"] != p["profile"]:
            raise Refused("worktree_profile_mismatch")
        return {
            "status": "OK",
            "result": (
                task_evidence.check(settings, record)
                if op == "worktree_integrity"
                else task_evidence.execute_original(settings, record)
            ),
        }
    if op == "worktree_cleanup":
        p = b["packet"]
        record = work_record(settings, scope)
        profile = work_profile(settings, p["profile"])
        if record["profile"] != p["profile"]:
            raise Refused("worktree_profile_mismatch")
        result = cleanup_worktree(profile["repository"], record)
        (work_root(settings) / (scope + ".json")).unlink()
        return {"status": "OK", "result": result}
    if op == "work_source_policy":
        p = b["packet"]
        draft = minimize_query(p["prompt"])
        return {
            "status": "OK",
            "result": {
                "query": draft.query,
                "sensitivity": draft.sensitivity,
                "queryMode": draft.mode,
                "reasonCodes": list(draft.reason_codes),
                "digest": draft.digest,
                "sourceNeed": p["source_need"],
            },
        }
    if op == "media":
        p = load(b["packet"]["token"], None, scope, settings, bind=True)
        return {"status": "OK", "digest": p["digest"], "summary": p["summary"]}
    if op == "classify":
        packet = dict(b["packet"])
        packet["disclosed"] = expand(packet.get("disclosed", {}), scope, settings)
        # No token, file path or private snapshot identifiers are sent to Gemini.
        audit = (remote or Remote(settings)).classify(
            packet, b["nonce"], (BASE / "PROMPT.txt").read_text()
        )
        return assess(b["packet"], b["state"], audit, b["strong"])
    if op == "infer":
        if b["tier"] == "PRIVATE_80B":
            raise Refused("private_80b_retired")
        packet = expand(b["packet"], scope, settings)
        if (
            len(canonical({k: v for k, v in packet.items() if k != "images"}).encode())
            > settings["max_context_bytes"]
        ):
            raise Refused("answer_context_limit")
        if b["tier"] == "PRIVATE_LEAD":
            return (lifecycle or PrivateLeadLifecycle(settings)).infer(scope, packet)
        if b["tier"] == "MULTIMODAL" and settings["multimodal"]["transport"] == "local":
            return LocalMultimodalBackend(settings).infer(packet)
        return (remote or Remote(settings)).infer(b["tier"], packet, b["nonce"])
    if op == "private_lead_propose" and "experiment" in b["packet"]:
        binding = b["packet"]["experiment"]
        lc = lifecycle or PrivateLeadLifecycle(settings)
        diagnostic = DiagnosticLifecycle(lc, binding, installed_identity())
        remaining = diagnostic.dispatch.timeout(3000)

        def expire(*_):
            diagnostic.ledger.stop(binding, "DEADLINE")
            raise Refused("experiment_deadline")

        previous = signal.signal(signal.SIGALRM, expire)
        signal.setitimer(signal.ITIMER_REAL, remaining)
        try:
            return diagnostic.propose(scope, b["packet"]["request"])
        except BaseException as error:
            if type(error) is Refused and str(error) == "operation_cancelled":
                diagnostic.ledger.stop(binding, "CANCELLED")
            raise
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    if op == "private_lead_propose":
        return (lifecycle or PrivateLeadLifecycle(settings)).propose(
            scope, b["packet"]["request"]
        )
    lc = lifecycle or (
        PrivateLeadLifecycle(settings)
        if b["tier"] == "PRIVATE_LEAD"
        else Private80BLifecycle(settings)
    )
    if op == "close":
        lc.release(scope, close=True)
    elif op == "sweep":
        lc.sweep()
    elif op == "stop":
        lc.sweep(immediate=True, manual=True)
    elif op == "resume":
        lc.resume()
    return {"status": "OK", "gpu": lc.status()}


def main():
    os.umask(0o077)
    verify_release()
    settings = load_settings()
    raw = sys.stdin.buffer.read(220001)
    if len(raw) > 220000:
        raise Refused("input_limit")
    body = authorize(strict_json(raw), settings)

    # SIGTERM interrupts bootstrap/query and unwinds the lease finally block.
    def stop(*_):
        raise Refused("operation_cancelled")

    signal.signal(signal.SIGTERM, stop)
    return execute(body, settings)


if __name__ == "__main__":
    try:
        print(canonical(main()))
    except Exception as e:
        # Refused messages are enumerated local codes. Never echo arbitrary errors.
        safe = (
            str(e)
            if type(e) is Refused and str(e).replace("_", "").isalnum()
            else "operation_unavailable"
        )
        result = {"status": "UNAVAILABLE", "reason": safe}
        if type(e) is Refused and hasattr(e, "diagnostic"):
            result["diagnostic"] = safe_diagnostic(e.diagnostic)
        print(canonical(result))
        sys.exit(1)
