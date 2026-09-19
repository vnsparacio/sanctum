"""Host-owned task inputs, immutable evidence snapshots and contained test views."""

import contextlib
import hashlib
import os
import stat
import tempfile
import unicodedata
from pathlib import Path

from common import Refused, atomic, canonical, private_dir, strict_json
from workspace import _real_directory

VERSION = "sanctum-task-protection/v1"
SNAPSHOT = "sanctum-task-evidence/v1"
LIMIT_FILES = 10000
LIMIT_BYTES = 128 * 1024 * 1024


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def path_name(value):
    if (
        type(value) is not str
        or not value
        or len(value) > 512
        or value.startswith("/")
        or "\\" in value
        or any(ord(c) < 32 for c in value)
    ):
        raise Refused("task_protection_contract")
    if value != unicodedata.normalize("NFC", value) or any(
        p in ("", ".", "..") or p.casefold() == ".git" for p in value.split("/")
    ):
        raise Refused("task_protection_contract")
    return value


def validate_contract(value):
    if (
        type(value) is not dict
        or set(value)
        != {
            "schema",
            "protected",
            "mutable",
            "mutable_tests",
            "allow_new",
            "acceptance",
        }
        or value["schema"] != VERSION
        or type(value["allow_new"]) is not bool
    ):
        raise Refused("task_protection_contract")
    for key in ("protected", "mutable_tests", "mutable"):
        if key == "mutable" and value[key] == "*":
            continue
        if type(value[key]) is not list or len(value[key]) > 256:
            raise Refused("task_protection_contract")
        names = [path_name(p) for p in value[key]]
        if len(set(p.casefold() for p in names)) != len(names):
            raise Refused("task_protection_contract")
    protected = set(value["protected"])
    mutable = set(value["mutable_tests"]) | (
        set() if value["mutable"] == "*" else set(value["mutable"])
    )
    if any(
        a.casefold() == b.casefold() or a.startswith(b + "/") or b.startswith(a + "/")
        for a in protected
        for b in mutable
    ):
        raise Refused("task_protection_contract")
    acceptance = value["acceptance"]
    if acceptance is not None:
        if (
            type(acceptance) is not dict
            or set(acceptance) != {"runner", "entries"}
            or acceptance["runner"] != "node-test-v1"
            or type(acceptance["entries"]) is not list
            or not 1 <= len(acceptance["entries"]) <= 32
        ):
            raise Refused("task_protection_contract")
        paths = []
        for entry in acceptance["entries"]:
            if (
                type(entry) is not dict
                or set(entry) != {"path", "names"}
                or path_name(entry["path"]) not in protected
                or type(entry["names"]) is not list
                or not 1 <= len(entry["names"]) <= 128
                or any(
                    type(n) is not str or not n or len(n) > 256 for n in entry["names"]
                )
            ):
                raise Refused("task_protection_contract")
            paths.append(entry["path"])
        if len(set(paths)) != len(paths):
            raise Refused("task_protection_contract")
    return strict_json(canonical(value))


def unrestricted_contract():
    return {
        "schema": VERSION,
        "protected": [],
        "mutable": "*",
        "mutable_tests": [],
        "allow_new": True,
        "acceptance": None,
    }


def inventory(root):
    """No-follow inventory; file data reads are checked against the opened inode."""
    root = _real_directory(root)
    out = {}
    total = 0

    def walk(directory, relative=""):
        nonlocal total
        entries = sorted(os.scandir(directory), key=lambda x: x.name)
        folded = set()
        for item in entries:
            if not relative and item.name == ".git":
                continue
            name = relative + item.name
            key = unicodedata.normalize("NFC", item.name).casefold()
            if key in folded or key == ".git":
                raise Refused("protected_input_modified")
            folded.add(key)
            info = item.stat(follow_symlinks=False)
            mode = stat.S_IMODE(info.st_mode)
            if len(out) >= LIMIT_FILES:
                raise Refused("task_evidence_limit")
            if stat.S_ISDIR(info.st_mode):
                out[name] = {"kind": "directory", "mode": mode}
                walk(Path(item.path), name + "/")
                continue
            if stat.S_ISLNK(info.st_mode):
                out[name] = {
                    "kind": "symlink",
                    "mode": mode,
                    "digest": hashlib.sha256(
                        os.readlink(item.path).encode()
                    ).hexdigest(),
                }
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise Refused("protected_input_modified")
            total += info.st_size
            if total > LIMIT_BYTES:
                raise Refused("task_evidence_limit")
            fd = os.open(item.path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                opened = os.fstat(fd)
                if (opened.st_dev, opened.st_ino, opened.st_nlink) != (
                    info.st_dev,
                    info.st_ino,
                    1,
                ):
                    raise Refused("protected_input_modified")
                h = hashlib.sha256()
                with os.fdopen(fd, "rb", closefd=False) as stream:
                    for block in iter(lambda: stream.read(65536), b""):
                        h.update(block)
                after = os.fstat(fd)
                if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
                    opened.st_size,
                    opened.st_mtime_ns,
                    opened.st_ctime_ns,
                ):
                    raise Refused("protected_input_modified")
            finally:
                os.close(fd)
            out[name] = {
                "kind": "file",
                "mode": mode,
                "digest": h.hexdigest(),
                "size": info.st_size,
                "device": info.st_dev,
                "inode": info.st_ino,
            }

    walk(root)
    return out


