"""One-allocation diagnostic lifecycle; independent sweep never allocates.

Provider absence is separate from local cancellation/timeout. An ambiguous create
stays owned even after a negative list: an in-flight provider create may arrive late.
"""

import fcntl
import os
import re
import signal

from common import BASE, Refused, database
from experiment import (
    IDENTITY_KEYS,
    ExperimentDispatch,
    ExperimentLedger,
    hex_id,
    process_identity,
)
from retirement import historical_ownership, require_reconciled


def binding_of(record):
    return {k: record[k] for k in IDENTITY_KEYS}


def alive(pid, identity):
    """True: identical live process; False: confirmed gone/replaced; None: unknown.

    A failed ps lookup cannot prove exit. A signal-zero probe sends no signal;
    only ESRCH proves absence. Permissions/errors and missing identity stay unknown.
    """
    if type(pid) is not int or pid < 1 or not hex_id(identity, 64):
        return None
    observed = process_identity(pid)
    if observed is not None:
        return observed == identity
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return None
    return None


class ExperimentSupervisor:
    def __init__(
        self, ledger, lifecycle, is_alive=alive, kill=os.kill, publish_heartbeat=False
    ):
        self.ledger, self.lc, self.is_alive, self.kill = (
            ledger,
            lifecycle,
            is_alive,
            kill,
        )
        self.publish_heartbeat = publish_heartbeat

    def tick(self):
        fd = os.open(
            self.lc.root / "experiment-supervisor.lock",
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                r = self.ledger.current()
                return self.ledger.snapshot(binding_of(r)) if r else None
            return self._tick()
        finally:
            os.close(fd)

    def _tick(self):
        r = self.ledger.current()
        if not r:
            return None
        b = binding_of(r)
        if self.publish_heartbeat:
            with self.ledger.transaction() as c:
                r = self.ledger._bound(c, b)
                r.update(
                    supervisor_heartbeat=self.ledger.now(),
                    supervisor_pid=os.getpid(),
                    supervisor_process=process_identity(os.getpid()),
                )
                self.ledger._write(c, r)
        snap = self.ledger.snapshot(b)
        try:
            require_reconciled(self.lc.settings["state_directory"])
        except Refused:
            self.ledger.stop(b, "IDENTITY")
        if self.ledger.now() >= min(r["expires"], r["deadline"] - 120):
            self.ledger.stop(b, "DEADLINE")
        elif not self.is_alive(r["owner_pid"], r["owner_process"]):
            self.ledger.stop(b, "CALLER_LOST")
        elif r.get("control_pid") and not self.is_alive(
            r["control_pid"], r["control_process"]
        ):
            self.ledger.stop(b, "WORKER_LOST")
        elif r.get("worker_pid") and not self.is_alive(
            r["worker_pid"], r["worker_process"]
        ):
            self.ledger.stop(b, "WORKER_LOST")
        elif any(
            a["outcome"] == "UNCERTAIN" and not self.is_alive(a["pid"], a["process"])
            for a in snap["attempts"]
        ):
            self.ledger.stop(b, "WORKER_LOST")
        r = self.ledger.snapshot(b)
        if r["state"] == "ACTIVE":
            return r
        self.lc.provider.experiment_deadline = r["deadline"]
        self.lc.provider.experiment_cleanup = True
        # Signal only recorded, still-identical local workers, never the caller or
        # another process that reused a PID. Persist the grace across restarts.
        first = r["cancel_requested"]
        if first is None:
            with self.ledger.transaction() as c:
                current = self.ledger._bound(c, b)
                current["cancel_requested"] = self.ledger.now()
                self.ledger._write(c, current)
        sig = (
            signal.SIGKILL
            if first is not None and self.ledger.now() - first >= 5
            else signal.SIGTERM
        )
        workers = [
            (r.get(k + "_pid"), r.get(k + "_process"))
            for k in ("control", "worker", "allocation")
        ]
        workers += [
            (a["pid"], a["process"])
            for a in r["attempts"]
            if a["outcome"] == "UNCERTAIN"
        ]
        for pid, identity in set(workers):
            if (
                pid
                and pid not in (os.getpid(), r["owner_pid"])
                and self.is_alive(pid, identity) is True
            ):
                try:
                    self.kill(pid, sig)
                except OSError:
                    pass
        # No lifecycle lock is held over network calls. A hung lifecycle worker
        # cannot prevent this independent owner from deleting its exact allocation.
        with database(self.lc.root) as c:
            if r["lease_scope"]:
                c.execute(
                    "update leases set closing=1 where scope=?", (r["lease_scope"],)
                )
        if r["allocation"] == "NONE":
            return self._terminal(b)
        try:
            pods = self.lc.provider.pods()
            matches = [
                p
                for p in pods
                if p.get("id") == r["allocation_id"]
                or p.get("name") == r["allocation_name"]
            ]
            if len(matches) > 1:
                raise Refused("experiment_allocation_ambiguous")
            if matches:
                pod_id = matches[0]["id"]
                with self.ledger.transaction() as c:
                    current = self.ledger._bound(c, b)
                    current.update(
                        allocation_id=pod_id,
                        allocation="OWNED",
                        cleanup="DELETE_REQUESTED",
                    )
                    if (
                        self.is_alive(
                            current["allocation_pid"], current["allocation_process"]
                        )
                        is False
                    ):
                        current["allocation_inflight"] = False
                    self.ledger._write(c, current)
                self.lc.provider.delete(pod_id)
                # A delete response alone is insufficient.
                pods = self.lc.provider.pods()
                if any(
                    p.get("id") == pod_id or p.get("name") == r["allocation_name"]
                    for p in pods
                ):
                    raise Refused("experiment_deletion_unknown")
            elif r["allocation_inflight"] or r["allocation"] == "UNCERTAIN":
                raise Refused("experiment_allocation_unknown")
            current = self.ledger.snapshot(b)
            if current["allocation_inflight"]:
                raise Refused("experiment_allocation_unknown")
            # Record provider-confirmed absence before reconciling local leases.
            with self.ledger.transaction() as c:
                current = self.ledger._bound(c, b)
                current.update(
                    allocation="ABSENT",
                    absent_confirmed=self.ledger.now(),
                    cleanup="ABSENT_CONFIRMED",
                )
                self.ledger._write(c, current)
            self.lc.provider.close_tunnel(self.lc.state())
            with self.lc.lock(blocking=False):
                state = self.lc.state()
                if (
                    state.get("pod_name") == r["allocation_name"]
                    or state.get("pod_id") == current["allocation_id"]
                ):
                    self.lc.save(
                        state,
                        phase="OFFLINE",
                        pod_id=None,
                        pod_name=None,
                        allocation_uncertain=False,
                        manual_stop=True,
                        absent_confirmed_at=self.ledger.now(),
                    )
            return self._terminal(b)
        except Exception:
            with self.ledger.transaction() as c:
                current = self.ledger._bound(c, b)
                current.update(cleanup="UNKNOWN")
                self.ledger._write(c, current)
            return self.ledger.snapshot(b)

    def _terminal(self, b):
        # Live/hung workers must exit before local request/lease cleanup is final.
        r = self.ledger.snapshot(b)
        workers = [
            (r.get(k + "_pid"), r.get(k + "_process"))
            for k in ("control", "worker", "allocation")
            if r.get(k + "_pid") is not None or r.get(k + "_process") is not None
        ]
        workers += [
            (a["pid"], a["process"])
            for a in r["attempts"]
            if a["outcome"] == "UNCERTAIN"
        ]
        if r["allocation_inflight"] or any(
            self.is_alive(pid, identity) is not False for pid, identity in workers
        ):
            with self.ledger.transaction() as c:
                current = self.ledger._bound(c, b)
                current.update(state="CLEANUP_REQUIRED", cleanup="LOCAL_PENDING")
                self.ledger._write(c, current)
            return self.ledger.snapshot(b)
        with self.ledger.transaction() as c:
            r = self.ledger._bound(c, b)
            if r["lease_scope"]:
                lease = c.execute(
                    "select active from leases where scope=?", (r["lease_scope"],)
                ).fetchone()
                # An active row without a recorded worker is unknown ownership.
                # Inactive rows with cleared identity are normal completed calls.
                if not (lease and lease[0] != 0 and r.get("worker_pid") is None):
                    c.execute("delete from leases where scope=?", (r["lease_scope"],))
            # Only the diagnostic lease has verified worker identities above.
            # Preserve every other lease, even inactive or expired ones. Both
            # release stores must be empty before confirming local cleanup.
            # Ordinary acquire/create share the ledger lock, in this order.
            try:
                historical_pending = historical_ownership(
                    self.lc.settings["state_directory"]
                )["pending"]
            except Refused:
                historical_pending = True
            pending = (
                c.execute("select count(*) from leases").fetchone()[0]
                or historical_pending
            )
            if pending:
                r.update(state="CLEANUP_REQUIRED", cleanup="LOCAL_PENDING")
            else:
                r.update(state="COMPLETE", cleanup="CONFIRMED")
            self.ledger._write(c, r)
        return self.ledger.snapshot(b)


class DiagnosticLifecycle:
    def __init__(self, lifecycle, binding, identity, ledger=None):
        self.lc = lifecycle
        self.ledger = ledger or ExperimentLedger(lifecycle.root)
        self.binding, self.identity = binding, identity
        self.dispatch = ExperimentDispatch(self.ledger, binding, identity)
        self.lc.backend.experiment = self.dispatch
        self.lc.provider.experiment_deadline = binding["deadline"]
        self.lc.provider.experiment_cleanup = False

    def check(self):
        require_reconciled(self.lc.settings["state_directory"])
        r = self.ledger.check(self.binding, self.identity)
        if not alive(r["owner_pid"], r["owner_process"]):
            raise Refused("experiment_caller_lost")
        if (
            r["supervisor_heartbeat"] is None
            or self.ledger.now() - r["supervisor_heartbeat"] > 30
            or not alive(r["supervisor_pid"], r["supervisor_process"])
        ):
            raise Refused("experiment_supervisor_missing")
        return r

    def allocate(self, hourly_ceiling):
        r = self.check()
        # Independent janitor plus experiment supervisor must already be running.
        self.lc.provider.ensure_guard()
        with self.lc.lock():
            state = self.lc.state()
            if state.get("phase") != "OFFLINE" or any(
                state.get(k) for k in ("pod_id", "pod_name", "allocation_uncertain")
            ):
                raise Refused("experiment_existing_allocation")
            with database(self.lc.root) as c:
                if c.execute("select count(*) from leases").fetchone()[0]:
                    raise Refused("experiment_existing_leases")
        require_reconciled(self.lc.settings["state_directory"], confirmed=True)
        # Preflight is followed by one fresh managed-ownership read. Nothing is adopted
        # for inference, including an allocation left by another release.
        if any(
            str(p.get("name", "")).startswith(self.lc.managed_prefixes)
            for p in self.lc.provider.pods()
        ):
            raise Refused("experiment_existing_allocation")
        info = self.lc.provider.preflight()
        if not info["available"] or not 0 < info["hourly_usd"] <= min(
            hourly_ceiling, 3
        ):
            raise Refused("experiment_quote")
        name = self.lc.pod_prefix + "experiment-" + self.binding["experiment_id"]
        with self.ledger.transaction() as c:
            r = self.ledger._bound(c, self.binding, self.identity)
            self.ledger._admit(r)
            if r["allocation_attempts"]:
                raise Refused("experiment_allocation_limit")
            r.update(
                allocation_attempts=1,
                allocation="RESERVED",
                allocation_name=name,
                allocation_pid=os.getpid(),
                allocation_process=process_identity(os.getpid()),
                allocation_inflight=True,
            )
            self.ledger._write(c, r)
        with self.lc.lock():
            state = self.lc.state()
            self.lc.save(
                state,
                phase="POD_ALLOCATED",
                pod_name=name,
                pod_id=None,
                allocation_uncertain=True,
                started_at=self.ledger.now(),
                hourly_usd=info["hourly_usd"],
                manual_stop=True,
            )
        try:
            pod = self.lc.provider.create(name)
            if (
                not pod
                or type(pod.get("id")) is not str
                or not re.fullmatch("[A-Za-z0-9_-]{1,80}", pod["id"])
            ):
                raise Refused("experiment_allocation_unknown")
        except BaseException:
            with self.ledger.transaction() as c:
                r = self.ledger._bound(c, self.binding)
                r.update(allocation="UNCERTAIN", allocation_inflight=False)
                self.ledger._write(c, r)
            self.ledger.stop(self.binding, "ALLOCATION_FAILED")
            raise
        with self.ledger.transaction() as c:
            r = self.ledger._bound(c, self.binding)
            r.update(
                allocation="OWNED", allocation_id=pod["id"], allocation_inflight=False
            )
            self.ledger._write(c, r)
        with self.lc.lock():
            state = self.lc.state()
            self.lc.save(
                state,
                pod_id=pod["id"],
                allocation_id=pod["id"],
                allocation_uncertain=False,
            )
        self.check()  # Cancellation/deadline during create never authorizes readiness.

    def ready(self):
        r = self.check()
        if r["allocation"] != "OWNED" or r["ready"]:
            raise Refused("experiment_readiness_state")
        pod = r["allocation_id"]
        launched = False
        # Only cached startup. No runtime/model preparation, downloads or warmup.
        while True:
            self.check()
            try:
                host, port = self.lc.provider.ssh_info(pod)
                if not launched:
                    script = (
                        BASE / "runtime/bootstrap-private-lead-vllm.sh"
                    ).read_bytes()
                    self.lc.provider.ssh(
                        pod,
                        host,
                        port,
                        "bash -s",
                        script,
                        timeout=self.dispatch.timeout(60),
                    )
                    launched = True
                self.lc.provider.server_alive(pod, host, port)
                self.lc.provider.tunnel(pod, host, port)
                self.lc.backend.health_check(smoke=False)
                break
            except Refused as error:
                if str(error).startswith("experiment_"):
                    raise
                self.lc.sleep(min(5, self.dispatch.timeout(5)))
        with self.lc.lock():
            state = self.lc.state()
            self.lc.save(state, host=host, port=port)
        # Outside polling: exactly one smoke. Failure terminates the experiment.
        try:
            self.lc.backend.health_check(smoke=True)
        except BaseException:
            self.ledger.stop(self.binding, "READINESS_FAILED")
            raise
        with self.ledger.transaction() as c:
            r = self.ledger._bound(c, self.binding)
            self.ledger._admit(r)
            r["ready"] = True
            self.ledger._write(c, r)
        with self.lc.lock():
            state = self.lc.state()
            self.lc.save(state, phase="READY", ready_at=self.ledger.now())

    def propose(self, scope, request):
        r = self.check()
        if not r["ready"] or r["allocation"] != "OWNED":
            raise Refused("experiment_not_ready")
        with self.ledger.transaction() as c:
            r = self.ledger._bound(c, self.binding)
            self.ledger._admit(r)
            if r["lease_scope"] not in (None, scope):
                raise Refused("experiment_scope")
            r.update(
                lease_scope=scope,
                worker_pid=os.getpid(),
                worker_process=process_identity(os.getpid()),
            )
            self.ledger._write(c, r)
            # Experiments serialize proposals; crash leaves a closing-owned lease.
            if c.execute("select count(*) from leases where active>0").fetchone()[0]:
                raise Refused("experiment_request_active")
            c.execute(
                "insert into leases values (?,?,1,0) on conflict(scope) do update set active=1,expires=excluded.expires",
                (scope, self.binding["deadline"]),
            )
        try:
            return self.lc.backend.propose(request)
        finally:
            with self.ledger.transaction() as c:
                r = self.ledger._bound(c, self.binding)
                r.update(worker_pid=None, worker_process=None)
                self.ledger._write(c, r)
                # Clear worker ownership and deactivate its lease atomically.
                # A crash must not leave an active row with no worker identity.
                c.execute("update leases set active=0 where scope=?", (scope,))
