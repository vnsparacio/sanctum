"""Permanent retirement counterexamples. Synthetic providers/stores only."""

import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE / "src"), str(BASE), str(BASE / "tests")]
import worker
from authority import authorize
from backends import Private80BBackend
from common import Refused, canonical, database
from experiment import LIMITS, ExperimentLedger, process_identity
from lifecycle import Private80BLifecycle
from retirement import historical_ownership, require_reconciled
from runpod import Runpod
from test_runtime import FakeBackend, FakeProvider, state


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.s = json.loads((BASE / "SETTINGS.json").read_text())
        self.s["state_directory"] = str(self.root)
        self.p = FakeProvider()
        self.backend = FakeBackend()
        self.lc = Private80BLifecycle(
            self.s, self.p, self.backend, lambda: 1000, lambda _: None
        )

    def tearDown(self):
        self.tmp.cleanup()

    def refused(self, operation):
        with self.assertRaisesRegex(Refused, "private_80b_retired"):
            operation()
        self.assertEqual(self.p.created, 0)
        self.assertEqual(self.backend.calls, [])

    def binding(self):
        return {
            "experiment_id": "a" * 32,
            "source_id": "b" * 64,
            "install_id": "c" * 64,
            "deadline": 1900,
        }

    def test_default_legacy_and_explicit_true_cannot_create_lease_or_inference(self):
        for enabled in (None, False, True):
            if enabled is None:
                self.s["gpu"].pop("enabled", None)
            else:
                self.s["gpu"]["enabled"] = enabled
            for op in (
                lambda: self.lc.acquire("x"),
                lambda: self.lc.infer("x", {}),
                lambda: self.lc.propose("x", {}),
            ):
                self.refused(op)
        self.assertFalse((self.root / "control.sqlite").exists())

    def test_readiness_resume_and_locked_readiness_refuse_before_io(self):
        for op in (
            lambda: self.lc.ensure_ready("x", explicit=True),
            self.lc.resume,
            lambda: self.lc.ready_locked({}, "x"),
        ):
            self.refused(op)

    def test_config_disguise_cannot_enable_retired_lifecycle(self):
        self.s["gpu"].update(enabled=True, logical_profile="PRIVATE_LEAD")
        self.refused(lambda: self.lc.acquire("x"))

    def test_signed_inference_and_resume_refuse_without_nonce_or_lease(self):
        key = b"synthetic-key"
        (self.root / "authority.key").write_bytes(key)
        (self.root / "authority.key").chmod(0o600)
        for enabled in (None, False, True):
            self.s["gpu"]["enabled"] = enabled
            for operation in ("infer", "resume", "private_lead_propose"):
                for approval in ("exact_disclosure", "session_private_prompt"):
                    b = {
                        "operation": operation,
                        "tier": "PRIVATE_80B",
                        "packet": {"prompt": "synthetic"},
                        "state": state(),
                        "scope": "a" * 32,
                        "approval": approval,
                        "strong": False,
                        "nonce": "b" * 64,
                        "expires": 1100,
                        "spec_sha256": "test",
                    }
                    raw = canonical(b)
                    envelope = {
                        "body": raw,
                        "mac": hmac.new(key, raw.encode(), hashlib.sha256).hexdigest(),
                    }
                    self.refused(
                        lambda: authorize(
                            envelope, self.s, now=lambda: 1000, settings_hash="test"
                        )
                    )
        self.assertFalse((self.root / "control.sqlite").exists())

    def test_worker_rejects_even_injected_lifecycle_before_packet_expansion(self):
        for op in ("infer", "resume", "private_lead_propose"):
            with patch.object(
                worker,
                "expand",
                side_effect=AssertionError("expanded retired disclosure"),
            ):
                self.refused(
                    lambda: worker.execute(
                        {
                            "operation": op,
                            "tier": "PRIVATE_80B",
                            "scope": "a" * 32,
                            "packet": {},
                        },
                        self.s,
                        lifecycle=Mock(),
                    )
                )

    def test_backend_cannot_complete_or_smoke_even_with_legacy_enable(self):
        self.s["gpu"]["enabled"] = True
        send = Mock(side_effect=AssertionError("model HTTP"))
        b = Private80BBackend(self.s, send)
        for op in (
            lambda: b.infer({}),
            lambda: b.health_check(smoke=True),
            b.health_check,
        ):
            self.refused(op)
        send.assert_not_called()

    def test_provider_cannot_create_bootstrap_or_run_ssh_for_retired_release(self):
        for enabled in (None, False, True):
            self.s["gpu"]["enabled"] = enabled
            p = Runpod(self.s)
            with patch.object(p, "call", side_effect=AssertionError("provider IO")):
                for op in (
                    lambda: p.create("vinceai-qwen80b-new"),
                    lambda: p.bootstrap_server("id", "host", 22),
                    lambda: p.ssh("id", "host", 22, "true"),
                ):
                    self.refused(op)

    def test_low_level_provider_create_cannot_bypass_retirement(self):
        p = Runpod(self.s)
        for verb in ("create", "start", "resume"):
            self.refused(lambda: p.call("pod", verb, "x"))

    def test_lead_provider_cannot_allocate_an_80b_named_resource(self):
        p = Runpod(self.s, self.s["private_lead"])
        with patch.object(p, "call", side_effect=AssertionError("provider IO")):
            self.refused(lambda: p.create("vinceai-qwen80b-new"))

    def test_legacy_bootstrap_is_inert(self):
        r = subprocess.run(
            ["bash", str(BASE / "runtime/bootstrap-vllm.sh")],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stderr.strip(), "private_80b_retired")

    def test_zero_ownership_records_retired_after_provider_absence(self):
        self.lc.sweep()
        self.assertEqual(self.lc.status()["phase"], "RETIRED")
        self.assertTrue(require_reconciled(self.root, confirmed=True)["confirmed"])
        self.assertFalse((self.root / "control.sqlite").exists())

    def test_status_stop_and_sweep_remain_available(self):
        self.assertFalse(self.lc.status()["available"])
        for op in ("status", "stop", "sweep"):
            result = worker.execute(
                {
                    "operation": op,
                    "tier": "PRIVATE_80B",
                    "scope": "a" * 32,
                    "packet": {},
                },
                self.s,
                lifecycle=self.lc,
            )
            self.assertEqual(result["status"], "OK")
            self.assertEqual(result["gpu"]["inference"], "RETIRED")

    def test_exact_existing_allocation_deleted_and_storage_evidence_preserved(self):
        descriptor = (BASE / "runtime/private-releases.json").read_bytes()
        sentinel = self.root / "persistent-cache-fixture"
        sentinel.write_text("synthetic")
        self.p.rows = [{"id": "owned", "name": "vinceai-qwen80b-historical"}]
        self.lc.save(
            self.lc.state(),
            phase="READY",
            pod_id="owned",
            pod_name=self.p.rows[0]["name"],
        )
        self.lc.sweep(immediate=True, manual=True)
        self.assertEqual(self.p.deleted, ["owned"])
        self.assertEqual(self.p.created, 0)
        self.assertEqual(sentinel.read_text(), "synthetic")
        self.assertEqual(
            descriptor, (BASE / "runtime/private-releases.json").read_bytes()
        )
        self.assertEqual(self.lc.status()["phase"], "RETIRED")

    def test_unknown_allocation_intent_never_retires(self):
        self.lc.save(
            self.lc.state(),
            phase="DEGRADED",
            allocation_uncertain=True,
            pod_name="vinceai-qwen80b-maybe",
        )
        with self.assertRaises(Refused):
            self.lc.sweep()
        self.assertEqual(self.lc.status()["phase"], "RECONCILIATION_REQUIRED")
        self.assertTrue(self.lc.state()["allocation_uncertain"])

    def test_unknown_provider_absence_never_retires(self):
        self.p.pods = Mock(side_effect=Refused("provider_unknown"))
        with self.assertRaises(Refused):
            self.lc.sweep()
        self.assertFalse(historical_ownership(self.root)["confirmed"])

    def test_discovered_historical_lease_reopens_cleanup_never_expires_away(self):
        self.lc.sweep()
        with database(self.root) as c:
            c.execute("insert into leases values (?,?,1,0)", ("old", 1))
        self.assertEqual(self.lc.status()["phase"], "RECONCILIATION_REQUIRED")
        self.lc.sweep(manual=True)
        self.assertEqual(self.lc.status()["leases"], 1)
        self.refused(lambda: self.lc.infer("new", {}))
        with self.assertRaises(Refused):
            require_reconciled(self.root)

    def test_discovered_provider_record_is_not_adopted_for_inference(self):
        self.lc.sweep()
        self.p.rows = [{"id": "unknown", "name": "vinceai-qwen80b-unknown"}]
        with self.assertRaises(Refused):
            self.lc.sweep()
        self.assertEqual(self.p.created, 0)
        self.assertEqual(self.p.deleted, [])
        self.assertFalse(historical_ownership(self.root)["confirmed"])

    def test_retired_empty_storage_is_not_created_by_lead_experiment(self):
        self.lc.sweep()
        ledger = ExperimentLedger(self.root / "private-lead", lambda: 1000)
        ledger.create(
            self.binding(),
            owner_pid=os.getpid(),
            owner_process=process_identity(os.getpid()),
            ordinary_root=self.root,
        )
        self.assertFalse((self.root / "control.sqlite").exists())
        self.assertEqual(ledger.snapshot(self.binding())["limits"], LIMITS)

    def test_later_historical_ownership_blocks_dispatch_before_reservation(self):
        self.lc.sweep()
        ledger = ExperimentLedger(self.root / "private-lead", lambda: 1000)
        ledger.create(
            self.binding(),
            owner_pid=os.getpid(),
            owner_process=process_identity(os.getpid()),
            ordinary_root=self.root,
        )
        self.lc.save(
            self.lc.state(),
            pod_name="vinceai-qwen80b-discovered",
            allocation_uncertain=True,
        )
        with self.assertRaises(Refused):
            ledger.reserve(self.binding(), self.binding(), "proposal", 1024)
        self.assertEqual(ledger.snapshot(self.binding())["counts"]["reserved"], 0)

    def test_recorded_allocation_id_without_pod_id_is_reconciled(self):
        self.p.rows = [{"id": "owned", "name": "vinceai-qwen80b-old"}]
        self.lc.save(self.lc.state(), allocation_id="owned")
        self.assertTrue(historical_ownership(self.root)["pending"])
        self.lc.sweep()
        self.assertEqual(self.p.deleted, ["owned"])
        self.assertEqual(self.lc.status()["phase"], "RETIRED")

    def test_wrong_namespace_record_never_deletes_lead_resource(self):
        self.p.rows = [{"id": "wrong", "name": "sanctum-private-lead-current"}]
        self.lc.save(self.lc.state(), pod_id="wrong")
        with self.assertRaisesRegex(Refused, "retired_resource_identity"):
            self.lc.sweep()
        self.assertEqual(self.p.deleted, [])
        self.assertFalse(historical_ownership(self.root)["confirmed"])

    def test_unknown_identity_cannot_be_a_retirement_proof(self):
        self.lc.save(self.lc.state(), phase="RETIRED", retired_confirmed_at=-1)
        with self.assertRaises(Refused):
            require_reconciled(self.root, confirmed=True)

    def test_malformed_historical_database_fails_closed(self):
        (self.root / "control.sqlite").write_bytes(b"not sqlite")
        with self.assertRaisesRegex(Refused, "retired_ownership_unknown"):
            historical_ownership(self.root)


if __name__ == "__main__":
    unittest.main()
