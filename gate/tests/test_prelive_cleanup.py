"""Cleanup recovery contracts; synthetic stores/providers and harmless children only."""
import contextlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE/'src'), str(BASE/'tests')]
from common import Refused, database
from experiment import ExperimentLedger, process_identity
from experiment_lifecycle import DiagnosticLifecycle, ExperimentSupervisor, alive
from lifecycle import Private80BLifecycle, PrivateLeadLifecycle
from test_prelive import Fixture, Provider


class SweepCleanupTests(Fixture):
    def test_both_sweeps_preserve_unknown_rows_during_experiment(self):
        for cls in (Private80BLifecycle, PrivateLeadLifecycle):
            for manual in (False, True):
                with self.subTest(release=cls.__name__, manual=manual):
                    lc = cls(self.settings, provider=Provider(), now=self.now)
                    self.update(state='CLEANUP_REQUIRED', cleanup='REQUIRED')
                    with database(lc.root) as c:
                        c.execute('insert into leases values (?,?,1,0)', ('d'*32, 999))
                        c.execute('insert into leases values (?,?,0,1)', ('e'*32, 2000))
                    lc.sweep(manual=manual)
                    with database(lc.root) as c:
                        self.assertEqual(c.execute('select scope,expires,active,closing from leases order by scope').fetchall(),
                                         [('d'*32, 999, 1, 0), ('e'*32, 2000, 0, 1)])
                        c.execute('delete from leases')  # Explicit synthetic owner reconciliation.

    def test_80b_sweep_cannot_turn_local_pending_into_confirmed(self):
        provider = Provider(); provider.rows = [{'id':'synthetic-pod','name':'synthetic-name'}]
        lc = PrivateLeadLifecycle(self.settings, provider=provider, now=self.now)
        self.update(state='CLEANUP_REQUIRED', allocation='OWNED', allocation_id='synthetic-pod', allocation_name='synthetic-name')
        lc.save(lc.state(), phase='READY', pod_id='synthetic-pod', pod_name='synthetic-name')
        with database(self.root) as c: c.execute('insert into leases values (?,?,1,0)', ('d'*32, 999))
        supervisor = ExperimentSupervisor(self.ledger, lc)
        self.assertEqual(supervisor.tick()['cleanup'], 'LOCAL_PENDING')
        Private80BLifecycle(self.settings, provider=Provider(), now=self.now).sweep()
        result = supervisor.tick()
        self.assertEqual(result['cleanup'], 'LOCAL_PENDING')
        self.assertEqual(result['allocation'], 'ABSENT'); self.assertEqual(len(provider.deleted), 1)
        with database(self.root) as c:
            self.assertEqual(c.execute('select active from leases').fetchone(), (1,))
            c.execute('delete from leases')
        Private80BLifecycle(self.settings, provider=Provider(), now=self.now).sweep()
        self.assertEqual(supervisor.tick()['cleanup'], 'CONFIRMED')

    def test_sweep_rechecks_experiment_created_while_taking_lifecycle_lock(self):
        for cls in (Private80BLifecycle, PrivateLeadLifecycle):
            with self.subTest(release=cls.__name__):
                self.update(state='COMPLETE', cleanup='CONFIRMED')
                lc = cls(self.settings, provider=Provider(), now=self.now)
                original = lc.lock
                @contextlib.contextmanager
                def interleaved_lock(*args, **kwargs):
                    # Deterministic concurrent-create boundary, before ordinary pruning.
                    with original(*args, **kwargs):
                        binding={**self.binding,'experiment_id':('e' if cls is PrivateLeadLifecycle else 'f')*32}
                        self.ledger.create(binding, owner_pid=os.getpid(), owner_process=process_identity(os.getpid()), ordinary_root=self.root)
                        self.ledger.stop(binding, 'CANCELLED')
                        with database(lc.root) as c:
                            c.execute('insert into leases values (?,?,1,0)', ('d'*32, 999))
                        yield
                with patch.object(lc, 'lock', interleaved_lock): lc.sweep()
                with database(lc.root) as c:
                    self.assertEqual(c.execute('select active from leases').fetchone(), (1,))
                    c.execute('delete from leases')
                Private80BLifecycle(self.settings, provider=Provider(), now=self.now).sweep()
                PrivateLeadLifecycle(self.settings, provider=Provider(), now=self.now).sweep()

    def test_ordinary_idle_and_expiry_behavior_without_experiment(self):
        self.update(state='COMPLETE', cleanup='CONFIRMED')
        for cls in (PrivateLeadLifecycle,):
            with self.subTest(release=cls.__name__):
                lc = cls(self.settings, provider=Provider(), now=self.now)
                lc.acquire('d'*32); lc.release('d'*32)
                with database(lc.root) as c:
                    c.execute('insert into leases values (?,?,1,0)', ('e'*32, 999))
                lc.sweep()
                with database(lc.root) as c:
                    self.assertEqual(c.execute('select scope,active,closing from leases').fetchall(), [('d'*32, 0, 0)])

    def test_supervisor_runs_even_with_lifecycle_lock_held(self):
        lc = PrivateLeadLifecycle(self.settings, provider=Provider(), now=self.now)
        self.ledger.stop(self.binding, 'CANCELLED')
        with lc.lock(): lc.sweep()
        self.assertEqual(self.snapshot()['cleanup'], 'CONFIRMED')

    def test_no_admission_transaction_is_held_across_provider_calls(self):
        self.update(state='COMPLETE', cleanup='CONFIRMED')
        for cls in (Private80BLifecycle, PrivateLeadLifecycle):
            lc = cls(self.settings, provider=Provider(), now=self.now)
            lc.save(lc.state(), phase='READY', pod_id='synthetic-pod', pod_name='synthetic-name')
            observed = []
            def provider_cleanup(state):
                def acquire():
                    with self.ledger.transaction(): observed.append(True)
                t = threading.Thread(target=acquire); t.start(); t.join(timeout=2)
                self.assertFalse(t.is_alive(), 'provider call held admission transaction')
            with patch.object(lc, 'terminate_locked', provider_cleanup): lc.sweep(immediate=True)
            self.assertEqual(observed, [True])