def content_identity(rows):
    return {
        p: {k: v for k, v in row.items() if k not in ("device", "inode")}
        for p, row in rows.items()
    }


def store_root(settings):
    return private_dir(
        Path(settings["state_directory"]) / "private-lead/work-mode/evidence"
    )


def snapshot(settings, record, contract):
    contract = validate_contract(contract)
    root = Path(record["root"])
    rows = inventory(root)
    directory = store_root(settings) / record["workspace_id"]
    directory.mkdir(mode=0o700)
    protected = {p: rows.get(p, {"kind": "absent"}) for p in contract["protected"]}
    for path, row in protected.items():
        if row["kind"] not in ("file", "absent"):
            raise Refused("task_protection_contract")
        if row["kind"] == "file":
            fd = os.open(root / path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino, opened.st_nlink) != (
                    row["device"],
                    row["inode"],
                    1,
                ):
                    raise Refused("protected_input_modified")
                raw = stream.read(LIMIT_BYTES + 1)
            if hashlib.sha256(raw).hexdigest() != row["digest"]:
                raise Refused("protected_input_modified")
            target = directory / (row["digest"] + ".blob")
            if not target.exists():
                target.write_bytes(raw)
                target.chmod(0o400)
    if contract["acceptance"] and any(
        protected[x["path"]]["kind"] != "file"
        for x in contract["acceptance"]["entries"]
    ):
        raise Refused("task_protection_contract")
    value = {
        "schema": SNAPSHOT,
        "task_id": record["workspace_id"],
        "workspace": str(root),
        "contract": contract,
        "original": rows,
        "protected": protected,
    }
    atomic(directory / "manifest.json", (canonical(value) + "\n").encode())
    (directory / "manifest.json").chmod(0o400)
    record["protection_digest"] = digest(value)
    return record


def load(settings, record):
    directory = store_root(settings) / record["workspace_id"]
    path = directory / "manifest.json"
    if directory.is_symlink() or path.is_symlink():
        raise Refused("task_evidence_unavailable")
    value = strict_json(path.read_text())
    if (
        value.get("schema") != SNAPSHOT
        or value.get("task_id") != record["workspace_id"]
        or value.get("workspace") != record["root"]
        or digest(value) != record.get("protection_digest")
    ):
        raise Refused("task_evidence_unavailable")
    validate_contract(value["contract"])
    return value, directory


def check(settings, record):
    value, directory = load(settings, record)
    contract = value["contract"]
    facts = {
        "schema": SNAPSHOT,
        "taskId": record["workspace_id"],
        "contractDigest": digest(contract),
        "snapshotDigest": record["protection_digest"],
        "integrity": "PASS",
        "candidateDigest": None,
        "acceptanceRequired": contract["acceptance"] is not None,
        "protectedCount": len(value["protected"]),
    }
    try:
        rows = inventory(record["root"])
        facts["candidateDigest"] = digest(content_identity(rows))
        for path, original in value["protected"].items():
            # Exact spelling, inode, kind, mode and bytes; Git staging is irrelevant.
            if rows.get(path, {"kind": "absent"}) != original:
                raise Refused("protected_input_modified")
            if original["kind"] == "file":
                blob = directory / (original["digest"] + ".blob")
                if (
                    blob.is_symlink()
                    or not blob.is_file()
                    or blob.stat().st_nlink != 1
                    or hashlib.sha256(blob.read_bytes()).hexdigest()
                    != original["digest"]
                ):
                    raise Refused("task_evidence_unavailable")
        mutable = contract["mutable"]
        allowed = set(contract["mutable_tests"]) | (
            set() if mutable == "*" else set(mutable)
        )
        for path in set(rows) | set(value["original"]):
            current = rows.get(path)
            original = value["original"].get(path)
            if current == original:
                continue
            if current and current["kind"] == "symlink":
                raise Refused("protected_input_modified")
            if path not in value["original"]:
                if not contract["allow_new"]:
                    raise Refused("protected_input_modified")
            elif (
                mutable != "*"
                and path not in allowed
                and original["kind"] != "directory"
            ):
                raise Refused("protected_input_modified")
            if any(
                unicodedata.normalize("NFC", path).casefold() == p.casefold()
                and path != p
                for p in value["protected"]
            ):
                raise Refused("protected_input_modified")
    except Refused as error:
        if str(error) != "protected_input_modified":
            raise
        facts["integrity"] = "FAIL"
        atomic(directory / "violated", b"PROTECTED_INPUT_MODIFIED\n")
    if (directory / "violated").exists():
        facts["integrity"] = "FAIL"
    return facts


