"""Small local primitives. Errors are codes; never echo provider bodies or private input."""

import contextlib
import errno
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


class Refused(ValueError):
    pass


# Local operational floors, never model-selected. Cleanup has no admission floor.
STORAGE_START_BYTES = 2 * 1024**3
STORAGE_RUN_BYTES = 512 * 1024**2
_RESERVE_BYTES = 4 * 1024**2
_RESERVE_MAGIC = b"sanctum-cleanup-reserve/v1\n"


def storage_error(error):
    if isinstance(error, OSError) and error.errno in (errno.ENOSPC, errno.EDQUOT):
        return "local_disk_full"
    if (
        isinstance(error, sqlite3.Error)
        and (getattr(error, "sqlite_errorcode", 0) & 255) == sqlite3.SQLITE_FULL
    ):
        return "local_disk_full"
    return None


def storage_headroom(path, minimum=STORAGE_RUN_BYTES):
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        if shutil.disk_usage(probe).free < minimum:
            raise Refused("local_disk_low")
    except OSError as error:
        raise Refused(storage_error(error) or "local_storage_unavailable") from None


@contextlib.contextmanager
def reserve_lock(root):
    fd = os.open(
        Path(root) / "cleanup-storage.lock",
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o600,
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def prepare_cleanup_reserve(root):
    with reserve_lock(root):
        _prepare_cleanup_reserve(root)


def _prepare_cleanup_reserve(root):
    """Allocate real blocks before admission; never use a sparse reservation."""
    path = Path(root) / "cleanup-storage.reserve"
    if path.exists() or path.is_symlink():
        _check_reserve(path)
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(_RESERVE_MAGIC)
            block = bytes(64 * 1024)
            remaining = _RESERVE_BYTES - len(_RESERVE_MAGIC)
            while remaining:
                size = min(remaining, len(block))
                stream.write(block[:size])
                remaining -= size
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _check_reserve(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(fd)
        if (
            not stat.S_ISREG(meta.st_mode)
            or meta.st_uid != os.getuid()
            or meta.st_nlink != 1
            or meta.st_mode & 0o077
            or meta.st_size != _RESERVE_BYTES
            or os.read(fd, len(_RESERVE_MAGIC)) != _RESERVE_MAGIC
        ):
            raise Refused("cleanup_reserve_invalid")
        return meta.st_ino
    finally:
        os.close(fd)


def release_cleanup_reserve(root):
    with reserve_lock(root):
        _release_cleanup_reserve(root)


def _release_cleanup_reserve(root):
    """Free only our marked reserve under pressure, before normal lease writes."""
    try:
        storage_headroom(root)
        return
    except Refused as error:
        if str(error) not in ("local_disk_low", "local_disk_full"):
            raise
    path = Path(root) / "cleanup-storage.reserve"
    if not path.exists() and not path.is_symlink():
        return
    inode = _check_reserve(path)
    if path.lstat().st_ino != inode:
        raise Refused("cleanup_reserve_invalid")
    path.unlink()


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise Refused("duplicate_json_key")
            result[k] = v
        return result

    return json.loads(
        raw,
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(Refused("nonfinite_json")),
    )


def private_dir(path):
    p = Path(path)
    if p.is_symlink():
        raise Refused("unsafe_state_directory")
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    if p.stat().st_mode & 0o077:
        raise Refused("unsafe_state_permissions")
    return p


def atomic(path, data):
    p = Path(path)
    if p.is_symlink():
        raise Refused("unsafe_file")
    t = p.with_name(p.name + "." + os.urandom(8).hex() + ".tmp")
    fd = os.open(t, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(t, p)
    finally:
        t.unlink(missing_ok=True)


@contextlib.contextmanager
def database(root):
    p = private_dir(root) / "control.sqlite"
    if p.is_symlink():
        raise Refused("unsafe_database")
    c = sqlite3.connect(p, timeout=30)
    p.chmod(0o600)
    c.execute("pragma busy_timeout=30000")
    c.execute(
        "create table if not exists nonces (nonce text primary key, expires real)"
    )
    c.execute(
        "create table if not exists network (id text primary key, tier text, charged real, status text)"
    )
    c.execute(
        "create table if not exists leases (scope text primary key, expires real, active integer, closing integer default 0)"
    )
    c.commit()
    try:
        with c:
            yield c
    finally:
        c.close()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Refused("redirect_refused")


def http(url, payload=None, headers=None, timeout=30, limit=1048576):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    req = urllib.request.Request(
        url,
        data=None if payload is None else canonical(payload).encode(),
        headers=headers or {},
    )
    try:
        with opener.open(req, timeout=timeout) as r:
            raw = r.read(limit + 1)
    except urllib.error.HTTPError as e:
        raise Refused("http_" + str(e.code)) from None
    except Exception:
        raise Refused("transport_unavailable") from None
    if len(raw) > limit:
        raise Refused("response_too_large")
    return strict_json(raw)


def load_settings():
    return strict_json((BASE / "SETTINGS.json").read_text())


def verify_release():
    for name, expected in strict_json((BASE / "FREEZE.json").read_text()).items():
        p = BASE / name
        if (
            p.is_symlink()
            or not p.resolve().is_relative_to(BASE)
            or hashlib.sha256(p.read_bytes()).hexdigest() != expected
        ):
            raise Refused("release_drift")