class ProcessEvidenceTests(unittest.TestCase):
    def test_identity_match_replacement_and_unavailable_are_distinct(self):
        for observed, expected in (('a'*64, True), ('b'*64, False), (None, None)):
            with self.subTest(observed=observed), patch('experiment_lifecycle.process_identity', return_value=observed), patch('experiment_lifecycle.os.kill') as kill:
                self.assertIs(alive(123, 'a'*64), expected)
                if observed is None: kill.assert_called_once_with(123, 0)
        with patch('experiment_lifecycle.process_identity', return_value=None), patch('experiment_lifecycle.os.kill', side_effect=ProcessLookupError):
            self.assertIs(alive(123, 'a'*64), False)
        for error in (PermissionError(), OSError()):
            with patch('experiment_lifecycle.process_identity', return_value=None), patch('experiment_lifecycle.os.kill', side_effect=error):
                self.assertIsNone(alive(123, 'a'*64))
        self.assertIsNone(alive(123, None))

    def test_ps_failure_and_timeout_with_live_process_are_unknown(self):
        identity = process_identity(os.getpid()); self.assertIsNotNone(identity)
        for error in (OSError(), subprocess.TimeoutExpired('ps', 2)):
            with self.subTest(error=type(error).__name__), patch('experiment.subprocess.run', side_effect=error):
                self.assertIsNone(alive(os.getpid(), identity))


