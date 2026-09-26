"""Bounded owner warm-lease behavior with a synthetic lifecycle."""

import sys
import threading
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE / "src"), str(BASE)]

import manage
from common import Refused


class Clock:
    def __init__(self):
        self.value = 1000.0

    def now(self):
        return self.value

    def wait(self, seconds):
        self.value += seconds
        return False


class Lifecycle:
    def __init__(self, clock):
        self.clock = clock
        self.cfg = {
            "auto_start": False,
            "max_runtime_seconds": 900,
            "max_hourly_usd": 3,
        }
        self.phase = "OFFLINE"
        self.leases = 0
        self.active = 0
        self.started = None
        self.allocations = 0
        self.closed = 0
        self.fail_ready = False
        self.shared = False

    def status(self):
        return {
            "phase": self.phase,
            "leases": self.leases,
            "active_requests": self.active,
            "manual_stop": False,
            "started_at": self.started,
            "hourly_usd": 2 if self.started else None,
            "estimated_compute_usd": (
                (self.clock.now() - self.started) * 2 / 3600 if self.started else 0
            ),
        }

    def acquire(self, _scope):
        self.leases += 1
        self.active += 1

    def heartbeat(self, _scope):
        pass

    def ensure_ready(self, _scope, explicit=False):
        assert explicit
        if self.fail_ready:
            raise Refused("synthetic_readiness_failed")
        self.allocations += 1
        self.phase = "READY"
        self.started = self.clock.now()

    def check_lease(self, _scope):
        pass

    def release(self, _scope, close=False):
        if close:
            self.closed += 1
            self.leases -= 1
            if self.shared:
                self.leases += 1
                self.active += 1
            else:
                self.phase = "OFFLINE"
                self.started = None
        else:
            self.active -= 1


class HoldTests(unittest.TestCase):
    def test_two_bounded_allocations_release_every_lease(self):
        clock = Clock()
        lc = Lifecycle(clock)
        events = []
        result = manage.hold_private_lead(
            lc, 1700, 2, now=clock.now, wait=clock.wait, report=events.append
        )
        self.assertEqual(result["allocations"], 2)
        self.assertEqual(result["phase"], "OFFLINE")
        self.assertGreater(result["estimated_compute_usd"], 0)
        self.assertLess(result["estimated_compute_usd"], 2)
        self.assertEqual((lc.leases, lc.active, lc.closed), (0, 0, 2))
        self.assertEqual(
            [event["event"] for event in events],
            ["READY", "RELEASED", "READY", "RELEASED"],
        )

    def test_refuses_unfunded_or_busy_hold_before_allocation(self):
        clock = Clock()
        lc = Lifecycle(clock)
        with self.assertRaisesRegex(Refused, "hold_contract"):
            manage.hold_private_lead(lc, 4600, 1, now=clock.now, wait=clock.wait)
        self.assertEqual(lc.allocations, 0)
        lc.leases = 1
        with self.assertRaisesRegex(Refused, "hold_requires_idle_provider"):
            manage.hold_private_lead(lc, 1700, 2, now=clock.now, wait=clock.wait)
        self.assertEqual(lc.allocations, 0)

    def test_readiness_failure_closes_lease(self):
        clock = Clock()
        lc = Lifecycle(clock)
        lc.fail_ready = True
        with self.assertRaisesRegex(Refused, "synthetic_readiness_failed"):
            manage.hold_private_lead(lc, 1700, 2, now=clock.now, wait=clock.wait)
        self.assertEqual((lc.leases, lc.active, lc.closed), (0, 0, 1))

    def test_signal_releases_early_and_shared_task_remains_task_owned(self):
        clock = Clock()
        lc = Lifecycle(clock)
        stopped = threading.Event()

        def wait(seconds):
            clock.wait(seconds)
            if clock.now() >= 1050:
                stopped.set()

        result = manage.hold_private_lead(
            lc, 1700, 2, now=clock.now, wait=wait, stopped=stopped
        )
        self.assertEqual(
            (result["phase"], result["allocations"], lc.leases), ("OFFLINE", 1, 0)
        )

        clock = Clock()
        lc = Lifecycle(clock)
        lc.shared = True
        events = []
        result = manage.hold_private_lead(
            lc, 1700, 2, now=clock.now, wait=clock.wait, report=events.append
        )
        self.assertEqual(
            (result["phase"], result["allocations"], lc.leases), ("READY", 1, 1)
        )
        self.assertEqual(events[-1]["event"], "SHARED_WITH_WORK_MODE")


if __name__ == "__main__":
    unittest.main()
