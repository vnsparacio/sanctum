"""Mac-owned, cross-process single-flight lifecycle and persistent session leases."""

import contextlib
import fcntl
import os
import threading
import time
import uuid
from pathlib import Path

from backends import Private80BBackend, PrivateLeadBackend
from common import Refused, atomic, canonical, database, private_dir, strict_json
from runpod import Runpod


class Private80BLifecycle:
    def __init__(
        self, settings, provider=None, backend=None, now=time.time, sleep=time.sleep
    ):
        self.settings = settings
        self.cfg = settings["gpu"]
        self.root = private_dir(settings["state_directory"])
        self.provider = provider or Runpod(settings)
        self.backend = backend or Private80BBackend(settings)
        self.pod_prefix = "vinceai-qwen80b-"
        self.managed_prefixes = ("vinceai-qwen80b-", "sanctum-private-lead-")
        self.now, self.sleep = now, sleep

    @contextlib.contextmanager
    def lock(self, blocking=True):
        fd = os.open(
            self.root / "lifecycle.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            yield
        finally:
            os.close(fd)

    def state(self):
        p = self.root / "gpu.json"
        if p.is_symlink():
            raise Refused("unsafe_gpu_state")
        return (
            strict_json(p.read_text())
            if p.exists()
            else {"phase": "OFFLINE", "pod_id": None, "manual_stop": False}
        )

    def save(self, state, **changes):
        state.update(changes)
        state["updated_at"] = self.now()
        atomic(self.root / "gpu.json", canonical(state).encode())

    def check_enabled(self):
        if not isinstance(self, PrivateLeadLifecycle):
            raise Refused("private_80b_retired")

    def acquire(self, scope):
        self.check_enabled()
        from experiment import ExperimentLedger

        ledger = ExperimentLedger(
            Path(self.settings["state_directory"]) / "private-lead"
        )
        # Serialize admission with experiment creation and terminal reconciliation.
        # Always lock PRIVATE_LEAD first, then PRIVATE_80B; never hold this lock
        # across readiness, provider calls or inference.
        with ledger.transaction() as admission:
            if ledger._current(admission):
                raise Refused("experiment_ownership_required")
            self.check_enabled()
            with self.lease_store(ledger, admission) as c:
                row = c.execute(
                    "select closing from leases where scope=?", (scope,)
                ).fetchone()
                if row and row[0]:
                    raise Refused("session_closing")
                c.execute(
                    "insert into leases(scope,expires,active,closing) values(?,?,1,0) on conflict(scope) do update set expires=excluded.expires,active=active+1",
                    (scope, self.now() + 90),
                )

    @contextlib.contextmanager
    def lease_store(self, ledger, admission):
        """Use only under lead admission: lead first, then the ordinary store."""
        with (
            contextlib.nullcontext(admission)
            if self.root == ledger.root
            else database(self.root)
        ) as c:
            if c is not admission:
                c.execute("begin immediate")
            yield c

    def heartbeat(self, scope):
        with database(self.root) as c:
            c.execute(
                "update leases set expires=? where scope=? and closing=0",
                (self.now() + 90, scope),
            )

    def check_lease(self, scope):
        if (self.root / "manual-stop").exists():
            raise Refused("manual_stop")
        with database(self.root) as c:
            row = c.execute(
                "select expires,closing from leases where scope=?", (scope,)
            ).fetchone()
        if not row or row[0] <= self.now() or row[1]:
            raise Refused("lease_cancelled")

    def release(self, scope, close=False):
        final_close = close
        with database(self.root) as c:
            c.execute("begin immediate")
            row = c.execute(
                "select closing from leases where scope=?", (scope,)
            ).fetchone()
            final_close = final_close or bool(row and row[0])
            if close:
                c.execute("update leases set closing=1 where scope=?", (scope,))
            else:
                c.execute(
                    "update leases set active=max(active-1,0),expires=? where scope=?",
                    (self.now() + self.cfg["session_idle_seconds"], scope),
                )
            c.execute(
                "delete from leases where scope=? and active=0 and closing=1", (scope,)
            )
        if final_close:
            self.sweep(immediate=True)

    def resume(self):
        self.check_enabled()
        with self.lock():
            (self.root / "manual-stop").unlink(missing_ok=True)
            s = self.state()
            self.save(s, manual_stop=False)

    def status(self):
        s = self.state()
        if not isinstance(self, PrivateLeadLifecycle):
            from retirement import historical_ownership

            facts = historical_ownership(self.root)
            return {
                "phase": "RETIRED" if facts["confirmed"] else "RECONCILIATION_REQUIRED",
                "release": "PRIVATE_80B",
                "inference": "RETIRED",
                "available": False,
                **facts,
            }
        with database(self.root) as c:
            leases = c.execute(
                "select count(*),coalesce(sum(active),0) from leases where expires>?",
                (self.now(),),
            ).fetchone()
        return {
            k: s.get(k)
            for k in [
                "phase",
                "pod_id",
                "allocation_id",
                "started_at",
                "ready_at",
                "first_inference_at",
                "last_inference_at",
                "delete_requested_at",
                "absent_confirmed_at",
                "hourly_usd",
                "manual_stop",
                "error",
            ]
        } | {
            "leases": leases[0],
            "active_requests": leases[1],
            "estimated_compute_usd": (
                max(0, self.now() - s.get("started_at", self.now()))
                / 3600
                * s.get("hourly_usd", 0)
                if s.get("pod_id")
                else 0
            ),
        }

    def reconcile(self, s):
        pods = self.provider.pods()
        candidates = [
            p
            for p in pods
            if p.get("id") == s.get("pod_id")
            or (s.get("pod_name") and p.get("name") == s["pod_name"])
        ]
        if not isinstance(self, PrivateLeadLifecycle) and any(
            not str(p.get("name", "")).startswith("vinceai-qwen80b-")
            for p in candidates
        ):
            raise Refused("retired_resource_identity")
        managed = [
            p for p in pods if str(p.get("name", "")).startswith(self.managed_prefixes)
        ]
        if len(candidates) > 1 or any(p not in candidates for p in managed):
            raise Refused("untracked_or_duplicate_pod")
        if candidates:
            p = candidates[0]
            self.save(s, pod_id=p["id"], allocation_uncertain=False)
        elif s.get("allocation_uncertain"):
            raise Refused("allocation_unresolved")
        elif s.get("pod_id"):
            self.save(s, pod_id=None, phase="OFFLINE", manual_stop=True)
        return candidates

    def ensure_ready(self, scope, explicit=False):
        self.check_enabled()
        from experiment import ExperimentLedger

        diagnostic_root = Path(self.settings["state_directory"]) / "private-lead"
        if (diagnostic_root / "control.sqlite").exists() and ExperimentLedger(
            diagnostic_root
        ).current():
            raise Refused("experiment_ownership_required")
        with self.lock():
            self.check_lease(scope)
            s = self.state()
            self.reconcile(s)
            if s.get("manual_stop") or (not self.cfg["auto_start"] and not explicit):
                raise Refused("autostart_disabled")
            self.provider.ensure_guard()
            if s.get("pod_id"):
                if (
                    self.now() - s.get("started_at", 0)
                    >= self.cfg["max_runtime_seconds"]
                ):
                    raise Refused("gpu_runtime_limit")
                self.ready_locked(s, scope)
                return
            deadline = self.now() + self.cfg["capacity_wait_seconds"]
            self.save(s, phase="CAPACITY_WAIT", error=None)
            while self.now() < deadline:
                self.check_lease(scope)
                self.reconcile(s)
                info = self.provider.preflight()
                if not info["available"]:
                    self.sleep(10)
                    continue
                self.check_lease(scope)
                # Persist intent before mutation. Only an exact, definitive capacity
                # rejection permits retry; lost/ambiguous responses remain adopt-only.
                name = self.pod_prefix + "stage-" + uuid.uuid4().hex
                self.save(
                    s,
                    pod_name=name,
                    allocation_uncertain=True,
                    allocation_id=None,
                    started_at=self.now(),
                    ready_at=None,
                    first_inference_at=None,
                    last_inference_at=None,
                    delete_requested_at=None,
                    absent_confirmed_at=None,
                    hourly_usd=info["hourly_usd"],
                )
                try:
                    pod = self.provider.create(name)
                except Exception as e:
                    if type(e) is Refused and str(e) == "gpu_capacity_unavailable":
                        self.save(
                            s,
                            allocation_uncertain=False,
                            phase="CAPACITY_WAIT",
                            error="gpu_capacity_unavailable",
                        )
                        self.reconcile(s)
                        if not s.get("pod_id"):
                            self.save(s, pod_name=None)
                            self.sleep(10)
                            continue
                    else:
                        self.save(s, phase="DEGRADED", error="allocation_unresolved")
                        self.reconcile(s)
                        if not s.get("pod_id"):
                            raise Refused("allocation_unresolved")
                else:
                    if not pod or not pod.get("id"):
                        raise Refused("allocation_unresolved")
                    self.save(s, pod_id=pod["id"])
                self.save(
                    s,
                    phase="POD_ALLOCATED",
                    allocation_id=s.get("pod_id"),
                    allocation_uncertain=False,
                )
                self.ready_locked(s, scope)
                return
            raise Refused("capacity_timeout")

    def ready_locked(self, s, scope):
        self.check_enabled()
        try:
            deadline = self.now() + self.cfg["readiness_seconds"]
            while self.now() < deadline:
                self.check_lease(scope)
                try:
                    host, port = self.provider.ssh_info(s["pod_id"])
                    self.provider.ssh(s["pod_id"], host, port, "true")
                    break
                except Exception:
                    self.sleep(5)
            else:
                raise Refused("ssh_timeout")
            self.save(s, host=host, port=port, idle_since=None)
            try:
                self.provider.server_alive(s["pod_id"], host, port)
                self.provider.tunnel(s["pod_id"], host, port)
                self.backend.health_check(smoke=True)
                self.save(s, phase="READY", ready_at=self.now(), error=None)
                return
            except Exception:
                self.check_lease(scope)
            # This is idempotent and repairs interrupted installs at their final path.
            self.save(s, phase="SERVER_STARTING")
            self.provider.bootstrap_server(s["pod_id"], host, port)
            self.check_lease(scope)
            self.provider.tunnel(s["pod_id"], host, port)
            while self.now() < deadline:
                self.check_lease(scope)
                try:
                    self.provider.server_alive(s["pod_id"], host, port)
                    self.backend.health_check(smoke=True)
                    self.save(s, phase="READY", ready_at=self.now(), error=None)
                    return
                except Exception:
                    self.sleep(5)
            raise Refused("model_readiness_timeout")
        except Exception:
            self.save(s, phase="DEGRADED", error="readiness_failed")
            # Do not kill another session's active inference on a transient check.
            with database(self.root) as c:
                others = c.execute(
                    "select coalesce(sum(active),0) from leases where scope!=? and expires>?",
                    (scope, self.now()),
                ).fetchone()[0]
            if not others:
                self.terminate_locked(s)
            raise

    def terminate_locked(self, s):
        self.reconcile(s)
        if not s.get("pod_id"):
            self.save(s, phase="OFFLINE")
            return
        self.save(s, phase="STOPPING", delete_requested_at=self.now())
        self.provider.delete(s["pod_id"])
        for _ in range(6):
            if all(p.get("id") != s["pod_id"] for p in self.provider.pods()):
                self.provider.close_tunnel(s)
                self.save(
                    s,
                    phase="OFFLINE",
                    pod_id=None,
                    pod_name=None,
                    allocation_uncertain=False,
                    idle_since=None,
                    absent_confirmed_at=self.now(),
                )
                return
            self.sleep(2)
        self.save(s, phase="DEGRADED", error="termination_unconfirmed")
        raise Refused("termination_unconfirmed")

    def sweep(self, immediate=False, manual=False):
        if not isinstance(self, PrivateLeadLifecycle):
            return self.retire(manual=manual)
        from experiment import ExperimentLedger

        ledger = ExperimentLedger(
            Path(self.settings["state_directory"]) / "private-lead", self.now
        )
        if manual:
            # A stop request must survive a concurrent bootstrap holding the lock.
            atomic(self.root / "manual-stop", b"stop\n")
        with ledger.transaction() as admission:
            record = ledger._current(admission)
            if manual and not record:
                with self.lease_store(ledger, admission) as c:
                    c.execute("update leases set closing=1")
        if record:
            self.sweep_experiment(ledger, record, manual)
            return
        try:
            with self.lock(blocking=False):
                s = self.state()
                # Recheck after taking the lifecycle lock. Experiment creation and
                # all ordinary pruning share admission, including manual/runtime
                # cleanup. Never infer an unknown worker's exit from lease expiry.
                with ledger.transaction() as admission:
                    record = ledger._current(admission)
                    if not record:
                        with self.lease_store(ledger, admission) as c:
                            c.execute(
                                "delete from leases where expires<=? or (closing=1 and active=0)",
                                (self.now(),),
                            )
                            if manual or (self.root / "manual-stop").exists():
                                self.save(s, manual_stop=True)
                                immediate = True
                            if (
                                s.get("pod_id")
                                and self.now() - s.get("started_at", self.now())
                                >= self.cfg["max_runtime_seconds"]
                            ):
                                self.save(
                                    s, manual_stop=True, error="gpu_runtime_limit"
                                )
                                atomic(self.root / "manual-stop", b"runtime_limit\n")
                                c.execute("update leases set closing=1")
                                c.execute("delete from leases where active=0")
                                immediate = True
                            count = c.execute("select count(*) from leases").fetchone()[
                                0
                            ]
                # Provider work is outside admission. If ownership appeared while
                # acquiring the lock, delegate only after releasing both locks.
                if not record:
                    if count:
                        return
                    if s.get("allocation_uncertain"):
                        self.reconcile(s)
                        if s.get("pod_id"):
                            self.save(s, allocation_uncertain=False)
                    if not s.get("pod_id"):
                        self.save(s, phase="OFFLINE", pod_name=None, idle_since=None)
                        return
                    if not s.get("idle_since"):
                        self.save(s, phase="IDLE_GRACE", idle_since=self.now())
                    if (
                        immediate
                        or manual
                        or self.now() - s["idle_since"]
                        >= self.cfg["idle_grace_seconds"]
                    ):
                        self.terminate_locked(s)
        except BlockingIOError:
            # Startup owns the transition; closing lease is visible to that owner.
            return
        if record:
            self.sweep_experiment(ledger, record, manual)

    def retire(self, manual=False):
        """Reconcile only recorded historical compute; never prune unknown leases."""
        from retirement import historical_ownership

        if manual:
            atomic(self.root / "manual-stop", b"retired\n")
        try:
            with self.lock(blocking=False):
                s = self.state()
                try:
                    # The retired namespace is cleanup-only and ignores lead pods.
                    self.managed_prefixes = ("vinceai-qwen80b-",)
                    if (
                        s.get("allocation_id")
                        and not s.get("pod_id")
                        and not s.get("absent_confirmed_at")
                    ):
                        self.save(s, pod_id=s["allocation_id"])
                    self.terminate_locked(s)
                    facts = historical_ownership(self.root)
                    if facts["leases"] or facts["active_requests"]:
                        self.save(
                            s,
                            phase="RECONCILIATION_REQUIRED",
                            manual_stop=True,
                            error="retired_local_ownership_pending",
                            retired_confirmed_at=None,
                        )
                        return
                    self.save(
                        s,
                        phase="RETIRED",
                        pod_id=None,
                        pod_name=None,
                        allocation_uncertain=False,
                        manual_stop=True,
                        error=None,
                        absent_confirmed_at=self.now(),
                        retired_confirmed_at=self.now(),
                    )
                except Exception:
                    self.save(
                        s,
                        phase="RECONCILIATION_REQUIRED",
                        manual_stop=True,
                        error="retired_ownership_unknown",
                        retired_confirmed_at=None,
                    )
                    raise
        except BlockingIOError:
            return

    def sweep_experiment(self, ledger, record, manual):
        # The other release preserves its rows; only the lead cleanup owner may
        # reconcile the diagnostic allocation, with its own provider/configuration.
        if self.root != ledger.root:
            return
        from experiment_lifecycle import ExperimentSupervisor, binding_of

        if manual:
            ledger.stop(binding_of(record), "CANCELLED")
        ExperimentSupervisor(
            ledger,
            self,
            publish_heartbeat=getattr(self, "experiment_supervisor", False),
        ).tick()

    def infer(self, scope, packet):
        self.acquire(scope)
        stop = threading.Event()

        def pulse():
            while not stop.wait(10):
                try:
                    self.heartbeat(scope)
                except Exception:
                    return

        t = threading.Thread(target=pulse, daemon=True)
        t.start()
        try:
            self.ensure_ready(scope)
            self.check_lease(scope)
            return self.backend.infer(packet)
        finally:
            stop.set()
            t.join(timeout=1)
            self.release(scope)
            self.sweep()

    def propose(self, scope, request):
        """Run one bounded, data-only structured proposal under the normal lease."""
        self.acquire(scope)
        stop = threading.Event()

        def pulse():
            while not stop.wait(10):
                try:
                    self.heartbeat(scope)
                except Exception:
                    return

        t = threading.Thread(target=pulse, daemon=True)
        t.start()
        try:
            self.ensure_ready(
                scope, explicit=self.cfg.get("logical_profile") == "PRIVATE_LEAD"
            )
            self.check_lease(scope)
            with self.lock():
                state = self.state()
                self.save(
                    state,
                    first_inference_at=state.get("first_inference_at") or self.now(),
                    last_inference_at=self.now(),
                )
            result = self.backend.propose(request)
            with self.lock():
                state = self.state()
                self.save(state, last_inference_at=self.now())
            return result
        finally:
            stop.set()
            t.join(timeout=1)
            self.release(scope)
            self.sweep()


class PrivateLeadLifecycle(Private80BLifecycle):
    """Separately staged PRIVATE_LEAD ownership; it never selects itself for normal routing."""

    def __init__(
        self, settings, provider=None, backend=None, now=time.time, sleep=time.sleep
    ):
        cfg = settings.get("private_lead")
        if type(cfg) is not dict or cfg.get("logical_profile") != "PRIVATE_LEAD":
            raise Refused("private_lead_configuration")
        self.settings = settings
        self.cfg = cfg
        self.root = private_dir(Path(settings["state_directory"]) / "private-lead")
        self.provider = provider or Runpod(settings, cfg)
        self.backend = backend or PrivateLeadBackend(settings)
        self.pod_prefix = cfg["pod_prefix"]
        self.managed_prefixes = ("vinceai-qwen80b-", self.pod_prefix)
        self.now, self.sleep = now, sleep

    def ensure_ready(self, scope, explicit=False):
        from experiment import ExperimentLedger

        if ExperimentLedger(self.root).current():
            raise Refused("experiment_ownership_required")
        return super().ensure_ready(scope, explicit)