class WorkerCleanupTests(Fixture):
    def test_active_diagnostic_row_without_worker_identity_is_preserved(self):
        self.update(state='CLEANUP_REQUIRED', lease_scope='d'*32)
        with database(self.state) as c: c.execute('insert into leases values (?,?,1,0)', ('d'*32, 999))
        lc=PrivateLeadLifecycle(self.settings, provider=Provider(), now=self.now)
        self.assertEqual(ExperimentSupervisor(self.ledger, lc).tick()['cleanup'], 'LOCAL_PENDING')
        with database(self.state) as c: self.assertEqual(c.execute('select active from leases').fetchone(), (1,))

    def test_worker_and_lease_finalization_commit_or_rollback_together(self):
        lc=PrivateLeadLifecycle(self.settings, provider=Provider(), now=self.now)
        self.update(ready=True, allocation='OWNED', supervisor_heartbeat=1000,
                    supervisor_pid=os.getpid(), supervisor_process=process_identity(os.getpid()))
        diagnostic=DiagnosticLifecycle(lc, self.binding, self.identity, self.ledger)
        original=self.ledger._write
        def interrupted(c,r):
            original(c,r)
            if r['worker_pid'] is None: raise SystemExit('synthetic crash before commit')
        with patch.object(lc.backend, 'propose', return_value={'synthetic':True}), patch.object(self.ledger, '_write', interrupted):
            with self.assertRaises(SystemExit): diagnostic.propose('d'*32, {})
        self.assertEqual(self.snapshot()['worker_pid'], os.getpid())
        with database(self.state) as c:
            self.assertEqual(c.execute('select active from leases').fetchone(), (1,))
            c.execute('update leases set active=0')  # Synthetic verified reconciliation before next call.
        with patch.object(lc.backend, 'propose', return_value={'synthetic':True}): diagnostic.propose('d'*32, {})
        self.assertIsNone(self.snapshot()['worker_pid'])
        with database(self.state) as c: self.assertEqual(c.execute('select active from leases').fetchone(), (0,))

    def test_live_worker_unknown_lookup_preserves_lease_then_exit_reconciles(self):
        for allocation in ('NONE', 'OWNED'):
            with self.subTest(allocation=allocation), subprocess.Popen(
                    [sys.executable, '-c', 'import sys; print("ready",flush=True); sys.stdin.read()'],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as child:
                self.assertEqual(child.stdout.readline().strip(), 'ready')
                identity = process_identity(child.pid); self.assertIsNotNone(identity)
                provider = Provider(); lc = PrivateLeadLifecycle(self.settings, provider=provider, now=self.now)
                self.update(state='CLEANUP_REQUIRED', cleanup='REQUIRED', allocation=allocation,
                            worker_pid=child.pid, worker_process=identity, lease_scope='d'*32,
                            allocation_id='synthetic-pod' if allocation=='OWNED' else None,
                            allocation_name='synthetic-name' if allocation=='OWNED' else None)
                if allocation=='OWNED':
                    provider.rows=[{'id':'synthetic-pod','name':'synthetic-name'}]
                    lc.save(lc.state(), phase='READY', pod_id='synthetic-pod', pod_name='synthetic-name')
                with database(self.state) as c: c.execute('insert into leases values (?,?,1,0)', ('d'*32, 2000))
                signals=[]; supervisor=ExperimentSupervisor(self.ledger, lc, kill=lambda *args: signals.append(args))
                with patch('experiment_lifecycle.process_identity', return_value=None): result=supervisor.tick()
                self.assertEqual(result['cleanup'], 'LOCAL_PENDING'); self.assertEqual(result['state'], 'CLEANUP_REQUIRED')
                self.assertEqual(signals, []); self.assertIsNone(child.poll())
                self.assertEqual(process_identity(child.pid), identity)
                with database(self.state) as c: self.assertEqual(c.execute('select active from leases').fetchone(), (1,))
                # Newly verifiable live identity still cannot confirm cleanup.
                self.assertEqual(supervisor.tick()['cleanup'], 'LOCAL_PENDING')
                self.assertTrue(all(sig == signal.SIGTERM for _,sig in signals))
                child.stdin.close(); child.wait(timeout=5)
                restarted=ExperimentSupervisor(ExperimentLedger(self.state, self.now), lc)
                self.assertEqual(restarted.tick()['cleanup'], 'CONFIRMED')

    def test_unknown_control_attempt_and_allocation_identities_block_completion(self):
        for role in ('control', 'attempt', 'allocation'):
            with self.subTest(role=role):
                self.update(state='ACTIVE', cleanup='NOT_REQUIRED', control_pid=None, control_process=None,
                            allocation_pid=None, allocation_process=None)
                if role=='attempt': self.reserve()
                else: self.update(**{role+'_pid':123, role+'_process':'a'*64})
                self.ledger.stop(self.binding, 'CANCELLED')
                lc=PrivateLeadLifecycle(self.settings, provider=Provider(), now=self.now)
                supervisor=ExperimentSupervisor(self.ledger, lc, is_alive=lambda *_:None, kill=lambda *_:self.fail('unknown identity signaled'))
                self.assertEqual(supervisor.tick()['cleanup'], 'LOCAL_PENDING')
                with self.ledger.transaction() as c: c.execute('delete from experiment_attempts')

    def test_unknown_allocation_worker_does_not_clear_inflight(self):
        self.update(state='CLEANUP_REQUIRED', allocation='RESERVED', allocation_name='synthetic-name',
                    allocation_pid=123, allocation_process='a'*64, allocation_inflight=True)
        provider=Provider(); provider.rows=[{'id':'synthetic-pod','name':'synthetic-name'}]
        lc=PrivateLeadLifecycle(self.settings, provider=provider, now=self.now)
        result=ExperimentSupervisor(self.ledger, lc, is_alive=lambda *_:None).tick()
        self.assertTrue(result['allocation_inflight']); self.assertNotEqual(result['cleanup'], 'CONFIRMED')
        self.assertEqual(provider.deleted, ['synthetic-pod'])


class Disabled80BTests(Fixture):
    def test_source_default_disables_new_80b_use_before_provider_or_lease(self):
        self.assertIs(json.loads((BASE/'SETTINGS.json').read_text())['gpu']['enabled'], False)
        self.update(state='COMPLETE', cleanup='CONFIRMED'); self.settings['gpu']['enabled']=False
        provider=Provider(); lc=Private80BLifecycle(self.settings, provider=provider, now=self.now)
        for operation in (lambda:lc.acquire('d'*32), lambda:lc.infer('d'*32, {}), lambda:lc.propose('d'*32, {}), lambda:lc.ensure_ready('d'*32, explicit=True), lc.resume):
            with self.assertRaisesRegex(Refused, 'private_80b_retired'): operation()
        with database(self.root) as c: self.assertEqual(c.execute('select count(*) from leases').fetchone()[0], 0)
        self.assertEqual(provider.created, 0)
        lead=PrivateLeadLifecycle(self.settings, provider=Provider(), now=self.now)
        lead.acquire('d'*32)
        with database(lead.root) as c: self.assertEqual(c.execute('select active from leases').fetchone(), (1,))

    def test_disabled_80b_cleanup_and_worker_refusal_remain_available(self):
        import worker
        self.update(state='COMPLETE', cleanup='CONFIRMED'); self.settings['gpu']['enabled']=False
        lc=Private80BLifecycle(self.settings, provider=Provider(), now=self.now)
        with database(self.root) as c: c.execute('insert into leases values (?,?,0,0)', ('d'*32, 2000))
        with patch.object(lc, 'infer', side_effect=AssertionError('inference entered')):
            with self.assertRaisesRegex(Refused, 'private_80b_retired'):
                worker.execute({'operation':'infer','tier':'PRIVATE_80B','scope':'d'*32,'packet':{}}, self.settings, lifecycle=lc)
        lc.release('d'*32, close=True); lc.sweep(manual=True)
        self.assertEqual(lc.status()['leases'], 0); self.assertEqual(lc.status()['phase'], 'RETIRED')


if __name__ == '__main__': unittest.main()
