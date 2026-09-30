"""Mac-owned snapshot handoff for an isolated Qwen Code worker.

The coding container receives only qwen-input and writes only qwen-output.
Neither directory is a host workspace mount. This module never executes Qwen.
"""

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

import task_evidence
import worktree_edit
from common import Refused, atomic, canonical, strict_json

SCHEMA = "sanctum-qwen-snapshot/v1"
MAX_CHANGED = worktree_edit.MAX_PATCH_FILES


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _file(root, path, row):
    with worktree_edit.opened(root, path) as (_, __, ___, ____, raw):
        if len(raw) != row["size"] or _sha(raw) != row["digest"]:
            raise Refused("qwen_snapshot_race")
        return raw


def export(settings, record):
    """Freeze a clean task worktree into a private, one-use container input."""
    with worktree_edit.locked(settings, record):
        value, directory = task_evidence.load(settings, record)
        facts = task_evidence.check(settings, record)
        baseline = task_evidence.content_identity(value["original"])
        baseline_digest = task_evidence.digest(baseline)
        if facts["integrity"] != "PASS" or facts["candidateDigest"] != baseline_digest:
            raise Refused("qwen_snapshot_baseline_changed")
        if any(row["kind"] not in ("file", "directory") for row in baseline.values()):
            raise Refused("qwen_snapshot_type")
        if (directory / "qwen-export.json").exists() or (
            directory / "qwen-input"
        ).exists():
            raise Refused("qwen_snapshot_exists")
        temporary = Path(tempfile.mkdtemp(prefix="qwen-input-", dir=directory))
        try:
            for path, row in sorted(
                baseline.items(), key=lambda item: (item[0].count("/"), item[0])
            ):
                target = temporary / path
                if row["kind"] == "directory":
                    target.mkdir(mode=0o700)
                    continue
                raw = _file(record["root"], path, row)
                fd = os.open(
                    target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            if (
                task_evidence.check(settings, record)["candidateDigest"]
                != baseline_digest
            ):
                raise Refused("qwen_snapshot_race")
            os.rename(temporary, directory / "qwen-input")
            atomic(
                directory / "qwen-export.json",
                (
                    canonical(
                        {
                            "schema": SCHEMA,
                            "taskId": record["workspace_id"],
                            "snapshotDigest": record["protection_digest"],
                            "baselineDigest": baseline_digest,
                        }
                    )
                    + "\n"
                ).encode(),
            )
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return {
            "schema": SCHEMA,
            "taskId": record["workspace_id"],
            "snapshotDigest": record["protection_digest"],
            "baselineDigest": baseline_digest,
            "input": str(directory / "qwen-input"),
            "output": str(directory / "qwen-output"),
        }


def import_output(settings, record):
    """Admit one exact final snapshot through the existing Mac patch authority."""
    try:
        value, directory = task_evidence.load(settings, record)
    except FileNotFoundError:
        raise Refused("qwen_snapshot_identity") from None
    marker = directory / "qwen-export.json"
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_mode & 0o077:
        raise Refused("qwen_snapshot_unavailable")
    exported = strict_json(marker.read_text())
    baseline = task_evidence.content_identity(value["original"])
    baseline_digest = task_evidence.digest(baseline)
    if exported != {
        "schema": SCHEMA,
        "taskId": record["workspace_id"],
        "snapshotDigest": record["protection_digest"],
        "baselineDigest": baseline_digest,
    }:
        raise Refused("qwen_snapshot_identity")
    if (directory / "qwen-import-attempt.json").exists():
        raise Refused("qwen_snapshot_import_replayed")
    facts = task_evidence.check(settings, record)
    if facts["integrity"] != "PASS" or facts["candidateDigest"] != baseline_digest:
        raise Refused("qwen_snapshot_baseline_changed")
    output = directory / "qwen-output"
    if (
        output.is_symlink()
        or not output.is_dir()
        or (output / ".git").exists()
        or (output / ".git").is_symlink()
    ):
        raise Refused("qwen_snapshot_output_invalid")
    rows = task_evidence.inventory(output)
    output_digest = task_evidence.digest(task_evidence.content_identity(rows))
    directories = {p for p, row in baseline.items() if row["kind"] == "directory"}
    if {p for p, row in rows.items() if row["kind"] == "directory"} != directories:
        raise Refused("qwen_snapshot_structure")
    if any(
        row["kind"] != "file" for row in rows.values() if row["kind"] != "directory"
    ):
        raise Refused("qwen_snapshot_type")
    if any(p not in rows for p, row in baseline.items() if row["kind"] == "file"):
        raise Refused("qwen_snapshot_deletion")
    expected = dict(baseline)
    changes = []
    patches = []
    for path, row in sorted(rows.items()):
        if row["kind"] != "file":
            continue
        previous = baseline.get(path)
        if previous is not None and previous["kind"] != "file":
            raise Refused("qwen_snapshot_type")
        if previous is not None and row["digest"] == previous["digest"]:
            continue
        if len(changes) >= MAX_CHANGED:
            raise Refused("qwen_snapshot_patch_limit")
        if worktree_edit._restricted_patch_path(
            path
        ) or worktree_edit.protected_or_disallowed(
            value["contract"], value["original"], path
        ):
            raise Refused("qwen_snapshot_path_denied")
        if row["size"] > worktree_edit.MAX_FILE:
            raise Refused("qwen_snapshot_patch_limit")
        before = _file(record["root"], path, previous) if previous else None
        after = _file(output, path, row)
        if b"\0" in after:
            raise Refused("qwen_snapshot_type")
        try:
            after.decode("utf-8")
        except UnicodeDecodeError:
            raise Refused("qwen_snapshot_type") from None
        patches.append(worktree_edit.canonical_diff(path, before, after))
        expected[path] = {
            "kind": "file",
            "mode": previous["mode"] if previous else 0o600,
            "digest": row["digest"],
            "size": row["size"],
        }
        changes.append(path)
    if not changes:
        raise Refused("qwen_snapshot_no_edit")
    patch = b"".join(patches)
    if len(patch) > worktree_edit.MAX_PATCH:
        raise Refused("qwen_snapshot_patch_limit")
    if (
        task_evidence.digest(
            task_evidence.content_identity(task_evidence.inventory(output))
        )
        != output_digest
    ):
        raise Refused("qwen_snapshot_race")
    attempt = {
        "schema": SCHEMA,
        "taskId": record["workspace_id"],
        "baselineDigest": baseline_digest,
        "patchDigest": _sha(patch),
        "outputDigest": output_digest,
        "paths": changes,
    }
    atomic(directory / "qwen-import-attempt.json", (canonical(attempt) + "\n").encode())
    result = worktree_edit.apply_patch(
        settings,
        record,
        patch.decode("utf-8"),
        expected_candidate_digest=baseline_digest,
    )
    if not result["ok"]:
        return result
    after = task_evidence.check(settings, record)
    if after["integrity"] != "PASS" or after["candidateDigest"] != task_evidence.digest(
        expected
    ):
        return {
            "ok": False,
            "code": "QWEN_IMPORT_UNCERTAIN",
            "executionState": "COMPLETION_UNKNOWN",
        }
    receipt = {
        **attempt,
        "candidateDigest": after["candidateDigest"],
        "workspaceGeneration": result["receipt"]["workspace_generation"],
        "authorityResult": result["receipt"]["authority_result"],
    }
    atomic(directory / "qwen-import.json", (canonical(receipt) + "\n").encode())
    return {"ok": True, "code": "OK", "executionState": "COMPLETED", "receipt": receipt}
