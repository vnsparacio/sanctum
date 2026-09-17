"""Explicit diagnostic ownership in the existing private control.sqlite.

Only fixed codes, identities, timestamps and bounded counters are persisted.
Reservations are durable before transmission and are never refunded.
"""
import contextlib
import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
import time
from common import BASE, Refused, canonical, database, strict_json

LIMITS = {'total': 6, 'readiness': 1, 'proposal': 5,
          'readiness_tokens': 16, 'proposal_tokens': 1024}
CLEANUP_SECONDS = 120
MIN_CALL_SECONDS = 1
IDENTITY_KEYS = {'experiment_id', 'source_id', 'install_id', 'deadline'}
STOP_CODES = {'DEADLINE', 'CALLER_LOST', 'WORKER_LOST', 'CANCELLED', 'READINESS_FAILED',
              'PROBE_FAILED', 'PROBES_COMPLETE', 'DISPATCH_UNCERTAIN', 'BUDGET', 'ALLOCATION_FAILED', 'IDENTITY'}


def process_identity(pid):
    if type(pid) is not int or pid < 1: return None
    try:
        result = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'lstart='],
                                capture_output=True, timeout=2, check=False)
        if result.returncode or not result.stdout.strip(): return None
        return hashlib.sha256(result.stdout.strip()).hexdigest()
    except (OSError, subprocess.SubprocessError): return None


def installed_identity(base=BASE):
    """Read only public byte identities from the installation receipt/freeze."""
    receipt = strict_json((base.parent / 'receipt.json').read_text())
    source = receipt.get('work_mode_source_manifest_sha256')
    freeze = base / 'FREEZE.json'
    install = hashlib.sha256(freeze.read_bytes()).hexdigest()
    if not hex_id(source, 64): raise Refused('experiment_source_identity')
    return {'source_id': source, 'install_id': install}


def hex_id(value, size):
    return type(value) is str and re.fullmatch('[a-f0-9]{'+str(size)+'}', value) is not None


def validate_binding(value):
    if (type(value) is not dict or set(value) != IDENTITY_KEYS or
        not hex_id(value['experiment_id'], 32) or
        any(not hex_id(value[k], 64) for k in ('source_id', 'install_id')) or
        type(value['deadline']) not in (int, float) or not math.isfinite(value['deadline'])):
        raise Refused('experiment_binding')
    return value