@contextlib.contextmanager
def acceptance_view(settings, record):
    facts = check(settings, record)
    if facts["integrity"] != "PASS":
        raise Refused("protected_input_modified")
    value, directory = load(settings, record)
    acceptance = value["contract"]["acceptance"]
    if acceptance is None:
        raise Refused("protected_execution_unconfigured")
    with tempfile.TemporaryDirectory(
        prefix="acceptance-", dir=store_root(settings)
    ) as temporary:
        target = Path(temporary) / "candidate"
        target.mkdir(mode=0o700)
        source = Path(record["root"])
        rows = inventory(source)
        for path, row in rows.items():
            dest = target / path
            if row["kind"] == "directory":
                dest.mkdir(mode=0o755, exist_ok=True)
            elif row["kind"] == "symlink":
                dest.symlink_to(os.readlink(source / path))
            else:
                # No symlink dereference; candidate writes cannot reach originals.
                fd = os.open(source / path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, "rb") as stream:
                    raw = stream.read(LIMIT_BYTES + 1)
                if hashlib.sha256(raw).hexdigest() != row["digest"]:
                    raise Refused("protected_input_modified")
                dest.write_bytes(raw)
                dest.chmod(row["mode"])
        for path, row in value["protected"].items():
            if row["kind"] == "file":
                dest = target / path
                dest.write_bytes((directory / (row["digest"] + ".blob")).read_bytes())
                dest.chmod(row["mode"])
        if check(settings, record) != facts:
            raise Refused("protected_input_modified")
        yield target, acceptance, facts


def patch_assessment(settings, record, patch):
    """Classify syntax separately from protected/mutation-boundary violations."""
    import subprocess

    from workspace import GIT, GIT_ENV

    value, _ = load(settings, record)
    contract = value["contract"]
    if check(settings, record)["integrity"] != "PASS":
        raise Refused("protected_input_modified")
    outputs = []
    for direction in ([], ["--reverse"]):
        r = subprocess.run(
            GIT + ["apply", "--numstat", "-z", "--recount", *direction, "-"],
            cwd=record["root"],
            env=GIT_ENV,
            input=patch.encode(),
            capture_output=True,
            timeout=30,
        )
        if r.returncode:
            return "WORKSPACE_PATCH_INVALID"
        outputs.append(r.stdout)
    records = b"".join(outputs).split(b"\0")
    names = []
    i = 0
    try:
        while i < len(records) - 1:
            head = records[i].split(b"\t", 2)
            i += 1
            if len(head) != 3:
                raise ValueError()
            if head[2]:
                names.append(head[2].decode())
            else:
                names.extend([records[i].decode(), records[i + 1].decode()])
                i += 2
        if not names:
            raise ValueError()
        for name in names:
            path_name(name)
            fold = unicodedata.normalize("NFC", name).casefold()
            if any(
                fold == p.casefold()
                or fold.startswith(p.casefold() + "/")
                or p.casefold().startswith(fold + "/")
                for p in contract["protected"]
            ):
                return "WORKSPACE_PROTECTED_INPUT"
            if name not in value["original"]:
                if not contract["allow_new"]:
                    return "WORKSPACE_PROTECTED_INPUT"
            elif (
                contract["mutable"] != "*"
                and name not in contract["mutable"] + contract["mutable_tests"]
            ):
                return "WORKSPACE_PROTECTED_INPUT"
    except (ValueError, UnicodeDecodeError, IndexError, Refused):
        return "WORKSPACE_PATCH_INVALID"
    return "PASS"


def patch_allowed(settings, record, patch):
    return patch_assessment(settings, record, patch) == "PASS"


def execute_original(settings, record):
    from command_runner import run

    with acceptance_view(settings, record) as (view, acceptance, before):
        result = run(settings, record["profile"], view, "test", acceptance=acceptance)
        after = check(settings, record)
        if after != before:
            raise Refused("protected_input_modified")
        proof = result.get("protected_execution", {})
        return {
            "schema": SNAPSHOT,
            "taskId": record["workspace_id"],
            "snapshotDigest": record["protection_digest"],
            "candidateDigest": before["candidateDigest"],
            "integrity": after["integrity"],
            "executed": proof.get("executed") is True,
            "passed": result["ok"] is True,
            "code": result["code"],
            "executionState": result["executionState"],
            "outputDigest": result["output_digest"],
            "elapsedMs": result["elapsed_ms"],
            "containerAbsent": result["container_absent"],
        }
