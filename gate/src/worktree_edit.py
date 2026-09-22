"""Exact UTF-8 replacements. Observation and mutation authority are Mac-owned."""

import contextlib
import ctypes
import errno
import fcntl
import hashlib
import os
import re
import secrets
import stat
import subprocess
import tempfile
from pathlib import Path

import task_evidence
from common import Refused, atomic, canonical, strict_json
from workspace import GIT, GIT_ENV

MAX_FILE = 1024 * 1024
MAX_PATCH = 48_000
MAX_PATCH_FILES = 16
MAX_PATCH_HUNKS = 64
MAX_PATCH_RESULT = 4 * 1024 * 1024
VENDOR_PARTS = frozenset(
    {"vendor", "vendors", "node_modules", "third_party", "third-party"}
)
GENERATED_PARTS = frozenset(
    {"generated", "__generated__", "dist", "build", "coverage", ".next", "target"}
)
GENERATED_SUFFIXES = (".min.js", ".min.css", ".map")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?\n?$")
RECOVER = {
    "EDIT_SOURCE_NOT_OBSERVED",
    "EDIT_SOURCE_STALE",
    "EDIT_TARGET_NOT_FOUND",
    "EDIT_TARGET_NOT_UNIQUE",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fail(code):
    return {"ok": False, "code": code, "executionState": "NOT_STARTED"}


def validate(arguments):
    if type(arguments) is not dict:
        return "EDIT_SCHEMA_INVALID"
    operation = arguments.get("operation")
    shapes = {
        None: {"path", "old_text", "new_text"},
        "create": {"operation", "path", "new_text"},
        "delete": {"operation", "path"},
        "move": {"operation", "path", "destination"},
    }
    if (
        operation not in shapes
        or set(arguments) != shapes[operation]
        or any(type(v) is not str for v in arguments.values())
    ):
        return "EDIT_SCHEMA_INVALID"
    if operation is None and not arguments["old_text"]:
        return "EDIT_SCHEMA_INVALID"
    try:
        old = arguments.get("old_text", "").encode("utf-8")
        new = arguments.get("new_text", "").encode("utf-8")
    except UnicodeEncodeError:
        return "EDIT_ENCODING_UNSUPPORTED"
    if len(old) > 4096 or len(new) > 8192:
        return "EDIT_REPLACEMENT_TOO_LARGE"
    if b"\0" in old + new:
        return "EDIT_ENCODING_UNSUPPORTED"
    try:
        task_evidence.path_name(arguments["path"])
        if operation == "move":
            task_evidence.path_name(arguments["destination"])
    except Refused:
        return "EDIT_PATH_INVALID"
    if (
        operation == "move"
        and arguments["path"].casefold() == arguments["destination"].casefold()
    ):
        return "EDIT_NO_CHANGE"
    return None


@contextlib.contextmanager
def locked(settings, record):
    _, directory = task_evidence.load(settings, record)
    fd = os.open(
        directory / "editor.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        file = directory / "editor.json"
        state = (
            strict_json(file.read_text())
            if file.exists()
            else {"generation": 0, "observations": {}, "pending": {}, "required": []}
        )
        yield state, directory
        atomic(file, (canonical(state) + "\n").encode())
    finally:
        os.close(fd)


@contextlib.contextmanager
def opened(root, path):
    """Anchor every component with O_NOFOLLOW directory descriptors."""
    try:
        task_evidence.path_name(path)
    except Refused:
        raise Refused("EDIT_PATH_INVALID") from None
    fds = []
    try:
        current = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fds.append(current)
        for part in path.split("/")[:-1]:
            current = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current
            )
            fds.append(current)
        name = path.split("/")[-1]
        fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=current)
        fds.append(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Refused("EDIT_FILE_TYPE_UNSUPPORTED")
        if info.st_size > MAX_FILE:
            raise Refused("EDIT_REPLACEMENT_TOO_LARGE")
        chunks = []
        remaining = MAX_FILE + 1
        while remaining:
            block = os.read(fd, min(65536, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        if identity(after) != identity(info):
            raise Refused("EDIT_APPLY_RACE")
        if len(raw) > MAX_FILE:
            raise Refused("EDIT_REPLACEMENT_TOO_LARGE")
        if b"\0" in raw:
            raise Refused("EDIT_FILE_TYPE_UNSUPPORTED")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise Refused("EDIT_ENCODING_UNSUPPORTED") from None
        yield current, name, fd, info, raw
    except OSError:
        raise Refused("EDIT_PATH_INVALID") from None
    finally:
        for fd in reversed(fds):
            os.close(fd)


def identity(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def read(settings, record, path, max_chars):
    if type(max_chars) is not int or not 1 <= max_chars <= 24000:
        raise Refused("workspace_read_limit")
    with (
        locked(settings, record) as (state, _),
        opened(record["root"], path) as (_, __, fd, info, raw),
    ):
        text = raw.decode("utf-8")
        visible = text[:max_chars]
        observation = {
            "task_id": record["workspace_id"],
            "workspace_id": record["workspace_id"],
            "path": path,
            "generation": state["generation"],
            "digest": sha(raw),
            "file_type": "UTF8_REGULAR",
            "byte_length": len(raw),
            "ranges": [[0, len(visible.encode())]],
            "text": visible,
        }
        token = sha(canonical(observation).encode())
        state["pending"][path] = {"token": token, "observation": observation}
        # At most one pending read per path and a bounded task-wide inventory.
        if len(state["pending"]) > 128:
            state["pending"].pop(next(iter(state["pending"])))
        return {
            "path": path,
            "text": visible,
            "truncated": len(text) > max_chars,
            "size": len(raw),
            "_observation": token,
        }


def observe(settings, record, path, token):
    """Called only by the host after result egress and context-size checks."""
    with locked(settings, record) as (state, _):
        pending = state["pending"].pop(path, None)
        if not pending or pending["token"] != token:
            raise Refused("workspace_observation_invalid")
        state["observations"][path] = pending["observation"]
        if len(state["observations"]) > 128:
            state["observations"].pop(next(iter(state["observations"])))
        if path in state["required"]:
            state["required"].remove(path)
    return {"ok": True}


def canonical_diff(path, before, after):
    # Git renders the exact two byte strings without repository attributes,
    # textconv, external drivers, newline conversion, or user configuration.
    with tempfile.TemporaryDirectory(prefix="sanctum-edit-diff-") as tmp:
        base = Path(tmp)
        for prefix, raw in (("a", before), ("b", after)):
            if raw is None:
                continue
            p = base / prefix / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        left = "/dev/null" if before is None else f"a/{path}"
        right = "/dev/null" if after is None else f"b/{path}"
        result = subprocess.run(
            GIT
            + [
                "diff",
                "--no-index",
                "--no-ext-diff",
                "--no-textconv",
                "--binary",
                "--no-prefix",
                "--",
                left,
                right,
            ],
            cwd=base,
            env=GIT_ENV,
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 1 or not result.stdout or len(result.stdout) > 48000:
            raise Refused("EDIT_REPLACEMENT_TOO_LARGE")
        return result.stdout


def mutation_authority(settings, record, diff):
    # Reuse the existing actual-mutation authority/protection assessment.
    assessment = task_evidence.patch_assessment(settings, record, diff.decode("utf-8"))
    return {
        "outcome": "ALLOW" if assessment == "PASS" else "DENY",
        "canonical_diff_digest": sha(diff),
        "reason": assessment,
    }


def _patch_path(header, prefix):
    if not header.startswith(prefix):
        raise Refused("EDIT_PATCH_INVALID")
    value = header[len(prefix) :].rstrip("\n")
    if "\t" in value:
        value = value.split("\t", 1)[0]
    if value == "/dev/null":
        return None
    if value.startswith(("a/", "b/")):
        value = value[2:]
    try:
        return task_evidence.path_name(value)
    except Refused:
        raise Refused("EDIT_PATH_INVALID") from None


def _patch_line(lines, index, marker):
    if not lines[index].startswith(marker):
        raise Refused("EDIT_PATCH_INVALID")
    value = lines[index][1:].encode("utf-8")
    index += 1
    if index < len(lines) and lines[index] == "\\ No newline at end of file\n":
        if not value.endswith(b"\n"):
            raise Refused("EDIT_PATCH_INVALID")
        value = value[:-1]
        index += 1
    return value, index


def parse_patch(patch):
    """Parse a strict, bounded text unified diff without applying it."""
    try:
        raw = patch.encode("utf-8")
    except UnicodeEncodeError:
        raise Refused("EDIT_ENCODING_UNSUPPORTED") from None
    if not raw or len(raw) > MAX_PATCH or b"\0" in raw:
        raise Refused("EDIT_PATCH_TOO_LARGE")
    lines = patch.splitlines(keepends=True)
    files = []
    index = 0
    hunks = 0
    while index < len(lines):
        if lines[index].startswith("diff --git "):
            index += 1
        if index < len(lines) and lines[index] == "new file mode 100644\n":
            index += 1
        if index < len(lines) and re.fullmatch(
            r"index [0-9a-f]{7,64}\.\.[0-9a-f]{7,64}(?: 100644)?\n",
            lines[index],
        ):
            index += 1
        if index + 1 >= len(lines) or not lines[index].startswith("--- "):
            raise Refused("EDIT_PATCH_INVALID")
        old_path = _patch_path(lines[index], "--- ")
        new_path = _patch_path(lines[index + 1], "+++ ")
        index += 2
        if new_path is None or (old_path is not None and old_path != new_path):
            raise Refused("EDIT_PATCH_UNSUPPORTED")
        entry = {"path": new_path, "new": old_path is None, "hunks": []}
        while index < len(lines) and lines[index].startswith("@@ "):
            match = HUNK.fullmatch(lines[index])
            if not match:
                raise Refused("EDIT_PATCH_INVALID")
            old_start, old_count, new_start, new_count = (
                int(match.group(1)),
                int(match.group(2) or 1),
                int(match.group(3)),
                int(match.group(4) or 1),
            )
            index += 1
            old_lines, new_lines = [], []
            while index < len(lines) and not lines[index].startswith(
                ("@@ ", "--- ", "diff --git ")
            ):
                marker = lines[index][:1]
                if marker not in (" ", "-", "+"):
                    raise Refused("EDIT_PATCH_INVALID")
                value, index = _patch_line(lines, index, marker)
                if marker in (" ", "-"):
                    old_lines.append(value)
                if marker in (" ", "+"):
                    new_lines.append(value)
            if len(old_lines) != old_count or len(new_lines) != new_count:
                raise Refused("EDIT_PATCH_INVALID")
            if (old_count and old_start == 0) or (new_count and new_start == 0):
                raise Refused("EDIT_PATCH_INVALID")
            entry["hunks"].append(
                {
                    "old_start": old_start,
                    "new_start": new_start,
                    "old": old_lines,
                    "new": new_lines,
                }
            )
            hunks += 1
            if hunks > MAX_PATCH_HUNKS:
                raise Refused("EDIT_PATCH_TOO_LARGE")
        if not entry["hunks"]:
            raise Refused("EDIT_PATCH_INVALID")
        files.append(entry)
        if len(files) > MAX_PATCH_FILES:
            raise Refused("EDIT_PATCH_TOO_LARGE")
    paths = [entry["path"] for entry in files]
    if len(set(path.casefold() for path in paths)) != len(paths):
        raise Refused("EDIT_PATCH_DUPLICATE_PATH")
    return files


def _restricted_patch_path(path):
    parts = {part.casefold() for part in path.split("/")}
    folded = path.casefold()
    if parts & VENDOR_PARTS:
        return "EDIT_VENDOR_PATH_UNSUPPORTED"
    if parts & GENERATED_PARTS or folded.endswith(GENERATED_SUFFIXES):
        return "EDIT_GENERATED_PATH_UNSUPPORTED"
    return None


def _candidate(entry, raw):
    source = raw.splitlines(keepends=True)
    output = []
    cursor = 0
    delta = 0
    for hunk in entry["hunks"]:
        old = hunk["old"]
        expected = hunk["old_start"] if not old else hunk["old_start"] - 1
        if not old and not entry["new"] and raw:
            raise Refused("EDIT_PATCH_CONTEXT_REQUIRED")
        matches = [
            at
            for at in range(0, len(source) - len(old) + 1)
            if source[at : at + len(old)] == old
        ]
        if old and not matches:
            raise Refused("EDIT_PATCH_CONTEXT_STALE")
        if old and len(matches) != 1:
            raise Refused("EDIT_PATCH_CONTEXT_DUPLICATE")
        if expected < cursor:
            raise Refused("EDIT_PATCH_INVALID")
        if expected > len(source):
            raise Refused("EDIT_PATCH_CONTEXT_STALE")
        if source[expected : expected + len(old)] != old:
            raise Refused("EDIT_PATCH_CONTEXT_STALE")
        next_start = expected + delta + (1 if hunk["new"] else 0)
        if hunk["new_start"] != next_start:
            raise Refused("EDIT_PATCH_INVALID")
        output.extend(source[cursor:expected])
        output.extend(hunk["new"])
        cursor = expected + len(old)
        delta += len(hunk["new"]) - len(old)
    output.extend(source[cursor:])
    return b"".join(output)


def _rollback_patch(record, committed, expected_digest):
    try:
        for item in reversed(committed):
            with opened_parent(record["root"], item["path"]) as (parent, name):
                with opened(record["root"], item["path"]) as (
                    _,
                    __,
                    ___,
                    ____,
                    current,
                ):
                    if current != item["candidate"]:
                        return False
                if item["before"] is None:
                    os.unlink(name, dir_fd=parent)
                else:
                    rollback = ".sanctum-edit-" + secrets.token_hex(16)
                    fd = os.open(
                        rollback,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        item["mode"],
                        dir_fd=parent,
                    )
                    try:
                        with os.fdopen(fd, "wb", closefd=False) as stream:
                            stream.write(item["before"])
                            stream.flush()
                        os.fchmod(fd, item["mode"])
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    os.replace(rollback, name, src_dir_fd=parent, dst_dir_fd=parent)
        rows = task_evidence.inventory(record["root"])
        return (
            task_evidence.digest(task_evidence.content_identity(rows))
            == expected_digest
        )
    except Exception:
        return False


def apply_patch(settings, record, patch, authorize=mutation_authority):
    """Apply one exact multi-file text patch with preflight and rollback."""
    try:
        entries = parse_patch(patch)
    except Refused as error:
        return fail(str(error))
    result = None
    mutated = False
    try:
        with locked(settings, record) as (state, directory):
            value, _ = task_evidence.load(settings, record)
            contract = value["contract"]
            before = task_evidence.check(settings, record)
            if before["integrity"] != "PASS":
                return fail("EDIT_PROTECTED_INPUT")
            initial_rows = task_evidence.inventory(record["root"])
            prepared = []
            total = 0
            for entry in entries:
                path = entry["path"]
                restricted = _restricted_patch_path(path)
                if restricted:
                    return fail(restricted)
                if protected_or_disallowed(contract, value["original"], path):
                    return fail("EDIT_PROTECTED_INPUT")
                if entry["new"]:
                    if any(
                        existing.casefold() == path.casefold()
                        for existing in initial_rows
                    ):
                        return fail("EDIT_DESTINATION_EXISTS")
                    try:
                        with opened_parent(record["root"], path):
                            pass
                    except Refused as error:
                        return fail(str(error))
                    raw, mode, info = b"", 0o600, None
                else:
                    try:
                        with opened(record["root"], path) as (_, __, ___, info, raw):
                            mode = stat.S_IMODE(info.st_mode)
                    except Refused as error:
                        code = str(error)
                        if code == "EDIT_REPLACEMENT_TOO_LARGE":
                            return fail("EDIT_FILE_TOO_LARGE")
                        if code in (
                            "EDIT_FILE_TYPE_UNSUPPORTED",
                            "EDIT_ENCODING_UNSUPPORTED",
                        ):
                            return fail("EDIT_BINARY_FILE_UNSUPPORTED")
                        return fail(
                            code if code.startswith("EDIT_") else "EDIT_PATH_INVALID"
                        )
                try:
                    candidate = _candidate(entry, raw)
                except Refused as error:
                    return fail(str(error))
                if candidate == raw:
                    return fail("EDIT_NO_CHANGE")
                if len(candidate) > MAX_FILE:
                    return fail("EDIT_FILE_TOO_LARGE")
                total += len(candidate)
                if total > MAX_PATCH_RESULT:
                    return fail("EDIT_PATCH_TOO_LARGE")
                prepared.append(
                    {
                        "path": path,
                        "before": None if entry["new"] else raw,
                        "candidate": candidate,
                        "mode": mode,
                        "info": info,
                    }
                )

            diff = b"".join(
                canonical_diff(item["path"], item["before"], item["candidate"])
                for item in prepared
            )
            if len(diff) > MAX_PATCH:
                return fail("EDIT_PATCH_TOO_LARGE")
            decision = authorize(settings, record, diff)
            if decision.get("outcome") != "ALLOW" or decision.get(
                "canonical_diff_digest"
            ) != sha(diff):
                return fail("EDIT_AUTHORITY_DENIED")
            rows = task_evidence.inventory(record["root"])
            if (
                task_evidence.digest(task_evidence.content_identity(rows))
                != before["candidateDigest"]
            ):
                return fail("EDIT_APPLY_RACE")
            artifact = "edit-" + str(state["generation"] + 1)
            atomic(
                directory / (artifact + ".proposal.json"),
                (canonical({"operation": "patch", "patch": patch}) + "\n").encode(),
            )
            staged = []
            committed = []
            try:
                for item in prepared:
                    with opened_parent(record["root"], item["path"]) as (parent, _):
                        temp = ".sanctum-edit-" + secrets.token_hex(16)
                        fd = os.open(
                            temp,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            item["mode"],
                            dir_fd=parent,
                        )
                        try:
                            with os.fdopen(fd, "wb", closefd=False) as stream:
                                stream.write(item["candidate"])
                                stream.flush()
                            os.fchmod(fd, item["mode"])
                            os.fsync(fd)
                        finally:
                            os.close(fd)
                        staged.append((item, temp))
                for item, temp in staged:
                    with opened_parent(record["root"], item["path"]) as (parent, name):
                        if item["before"] is None:
                            rename_exclusive(parent, temp, parent, name)
                        else:
                            with opened(record["root"], item["path"]) as (
                                _,
                                __,
                                ___,
                                current,
                                raw,
                            ):
                                if (
                                    identity(current) != identity(item["info"])
                                    or raw != item["before"]
                                ):
                                    raise Refused("EDIT_APPLY_RACE")
                            os.replace(
                                temp,
                                name,
                                src_dir_fd=parent,
                                dst_dir_fd=parent,
                            )
                        committed.append(item)
                        mutated = True
                staged = []
            except Exception:
                for item, temp in staged:
                    try:
                        with opened_parent(record["root"], item["path"]) as (parent, _):
                            os.unlink(temp, dir_fd=parent)
                    except Exception:
                        pass
                staged = []
                rolled_back = _rollback_patch(
                    record, committed, before["candidateDigest"]
                )
                result = {
                    "ok": False,
                    "code": "EDIT_PATCH_APPLY_FAILED",
                    "executionState": (
                        "NOT_STARTED" if rolled_back else "COMPLETION_UNKNOWN"
                    ),
                    "rollback": "COMPLETED" if rolled_back else "UNKNOWN",
                }
                return result
            finally:
                for item, temp in staged:
                    try:
                        with opened_parent(record["root"], item["path"]) as (parent, _):
                            os.unlink(temp, dir_fd=parent)
                    except Exception:
                        pass

            state["generation"] += 1
            for item in prepared:
                state["observations"].pop(item["path"], None)
                if item["path"] not in state["required"]:
                    state["required"].append(item["path"])
            after = task_evidence.check(settings, record)
            expected = task_evidence.content_identity(initial_rows)
            for item in prepared:
                expected[item["path"]] = {
                    "kind": "file",
                    "mode": item["mode"],
                    "digest": sha(item["candidate"]),
                    "size": len(item["candidate"]),
                }
            if after["integrity"] != "PASS" or after[
                "candidateDigest"
            ] != task_evidence.digest(expected):
                return {
                    "ok": False,
                    "code": "EDIT_APPLY_RACE",
                    "executionState": "COMPLETION_UNKNOWN",
                }
            receipt = {
                "operation": "patch",
                "paths": [item["path"] for item in prepared],
                "canonical_diff_digest": sha(diff),
                "workspace_generation": state["generation"],
                "proposal_digest": sha(patch.encode()),
                "authority_result": decision["outcome"],
                "host_invention_count": 0,
                "fuzzy_match_count": 0,
                "diff_correspondence": True,
                "rollback": "NOT_NEEDED",
            }
            atomic(directory / (artifact + ".diff"), diff)
            atomic(
                directory / (artifact + ".json"),
                (canonical(receipt) + "\n").encode(),
            )
            result = {
                "ok": True,
                "code": "OK",
                "executionState": "COMPLETED",
                "receipt": receipt,
            }
            return result
    except Exception:
        return {
            "ok": False,
            "code": "EDIT_STATE_UNAVAILABLE",
            "executionState": (
                "COMPLETION_UNKNOWN"
                if mutated
                or (result and result.get("executionState") == "COMPLETION_UNKNOWN")
                else "NOT_STARTED"
            ),
        }


def apply(settings, record, arguments, authorize=mutation_authority):
    error = validate(arguments)
    if error:
        return fail(error)
    path = arguments["path"]
    old = arguments.get("old_text", "").encode()
    new = arguments.get("new_text", "").encode()
    result = None
    try:
        with locked(settings, record) as (state, directory):
            result = (
                _apply(
                    settings, record, arguments, state, directory, authorize, old, new
                )
                if "operation" not in arguments
                else _apply_file_operation(
                    settings, record, arguments, state, directory, authorize, new
                )
            )
            if result.get("ok") or result.get("code") in RECOVER:
                observed = (
                    arguments.get("destination")
                    if arguments.get("operation") == "move"
                    else None if arguments.get("operation") == "delete" else path
                )
                if observed and observed not in state["required"]:
                    state["required"].append(observed)
                for affected in {path, arguments.get("destination")} - {None}:
                    state["observations"].pop(affected, None)
        return result
    except Exception:
        uncertain = result is not None and (
            result.get("ok") or result.get("executionState") == "COMPLETION_UNKNOWN"
        )
        return {
            "ok": False,
            "code": "EDIT_STATE_UNAVAILABLE",
            "executionState": "COMPLETION_UNKNOWN" if uncertain else "NOT_STARTED",
        }


@contextlib.contextmanager
def opened_parent(root, path):
    """Open the destination parent without following any path component."""
    try:
        task_evidence.path_name(path)
    except Refused:
        raise Refused("EDIT_PATH_INVALID") from None
    fds = []
    try:
        current = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fds.append(current)
        for part in path.split("/")[:-1]:
            current = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current
            )
            fds.append(current)
        yield current, path.split("/")[-1]
    except OSError:
        raise Refused("EDIT_PATH_INVALID") from None
    finally:
        for fd in reversed(fds):
            os.close(fd)


def rename_exclusive(source_parent, source, destination_parent, destination):
    """Atomically rename without replacing a destination on Darwin or Linux."""
    libc = ctypes.CDLL(None, use_errno=True)
    raw_source = os.fsencode(source)
    raw_destination = os.fsencode(destination)
    if hasattr(libc, "renameatx_np"):
        result = libc.renameatx_np(
            source_parent,
            ctypes.c_char_p(raw_source),
            destination_parent,
            ctypes.c_char_p(raw_destination),
            0x00000004,  # RENAME_EXCL
        )
    elif hasattr(libc, "renameat2"):
        result = libc.renameat2(
            source_parent,
            ctypes.c_char_p(raw_source),
            destination_parent,
            ctypes.c_char_p(raw_destination),
            1,  # RENAME_NOREPLACE
        )
    else:
        raise Refused("EDIT_OPERATION_UNAVAILABLE")
    if result:
        error = ctypes.get_errno()
        if error in (errno.EEXIST, errno.ENOTEMPTY):
            raise Refused("EDIT_DESTINATION_EXISTS")
        raise OSError(error, os.strerror(error))


def protected_or_disallowed(contract, original, path):
    fold = path.casefold()
    if any(
        fold == protected.casefold()
        or fold.startswith(protected.casefold() + "/")
        or protected.casefold().startswith(fold + "/")
        for protected in contract["protected"]
    ):
        return True
    if path not in original:
        # On case-insensitive hosts a differently cased name can resolve to an
        # existing file. Never treat that alias as permission to create a new
        # file when the existing one is outside the mutable scope.
        if any(existing.casefold() == fold for existing in original):
            return True
        return not contract["allow_new"]
    return contract["mutable"] != "*" and path not in (
        contract["mutable"] + contract["mutable_tests"]
    )


def observed_source(state, record, path, raw):
    observation = state["observations"].get(path)
    if path in state["required"] or not observation:
        return "EDIT_SOURCE_NOT_OBSERVED"
    if (
        observation["task_id"] != record["workspace_id"]
        or observation["workspace_id"] != record["workspace_id"]
    ):
        return "EDIT_SOURCE_NOT_OBSERVED"
    if sha(raw) != observation["digest"]:
        return "EDIT_SOURCE_STALE"
    return None


def _apply_file_operation(settings, record, args, state, directory, authorize, content):
    operation = args["operation"]
    path = args["path"]
    destination = args.get("destination")
    value, _ = task_evidence.load(settings, record)
    contract = value["contract"]
    if protected_or_disallowed(contract, value["original"], path) or (
        destination
        and protected_or_disallowed(contract, value["original"], destination)
    ):
        return fail("EDIT_PROTECTED_INPUT")
    before = task_evidence.check(settings, record)
    if before["integrity"] != "PASS":
        return fail("EDIT_PROTECTED_INPUT")
    temp = None
    mutated = False
    try:
        source = None
        source_context = opened(record["root"], path) if operation != "create" else None
        with contextlib.ExitStack() as stack:
            if source_context:
                source_parent, source_name, _, source_info, source = (
                    stack.enter_context(source_context)
                )
                error = observed_source(state, record, path, source)
                if error:
                    return fail(error)
            destination_path = destination if operation == "move" else path
            destination_parent, destination_name = stack.enter_context(
                opened_parent(record["root"], destination_path)
            )
            try:
                os.stat(
                    destination_name, dir_fd=destination_parent, follow_symlinks=False
                )
                if operation == "create" or destination_path != path:
                    return fail("EDIT_DESTINATION_EXISTS")
            except FileNotFoundError:
                if operation != "create" and destination_path == path:
                    return fail("EDIT_PATH_INVALID")
            initial_rows = task_evidence.inventory(record["root"])
            if any(
                candidate.casefold() == destination_path.casefold()
                and candidate != destination_path
                for candidate in initial_rows
            ):
                return fail("EDIT_DESTINATION_EXISTS")

            diff = (
                canonical_diff(path, None, content)
                if operation == "create"
                else (
                    canonical_diff(path, source, None)
                    if operation == "delete"
                    else canonical_diff(path, source, None)
                    + canonical_diff(destination, None, source)
                )
            )
            decision = authorize(settings, record, diff)
            if decision.get("outcome") != "ALLOW" or decision.get(
                "canonical_diff_digest"
            ) != sha(diff):
                return fail("EDIT_AUTHORITY_DENIED")

            rows = task_evidence.inventory(record["root"])
            if (
                task_evidence.digest(task_evidence.content_identity(rows))
                != before["candidateDigest"]
            ):
                return fail("EDIT_APPLY_RACE")
            expected = task_evidence.content_identity(rows)
            artifact = "edit-" + str(state["generation"] + 1)
            atomic(
                directory / (artifact + ".proposal.json"),
                (canonical(args) + "\n").encode(),
            )
            if operation == "create":
                temp = ".sanctum-edit-" + secrets.token_hex(16)
                out = os.open(
                    temp,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=destination_parent,
                )
                try:
                    with os.fdopen(out, "wb", closefd=False) as stream:
                        stream.write(content)
                        stream.flush()
                    os.fsync(out)
                finally:
                    os.close(out)
                rename_exclusive(
                    destination_parent,
                    temp,
                    destination_parent,
                    destination_name,
                )
                temp = None
                mutated = True
                expected[path] = {
                    "kind": "file",
                    "mode": 0o600,
                    "digest": sha(content),
                    "size": len(content),
                }
            elif operation == "delete":
                if identity(
                    os.stat(source_name, dir_fd=source_parent, follow_symlinks=False)
                ) != identity(source_info):
                    return fail("EDIT_APPLY_RACE")
                os.unlink(source_name, dir_fd=source_parent)
                mutated = True
                expected.pop(path)
            else:
                if identity(
                    os.stat(source_name, dir_fd=source_parent, follow_symlinks=False)
                ) != identity(source_info):
                    return fail("EDIT_APPLY_RACE")
                rename_exclusive(
                    source_parent,
                    source_name,
                    destination_parent,
                    destination_name,
                )
                mutated = True
                expected[destination] = expected.pop(path)

        state["generation"] += 1
        after = task_evidence.check(settings, record)
        if after["candidateDigest"] != task_evidence.digest(expected):
            return {
                "ok": False,
                "code": "EDIT_APPLY_RACE",
                "executionState": "COMPLETION_UNKNOWN",
            }
        if after["integrity"] != "PASS":
            return {
                "ok": False,
                "code": "PROTECTED_INPUT_MODIFIED",
                "executionState": "COMPLETION_UNKNOWN",
            }
        receipt = {
            "operation": operation,
            "old_digest": sha(source) if source is not None else None,
            "new_digest": (
                sha(content)
                if operation == "create"
                else sha(source) if operation == "move" else None
            ),
            "canonical_diff_digest": sha(diff),
            "workspace_generation": state["generation"],
            "proposal_digest": sha(canonical(args).encode()),
            "authority_result": decision["outcome"],
            "host_invention_count": 0,
            "fuzzy_match_count": 0,
            "diff_correspondence": True,
        }
        atomic(directory / (artifact + ".diff"), diff)
        atomic(directory / (artifact + ".json"), (canonical(receipt) + "\n").encode())
        return {
            "ok": True,
            "code": "OK",
            "executionState": "COMPLETED",
            "receipt": receipt,
        }
    except Refused as error:
        code = str(error) if str(error).startswith("EDIT_") else "EDIT_PROTECTED_INPUT"
        return {
            "ok": False,
            "code": code,
            "executionState": "COMPLETION_UNKNOWN" if mutated else "NOT_STARTED",
        }
    except Exception:
        return {
            "ok": False,
            "code": "EDIT_APPLY_RACE",
            "executionState": "COMPLETION_UNKNOWN" if mutated else "NOT_STARTED",
        }
    finally:
        if temp:
            try:
                with opened_parent(record["root"], path) as (parent, _):
                    os.unlink(temp, dir_fd=parent)
            except (OSError, Refused):
                pass


def _apply(settings, record, args, state, directory, authorize, old, new):
    path = args["path"]
    value, _ = task_evidence.load(settings, record)
    contract = value["contract"]
    fold = path.casefold()
    if any(
        fold == p.casefold()
        or fold.startswith(p.casefold() + "/")
        or p.casefold().startswith(fold + "/")
        for p in contract["protected"]
    ):
        return fail("EDIT_PROTECTED_INPUT")
    if (
        contract["mutable"] != "*"
        and path not in contract["mutable"] + contract["mutable_tests"]
    ):
        return fail("EDIT_PATH_NOT_MUTABLE")
    temp = None
    written = False
    try:
        with opened(record["root"], path) as (parent, name, fd, info, raw):
            observation = state["observations"].get(path)
            if path in state["required"] or not observation:
                return fail("EDIT_SOURCE_NOT_OBSERVED")
            if (
                observation["task_id"] != record["workspace_id"]
                or observation["workspace_id"] != record["workspace_id"]
            ):
                return fail("EDIT_SOURCE_NOT_OBSERVED")
            if sha(raw) != observation["digest"]:
                return fail("EDIT_SOURCE_STALE")
            # Count overlapping matches too; no choice of occurrence is inferred.
            matches = []
            start = 0
            while len(matches) < 2:
                at = raw.find(old, start)
                if at < 0:
                    break
                matches.append(at)
                start = at + 1
            if not matches:
                return fail("EDIT_TARGET_NOT_FOUND")
            if len(matches) != 1:
                return fail("EDIT_TARGET_NOT_UNIQUE")
            if old not in observation["text"].encode():
                return fail("EDIT_SOURCE_NOT_OBSERVED")
            if old == new:
                return fail("EDIT_NO_CHANGE")
            at = matches[0]
            candidate = raw[:at] + new + raw[at + len(old) :]
            if len(candidate) > MAX_FILE:
                return fail("EDIT_REPLACEMENT_TOO_LARGE")
            before = task_evidence.check(settings, record)
            if before["integrity"] != "PASS":
                return fail("EDIT_PROTECTED_INPUT")
            diff = canonical_diff(path, raw, candidate)
            decision = authorize(settings, record, diff)
            if decision.get("outcome") != "ALLOW" or decision.get(
                "canonical_diff_digest"
            ) != sha(diff):
                return fail("EDIT_AUTHORITY_DENIED")
            temp = ".sanctum-edit-" + secrets.token_hex(16)
            out = os.open(
                temp,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            try:
                with os.fdopen(out, "wb", closefd=False) as stream:
                    stream.write(candidate)
                    stream.flush()
                os.fchmod(out, stat.S_IMODE(info.st_mode))
                os.fsync(out)
            finally:
                os.close(out)
            # Every supported host workspace operation shares the task lock.
            # Candidate commands have a copy, never a live host mount.
            # Exclude only this host-created temporary from the final inventory.
            rows = task_evidence.inventory(record["root"])
            rows.pop("/".join(path.split("/")[:-1] + [temp]), None)
            if (
                task_evidence.digest(task_evidence.content_identity(rows))
                != before["candidateDigest"]
            ):
                return fail("EDIT_APPLY_RACE")
            expected = task_evidence.content_identity(rows)
            expected[path] = {
                **expected[path],
                "digest": sha(candidate),
                "size": len(candidate),
            }
            artifact = "edit-" + str(state["generation"] + 1)
            atomic(
                directory / (artifact + ".proposal.json"),
                (canonical(args) + "\n").encode(),
            )
            atomic(directory / (artifact + ".before"), raw)
            with opened(record["root"], path) as (p2, n2, f2, i2, r2):
                if (
                    identity(i2) != identity(info)
                    or r2 != raw
                    or identity(os.fstat(parent))[:2] != identity(os.fstat(p2))[:2]
                ):
                    return fail("EDIT_APPLY_RACE")
                os.replace(temp, name, src_dir_fd=parent, dst_dir_fd=parent)
                temp = None
                written = True
            state["generation"] += 1
            after = task_evidence.check(settings, record)
            if after["candidateDigest"] != task_evidence.digest(expected):
                return {
                    "ok": False,
                    "code": "EDIT_APPLY_RACE",
                    "executionState": "COMPLETION_UNKNOWN",
                }
            if after["integrity"] != "PASS":
                return {
                    "ok": False,
                    "code": "PROTECTED_INPUT_MODIFIED",
                    "executionState": "COMPLETION_UNKNOWN",
                }
            with opened(record["root"], path) as (_, __, ___, ____, actual):
                if actual != candidate:
                    return {
                        "ok": False,
                        "code": "EDIT_APPLY_RACE",
                        "executionState": "COMPLETION_UNKNOWN",
                    }
            receipt = {
                "old_digest": sha(raw),
                "new_digest": sha(candidate),
                "canonical_diff_digest": sha(diff),
                "workspace_generation": state["generation"],
                "proposal_digest": sha(canonical(args).encode()),
                "authority_result": decision["outcome"],
                "host_invention_count": 0,
                "fuzzy_match_count": 0,
                "diff_correspondence": True,
            }
            # Private diff is an audit artifact, never an authority grant.
            atomic(directory / ("edit-" + str(state["generation"]) + ".diff"), diff)
            atomic(
                directory / ("edit-" + str(state["generation"]) + ".json"),
                (canonical(receipt) + "\n").encode(),
            )
            return {
                "ok": True,
                "code": "OK",
                "executionState": "COMPLETED",
                "receipt": receipt,
            }
    except Refused as error:
        code = str(error) if str(error).startswith("EDIT_") else "EDIT_PROTECTED_INPUT"
        return {
            "ok": False,
            "code": code,
            "executionState": "COMPLETION_UNKNOWN" if written else "NOT_STARTED",
        }
    except Exception:
        return {
            "ok": False,
            "code": "EDIT_APPLY_RACE",
            "executionState": "COMPLETION_UNKNOWN" if written else "NOT_STARTED",
        }
    finally:
        if temp:
            # parent may already be closed by the context manager; use a fresh
            # anchored directory only if it is still the same directory.
            try:
                with opened(record["root"], path) as (p, _, __, ___, ____):
                    os.unlink(temp, dir_fd=p)
            except (OSError, Refused):
                pass