class ExperimentLedger:
    def __init__(self, root, now=time.time):
        self.root, self.now = Path(root), now
        with database(self.root) as c:
            c.execute('create table if not exists experiments (id text primary key, record text not null)')
            c.execute('create table if not exists experiment_attempts '
                      '(experiment text, number integer, class text, tokens integer, reserved real, '
                      'dispatched real, completed real, outcome text, pid integer, process text, '
                      'primary key(experiment,number))')

    @contextlib.contextmanager
    def transaction(self):
        with database(self.root) as c:
            c.execute('begin immediate')
            yield c

    def _read(self, c, experiment_id):
        row = c.execute('select record from experiments where id=?', (experiment_id,)).fetchone()
        if not row: raise Refused('experiment_missing')
        return strict_json(row[0])

    def _write(self, c, r):
        c.execute('update experiments set record=? where id=?', (canonical(r), r['experiment_id']))

    def _bound(self, c, binding, identity=None):
        validate_binding(binding)
        r = self._read(c, binding['experiment_id'])
        if any(r[k] != binding[k] for k in IDENTITY_KEYS): raise Refused('experiment_stale')
        if identity is not None and any(r[k] != identity.get(k) for k in ('source_id','install_id')):
            raise Refused('experiment_identity')
        return r

    def _current(self, c):
        rows = [strict_json(x[0]) for x in c.execute('select record from experiments')]
        open_rows = [r for r in rows if r['state'] != 'COMPLETE']
        if len(open_rows) > 1: raise Refused('experiment_ownership_ambiguous')
        return open_rows[0] if open_rows else None

    def current(self):
        with self.transaction() as c: return self._current(c)

    def create(self, binding, *, owner_pid, owner_process, expires=None, ordinary_root=None):
        validate_binding(binding)
        now = self.now(); expires = binding['deadline'] if expires is None else expires
        if (not now < expires <= binding['deadline'] <= now + 900 or
            type(owner_pid) is not int or owner_pid < 1 or not hex_id(owner_process,64)):
            raise Refused('experiment_envelope')
        r = {**binding, 'created': now, 'expires': expires, 'limits': dict(LIMITS),
             'owner_pid': owner_pid, 'owner_process': owner_process, 'state': 'ACTIVE',
             'stop_code': None, 'cleanup': 'NOT_REQUIRED', 'allocation': 'NONE',
             'allocation_name': None, 'allocation_id': None, 'allocation_attempts': 0,
             'allocation_pid': None, 'allocation_process': None, 'allocation_inflight': False,
             'cancel_requested': None, 'control_pid': None, 'control_process': None,
             'lease_scope': None, 'worker_pid': None, 'worker_process': None, 'ready': False, 'supervisor_heartbeat': None,
             'supervisor_pid': None, 'supervisor_process': None, 'absent_confirmed': None}
        with self.transaction() as c:
            if self._current(c): raise Refused('experiment_owned')
            # Ordinary admission takes this same transaction before either lease
            # store. Do not create diagnostic ownership over an existing lease,
            # including inactive/expired rows whose owner has not reconciled them.
            if c.execute('select count(*) from leases').fetchone()[0]:
                raise Refused('experiment_existing_leases')
            if ordinary_root is not None and Path(ordinary_root) != self.root:
                from retirement import require_reconciled
                require_reconciled(ordinary_root)
            c.execute('insert into experiments values (?,?)', (binding['experiment_id'], canonical(r)))
        return self.snapshot(binding)

    def _admit(self, r):
        from retirement import require_reconciled
        require_reconciled(self.root.parent)
        if r['state'] != 'ACTIVE': raise Refused('experiment_terminal')
        if self.now() >= min(r['expires'], r['deadline'] - CLEANUP_SECONDS):
            raise Refused('experiment_deadline')

    def check(self, binding, identity=None):
        with self.transaction() as c:
            r = self._bound(c, binding, identity); self._admit(r)
            return r

    def remaining(self, binding, cap, *, cleanup=False):
        with self.transaction() as c:
            r = self._bound(c, binding)
            if not cleanup: self._admit(r)
            remaining = min(r['expires'], r['deadline'] - (0 if cleanup else CLEANUP_SECONDS)) - self.now()
            if remaining < MIN_CALL_SECONDS: raise Refused('experiment_deadline')
            return min(cap, remaining)

    def reserve(self, binding, identity, call_class, tokens, *, pid=None, process=None):
        if call_class not in ('readiness', 'proposal') or type(tokens) is not int or tokens < 1:
            raise Refused('experiment_call_class')
        pid = os.getpid() if pid is None else pid
        process = process_identity(pid) if process is None else process
        if not hex_id(process,64): raise Refused('experiment_worker_identity')
        with self.transaction() as c:
            r = self._bound(c, binding, identity); self._admit(r)
            if min(r['expires'], r['deadline'] - CLEANUP_SECONDS) - self.now() < MIN_CALL_SECONDS:
                raise Refused('experiment_deadline')
            if tokens > r['limits'][call_class+'_tokens']: raise Refused('experiment_token_limit')
            rows = list(c.execute('select class from experiment_attempts where experiment=?', (r['experiment_id'],)))
            if len(rows) >= r['limits']['total']: raise Refused('experiment_total_limit')
            if sum(x[0] == call_class for x in rows) >= r['limits'][call_class]: raise Refused('experiment_class_limit')
            number = len(rows) + 1
            c.execute('insert into experiment_attempts values (?,?,?,?,?,NULL,NULL,?,?,?)',
                      (r['experiment_id'],number,call_class,tokens,self.now(),'UNCERTAIN',pid,process))
            return number

    def dispatched(self, binding, number):
        # This means dispatch began locally, not provider acknowledgement. A crash
        # between this commit and send remains uncertain and consumes the attempt.
        with self.transaction() as c:
            r = self._bound(c,binding); self._admit(r)
            row=c.execute('select dispatched from experiment_attempts where experiment=? and number=?',
                          (r['experiment_id'],number)).fetchone()
            if not row or row[0] is not None: raise Refused('experiment_attempt_state')
            c.execute('update experiment_attempts set dispatched=? where experiment=? and number=?',
                      (self.now(),r['experiment_id'],number))

    def completion(self, binding, number, known):
        with self.transaction() as c:
            r=self._bound(c,binding)
            c.execute('update experiment_attempts set completed=?,outcome=? where experiment=? and number=? and outcome=?',
                      (self.now() if known else None,'KNOWN' if known else 'UNCERTAIN',r['experiment_id'],number,'UNCERTAIN'))

    def stop(self, binding, code):
        if code not in STOP_CODES: raise Refused('experiment_stop_code')
        with self.transaction() as c:
            r=self._bound(c,binding)
            if r['state'] != 'COMPLETE':
                r.update(state='CLEANUP_REQUIRED',cleanup='REQUIRED',stop_code=r['stop_code'] or code)
                self._write(c,r)

    def snapshot(self, binding):
        with self.transaction() as c:
            r=self._bound(c,binding)
            rows=list(c.execute('select number,class,tokens,reserved,dispatched,completed,outcome,pid,process '
                                'from experiment_attempts where experiment=? order by number',(r['experiment_id'],)))
            r['attempts']=[dict(zip(('number','class','tokens','reserved','dispatched','completed','outcome','pid','process'),row)) for row in rows]
            r['counts']={'reserved':len(rows),'dispatched':sum(x[4] is not None for x in rows),
                         'known_completion':sum(x[6]=='KNOWN' for x in rows),'uncertain_completion':sum(x[6]=='UNCERTAIN' for x in rows)}
            return r


class ExperimentDispatch:
    def __init__(self, ledger, binding, identity):
        self.ledger,self.binding,self.identity=ledger,validate_binding(binding),identity
        self.number=None; self.known=False

    def timeout(self, cap): return self.ledger.remaining(self.binding,cap)

    @contextlib.contextmanager
    def attempt(self, call_class, tokens):
        self.number=self.ledger.reserve(self.binding,self.identity,call_class,tokens)
        self.known=False
        try:
            self.ledger.dispatched(self.binding,self.number)
            yield self
        except BaseException:
            if call_class=='readiness': self.ledger.stop(self.binding,'READINESS_FAILED')
            elif not self.known: self.ledger.stop(self.binding,'DISPATCH_UNCERTAIN')
            raise
        finally:
            self.ledger.completion(self.binding,self.number,self.known)

    def completed(self): self.known=True
