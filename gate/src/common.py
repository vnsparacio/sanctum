"""Small local primitives. Errors are codes; never echo provider bodies or private input."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import urllib.request
import urllib.error

BASE = Path(__file__).resolve().parents[1]

class Refused(ValueError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result: raise Refused('duplicate_json_key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(Refused('nonfinite_json')))

def private_dir(path):
    p = Path(path)
    if p.is_symlink(): raise Refused('unsafe_state_directory')
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    if p.stat().st_mode & 0o077: raise Refused('unsafe_state_permissions')
    return p

def atomic(path, data):
    p = Path(path)
    if p.is_symlink(): raise Refused('unsafe_file')
    t = p.with_name(p.name + '.' + os.urandom(8).hex() + '.tmp')
    fd = os.open(t, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(t, p)
    finally:
        t.unlink(missing_ok=True)

@contextlib.contextmanager
def database(root):
    p = private_dir(root) / 'control.sqlite'
    if p.is_symlink(): raise Refused('unsafe_database')
    c = sqlite3.connect(p, timeout=30)
    p.chmod(0o600)
    c.execute('pragma busy_timeout=30000')
    c.execute('create table if not exists nonces (nonce text primary key, expires real)')
    c.execute('create table if not exists network (id text primary key, tier text, charged real, status text)')
    c.execute('create table if not exists leases (scope text primary key, expires real, active integer, closing integer default 0)')
    c.commit()
    try:
        with c: yield c
    finally: c.close()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise Refused('redirect_refused')

def http(url, payload=None, headers=None, timeout=30, limit=1048576):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    req = urllib.request.Request(url, data=None if payload is None else canonical(payload).encode(), headers=headers or {})
    try:
        with opener.open(req, timeout=timeout) as r: raw = r.read(limit + 1)
    except urllib.error.HTTPError as e:
        raise Refused('http_' + str(e.code)) from None
    except Exception:
        raise Refused('transport_unavailable') from None
    if len(raw) > limit: raise Refused('response_too_large')
    return strict_json(raw)

def load_settings():
    return strict_json((BASE / 'SETTINGS.json').read_text())

def verify_release():
    for name, expected in strict_json((BASE / 'FREEZE.json').read_text()).items():
        p = BASE / name
        if p.is_symlink() or not p.resolve().is_relative_to(BASE) or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise Refused('release_drift')
