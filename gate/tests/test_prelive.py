"""Offline diagnostic controls. Synthetic state and provider; no network/model."""
import ast
import contextlib
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(BASE/'src'),str(BASE)]
from common import Refused,canonical,database,private_dir
from experiment import ExperimentLedger,ExperimentDispatch,LIMITS,installed_identity,process_identity
from experiment_lifecycle import ExperimentSupervisor,DiagnosticLifecycle
from lifecycle import PrivateLeadLifecycle
from backends import PrivateLeadBackend
import verify_exact_runtime as exact


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.clock=[1000.];self.now=lambda:self.clock[0]
        self.settings=json.loads((BASE/'SETTINGS.json').read_text());self.settings['state_directory']=str(self.root)
        self.settings['gpu']['enabled']=True  # Cannot revive the retired release.
        (self.root/'gpu.json').write_text(canonical({'phase':'RETIRED','retired_confirmed_at':999,'pod_id':None}))
        self.state=private_dir(self.root/'private-lead');self.ledger=ExperimentLedger(self.state,self.now)
        self.binding={'experiment_id':'a'*32,'source_id':'b'*64,'install_id':'c'*64,'deadline':1900.}
        self.identity={k:self.binding[k] for k in ('source_id','install_id')}
        self.ledger.create(self.binding,owner_pid=os.getpid(),owner_process=process_identity(os.getpid()))
    def tearDown(self):self.tmp.cleanup()
    def reserve(self,kind='proposal',tokens=1024):return self.ledger.reserve(self.binding,self.identity,kind,tokens)
    def snapshot(self):return self.ledger.snapshot(self.binding)
    def update(self,**values):
        with self.ledger.transaction() as c:
            r=self.ledger._bound(c,self.binding);r.update(values);self.ledger._write(c,r)


class LedgerTests(Fixture):
    def test_initial_private_state_and_exact_limits(self):
        self.assertEqual(self.snapshot()['counts'],{'reserved':0,'dispatched':0,'known_completion':0,'uncertain_completion':0})
        self.assertEqual(self.snapshot()['limits'],LIMITS);self.assertEqual((self.state/'control.sqlite').stat().st_mode&0o777,0o600)
    def test_six_succeed_seventh_refused(self):
        self.assertEqual(self.reserve('readiness',16),1)
        for number in range(2,7):self.assertEqual(self.reserve(),number)
        with self.assertRaisesRegex(Refused,'total_limit'):self.reserve()
    def test_readiness_and_proposal_limits_independent(self):
        self.reserve('readiness',16)
        with self.assertRaisesRegex(Refused,'class_limit'):self.reserve('readiness',16)
        for _ in range(5):self.reserve()
        self.assertEqual(self.snapshot()['counts']['reserved'],6)
    def test_five_proposals_deny_sixth_with_total_room(self):
        for _ in range(5):self.reserve()
        with self.assertRaisesRegex(Refused,'class_limit'):self.reserve()
        self.assertEqual(self.reserve('readiness',16),6)
    def test_token_allocation_and_invalid_class_fail_before_spend(self):
        for kind,tokens in [('readiness',17),('proposal',1025),('proposal',True),('warmup',1),('proposal',0)]:
            with self.assertRaises(Refused):self.reserve(kind,tokens)
        self.assertEqual(self.snapshot()['counts']['reserved'],0)
    def test_stale_binding_and_wrong_install_cannot_spend(self):
        for field,value in [('experiment_id','d'*32),('source_id','d'*64),('install_id','d'*64),('deadline',1901)]:
            with self.assertRaises(Refused):self.ledger.reserve({**self.binding,field:value},self.identity,'proposal',1024)
        with self.assertRaises(Refused):self.ledger.reserve(self.binding,{'source_id':'e'*64},'proposal',1024)
    def test_restart_reads_consumed_and_no_refund(self):
        n=self.reserve();self.ledger.dispatched(self.binding,n);self.ledger.completion(self.binding,n,False)
        restarted=ExperimentLedger(self.state,self.now)
        self.assertEqual(restarted.snapshot(self.binding)['counts'],{'reserved':1,'dispatched':1,'known_completion':0,'uncertain_completion':1})
        restarted.completion(self.binding,n,True)
        self.assertEqual(restarted.snapshot(self.binding)['counts']['reserved'],1)
        with self.assertRaises(Refused):restarted.dispatched(self.binding,n)
    def test_expired_and_completed_refuse_and_keep_ownership(self):
        self.clock[0]=1900
        with self.assertRaisesRegex(Refused,'deadline'):self.reserve()
        self.assertIsNotNone(self.ledger.current())
        self.update(state='COMPLETE')
        with self.assertRaisesRegex(Refused,'terminal'):self.reserve()
    def test_expiry_and_minimum_time_reserve_cleanup_window(self):
        for now in (1779.5,1780,1900):
            self.clock[0]=now
            with self.assertRaisesRegex(Refused,'deadline'):self.reserve()
        self.assertEqual(self.snapshot()['counts']['reserved'],0)
    def test_parallel_processes_cannot_share_last_attempt(self):
        self.reserve('readiness',16)
        for _ in range(4):self.reserve()
        script="""import json,sys
from experiment import ExperimentLedger
from common import Refused
root,binding,identity=json.loads(sys.argv[1]);ledger=ExperimentLedger(root,lambda:1000)
print('READY',flush=True);sys.stdin.readline()
try:print(ledger.reserve(binding,identity,'proposal',1024),flush=True)
except Refused:print('REFUSED',flush=True)
"""
        env={**os.environ,'PYTHONPATH':str(BASE/'src'),'PYTHONDONTWRITEBYTECODE':'1'}
        children=[subprocess.Popen([sys.executable,'-B','-c',script,json.dumps([str(self.state),self.binding,self.identity])],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=env) for _ in range(2)]
        try:
            for child in children:self.assertEqual(child.stdout.readline().strip(),'READY')
            for child in children:child.stdin.write('\n');child.stdin.flush()
            results=[child.communicate(timeout=15)[0].strip() for child in children]
            self.assertEqual(sorted(results),['6','REFUSED']);self.assertEqual(self.snapshot()['counts']['reserved'],6)
        finally:
            for child in children:
                if child.poll() is None:child.kill();child.wait()
    def test_crash_after_reservation_does_not_restore_attempt(self):
        script="import json,sys,os;from experiment import ExperimentLedger;r,b,i=json.loads(sys.argv[1]);ExperimentLedger(r,lambda:1000).reserve(b,i,'proposal',1024);os._exit(9)"
        result=subprocess.run([sys.executable,'-B','-c',script,json.dumps([str(self.state),self.binding,self.identity])],env={**os.environ,'PYTHONPATH':str(BASE/'src')})
        self.assertEqual(result.returncode,9);self.assertEqual(ExperimentLedger(self.state,self.now).snapshot(self.binding)['counts']['reserved'],1)
    def test_dispatch_failure_cancellation_and_parser_failure_never_refund(self):
        for error in (TimeoutError('PRIVATE_MARKER'),KeyboardInterrupt()):
            guard=ExperimentDispatch(self.ledger,self.binding,self.identity)
            with self.assertRaises(type(error)):
                with guard.attempt('proposal',1024):raise error
            self.assertEqual(self.snapshot()['counts']['reserved'],1)
            self.assertEqual(self.snapshot()['state'],'CLEANUP_REQUIRED')
            self.update(state='ACTIVE',stop_code=None)
            # New reservation in next iteration is still consumed.
            break
        self.update(state='ACTIVE',stop_code=None)
        guard=ExperimentDispatch(self.ledger,self.binding,self.identity)
        with self.assertRaises(KeyboardInterrupt):
            with guard.attempt('proposal',1024):raise KeyboardInterrupt()
        self.assertEqual(self.snapshot()['counts']['reserved'],2)
        self.assertNotIn('PRIVATE_MARKER',canonical(self.snapshot()))
    def test_single_active_experiment_and_no_reused_ids(self):
        with self.assertRaisesRegex(Refused,'owned'):
            self.ledger.create({**self.binding,'experiment_id':'e'*32},owner_pid=os.getpid(),owner_process=process_identity(os.getpid()))


class Provider:
    def __init__(self):self.rows=[];self.deleted=[];self.uncertain=False;self.created=0
    def pods(self):return list(self.rows)
    def delete(self,pod):
        self.deleted.append(pod)
        if not self.uncertain:self.rows=[]
    def close_tunnel(self,state):pass
    def ensure_guard(self):pass
    def preflight(self):return {'available':True,'hourly_usd':2.5}
    def create(self,name):self.created+=1;self.rows=[{'id':'synthetic-pod','name':name}];return self.rows[0]


class SupervisorTests(Fixture):
    def setUp(self):
        super().setUp();self.provider=Provider();self.lc=PrivateLeadLifecycle(self.settings,provider=self.provider,now=self.now,sleep=lambda _:None)
        self.supervisor=ExperimentSupervisor(self.ledger,self.lc,is_alive=lambda *_:False)
    def owned(self):
        self.update(allocation='OWNED',allocation_id='synthetic-pod',allocation_name='synthetic-name',allocation_attempts=1)
        self.provider.rows=[{'id':'synthetic-pod','name':'synthetic-name'}]
        self.lc.save(self.lc.state(),phase='READY',pod_id='synthetic-pod',pod_name='synthetic-name')
    def test_short_janitor_sweep_cannot_replace_live_watcher_identity(self):
        self.update(supervisor_pid=123,supervisor_process='a'*64,supervisor_heartbeat=999)
        self.supervisor.is_alive=lambda *_:True
        self.supervisor.tick()
        self.assertEqual(self.snapshot()['supervisor_pid'],123)
        watcher=ExperimentSupervisor(self.ledger,self.lc,is_alive=lambda *_:True,publish_heartbeat=True)
        watcher.tick();self.assertEqual(self.snapshot()['supervisor_pid'],os.getpid())

    def test_caller_dies_before_allocation_without_any_provider_call(self):
        with patch.object(self.provider,'pods',side_effect=AssertionError('provider must not be called')):
            self.assertEqual(self.supervisor.tick()['state'],'COMPLETE')
        self.assertEqual(self.provider.created,0)
    def test_caller_dies_after_reservation_preserves_uncertain_count(self):
        self.reserve();result=self.supervisor.tick()
        self.assertEqual(result['state'],'COMPLETE');self.assertEqual(result['counts']['uncertain_completion'],1)
    def test_caller_dies_while_allocation_owned_deletes_and_reconciles(self):
        self.owned();self.update(lease_scope='a'*32,worker_pid=999999,worker_process='d'*64)
        with database(self.state) as c:c.execute('insert into leases values (?,?,1,0)',('a'*32,2000))
        result=self.supervisor.tick();self.assertEqual(result['cleanup'],'CONFIRMED');self.assertEqual(result['allocation'],'ABSENT')
        with database(self.state) as c:self.assertEqual(c.execute('select count(*) from leases').fetchone()[0],0)
    def test_deadline_deletes_even_when_worker_is_alive_or_hung(self):
        self.owned();self.reserve();self.clock[0]=1780
        self.supervisor.is_alive=lambda *_:True
        result=self.supervisor.tick();self.assertEqual(self.provider.deleted,['synthetic-pod'])
        self.assertEqual(result['allocation'],'ABSENT');self.assertEqual(result['state'],'CLEANUP_REQUIRED')
        self.assertEqual(result['counts']['uncertain_completion'],1)
    def test_worker_death_ends_experiment_before_deadline(self):
        n=self.reserve();self.ledger.dispatched(self.binding,n)
        self.supervisor.is_alive=lambda pid,identity:pid==self.snapshot()['owner_pid'] and False
        self.update(owner_pid=123)
        self.supervisor.is_alive=lambda pid,_:pid==123
        self.assertEqual(self.supervisor.tick()['stop_code'],'WORKER_LOST')
    def test_unknown_provider_deletion_retains_ownership_and_supervision(self):
        self.owned();self.provider.uncertain=True
        result=self.supervisor.tick();self.assertEqual(result['state'],'CLEANUP_REQUIRED');self.assertEqual(result['cleanup'],'UNKNOWN')
        self.assertEqual(result['allocation_id'],'synthetic-pod');self.assertIsNotNone(self.ledger.current())
        self.provider.uncertain=False;self.assertEqual(self.supervisor.tick()['state'],'COMPLETE')
    def test_hung_worker_gets_verified_term_then_persisted_kill_grace(self):
        import signal
        self.owned();self.clock[0]=1780
        self.update(worker_pid=999999,worker_process='a'*64)
        signals=[];self.supervisor.is_alive=lambda *_:True;self.supervisor.kill=lambda pid,sig:signals.append((pid,sig))
        self.supervisor.tick();self.assertIn((999999,signal.SIGTERM),signals)
        self.clock[0]=1786;self.supervisor.tick();self.assertIn((999999,signal.SIGKILL),signals)
        self.assertEqual(self.snapshot()['state'],'CLEANUP_REQUIRED')

    def test_provider_list_failure_never_proves_absence(self):
        self.owned()
        with patch.object(self.provider,'pods',side_effect=OSError('PRIVATE_MARKER')):result=self.supervisor.tick()
        self.assertEqual(result['cleanup'],'UNKNOWN');self.assertNotIn('PRIVATE_MARKER',canonical(result))
    def test_restart_after_deadline_cleans_without_allocation(self):
        self.owned();self.clock[0]=2000
        restart=ExperimentSupervisor(ExperimentLedger(self.state,self.now),self.lc,is_alive=lambda *_:False)
        self.assertEqual(restart.tick()['state'],'COMPLETE');self.assertEqual(self.provider.created,0)
    def test_ambiguous_create_cannot_be_cleared_by_empty_list(self):
        self.update(allocation='UNCERTAIN',allocation_attempts=1,allocation_name='synthetic-name')
        result=self.supervisor.tick();self.assertEqual(result['cleanup'],'UNKNOWN');self.assertEqual(result['state'],'CLEANUP_REQUIRED')
    def test_hung_lifecycle_lock_does_not_block_provider_deletion(self):
        self.owned()
        with self.lc.lock():result=self.supervisor.tick()
        self.assertEqual(self.provider.deleted,['synthetic-pod']);self.assertEqual(result['state'],'CLEANUP_REQUIRED')
        self.assertEqual(self.supervisor.tick()['state'],'COMPLETE')


class DispatchTests(Fixture):
    def setUp(self):
        super().setUp();self.backend=PrivateLeadBackend(self.settings)
        self.backend.experiment=ExperimentDispatch(self.ledger,self.binding,self.identity)
        artifact=json.loads(subprocess.check_output(['node',str(BASE/'runtime-readiness.mjs')]))
        self.request=artifact['messages']['ordinaryInitial']
    def opener(self,text='{"kind":"ESCALATION","reason":"SYNTHETIC"}',broken=False):
        case=self
        class Opener:
            def open(self,req,timeout=None):
                if req.full_url.endswith('/models'):return io.BytesIO(json.dumps({'data':[{'id':case.backend.model}]}).encode())
                case.assertEqual(case.snapshot()['counts']['reserved'],1)
                case.assertEqual(case.snapshot()['counts']['dispatched'],1)
                case.assertLessEqual(timeout,case.binding['deadline']-120-case.now())
                if broken:raise TimeoutError('PRIVATE_MARKER')
                payload=json.loads(req.data)
                if not payload['stream']:
                    case.assertEqual(payload['max_tokens'],16)
                    return io.BytesIO(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':text}}]}).encode())
                case.assertEqual(payload['max_tokens'],1024)
                return io.BytesIO(('data: '+json.dumps({'choices':[{'delta':{'content':text},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n').encode())
        return Opener()
    def test_actual_proposal_reserves_before_http_and_records_completion(self):
        with patch('backends.urllib.request.build_opener',return_value=self.opener()):self.backend.propose(self.request)
        self.assertEqual(self.snapshot()['counts']['known_completion'],1)
    def test_completed_parse_failure_stays_consumed_but_correctable(self):
        with patch('backends.urllib.request.build_opener',return_value=self.opener('{')):
            with self.assertRaisesRegex(Refused,'result_schema'):self.backend.propose(self.request)
        self.assertEqual(self.snapshot()['counts']['known_completion'],1);self.assertEqual(self.snapshot()['state'],'ACTIVE')
    def test_timeout_uncertain_and_no_retry(self):
        with patch('backends.urllib.request.build_opener',return_value=self.opener(broken=True)):
            with self.assertRaises(Refused):self.backend.propose(self.request)
        self.assertEqual(self.snapshot()['counts']['reserved'],1);self.assertEqual(self.snapshot()['state'],'CLEANUP_REQUIRED')
    def test_smoke_failed_ends_experiment_and_never_retries(self):
        with patch('backends.urllib.request.build_opener',return_value=self.opener('BAD')):
            with self.assertRaisesRegex(Refused,'smoke_failed'):self.backend.health_check(smoke=True)
            with self.assertRaises(Refused):self.backend.health_check(smoke=True)
        self.assertEqual(self.snapshot()['counts']['reserved'],1);self.assertEqual(self.snapshot()['stop_code'],'READINESS_FAILED')
    def test_missing_ownership_cannot_use_ordinary_path(self):
        with patch('backends.urllib.request.build_opener',side_effect=AssertionError('no HTTP')):
            with self.assertRaisesRegex(Refused,'ownership_required'):PrivateLeadBackend(self.settings).propose(self.request)
    def test_expired_before_http_prevents_all_requests(self):
        self.clock[0]=1900
        with patch('backends.urllib.request.build_opener',side_effect=AssertionError('no HTTP')):
            with self.assertRaisesRegex(Refused,'deadline'):self.backend.propose(self.request)
    def test_provider_diagnostic_timeout_is_absolute_and_cleanup_survives_expiry(self):
        from runpod import Runpod
        from types import SimpleNamespace
        provider=Runpod(self.settings,self.settings['private_lead']);provider.cli=self.root/'synthetic-cli'
        provider.cli.write_bytes(b'synthetic');provider.pin={'binary_sha256':hashlib.sha256(b'synthetic').hexdigest()}
        provider.experiment_deadline=1900;timeouts=[]
        def run(args,**kwargs):
            timeouts.append(kwargs['timeout'])
            return SimpleNamespace(returncode=0,stdout=b'synthetic-key' if args[0]=='/usr/bin/security' else b'[]')
        with patch('runpod.subprocess.run',side_effect=run),patch('runpod.time.time',return_value=1775):provider.call('pod','list')
        self.assertEqual(timeouts,[5,5]);timeouts.clear()
        with patch('runpod.subprocess.run',side_effect=run),patch('runpod.time.time',return_value=1901):
            with self.assertRaisesRegex(Refused,'deadline'):provider.call('pod','list')
            provider.experiment_cleanup=True;provider.call('pod','list')
        self.assertEqual(timeouts,[10,20]);timeouts.clear();del provider.experiment_deadline
        with patch('runpod.subprocess.run',side_effect=run):provider.call('pod','list')
        self.assertEqual(timeouts,[10,45])

    def test_experiment_provider_error_records_fixed_code_without_body(self):
        from runpod import Runpod
        from types import SimpleNamespace
        provider=Runpod(self.settings,self.settings['private_lead']);provider.cli=self.root/'synthetic-cli'
        provider.cli.write_bytes(b'synthetic');provider.pin={'binary_sha256':hashlib.sha256(b'synthetic').hexdigest()}
        provider.experiment_deadline=1900
        def run(args,**kwargs):
            return SimpleNamespace(returncode=0,stdout=b'synthetic-key') if args[0]=='/usr/bin/security' else SimpleNamespace(returncode=1,stdout=b'',stderr=b'{"error":"PRIVATE_MARKER","code":"PRIVATE_MARKER"}')
        with patch('runpod.subprocess.run',side_effect=run),patch('runpod.time.time',return_value=1000):
            with self.assertRaises(Refused):provider.call('pod','list')
        record=json.loads((self.root/'last-runpod-error.json').read_text())
        self.assertEqual(record,{'code':'EXPERIMENT_PROVIDER_REQUEST_FAILED','time':1000})

    def test_worker_absolute_alarm_interrupts_active_stream_and_requires_cleanup(self):
        import worker
        now=time.time();binding={**self.binding,'experiment_id':'f'*32,'deadline':now+121.5}
        # Independent private synthetic state with real wall time for SIGALRM.
        root=private_dir(self.root/'alarm');settings={**self.settings,'state_directory':str(root)}
        ledger=ExperimentLedger(private_dir(root/'private-lead'))
        ledger.create(binding,owner_pid=os.getpid(),owner_process=process_identity(os.getpid()))
        with ledger.transaction() as c:
            r=ledger._bound(c,binding);r.update(ready=True,allocation='OWNED',allocation_id='synthetic',supervisor_pid=os.getpid(),supervisor_process=process_identity(os.getpid()),supervisor_heartbeat=now);ledger._write(c,r)
        backend=PrivateLeadBackend(settings);lc=PrivateLeadLifecycle(settings,provider=Provider(),backend=backend)
        class Hung(io.BytesIO):
            def __next__(self):time.sleep(100);return super().__next__()
        class Opener:
            def open(self,req,timeout=None):
                if req.full_url.endswith('/models'):return io.BytesIO(json.dumps({'data':[{'id':backend.model}]}).encode())
                return Hung()
        body={'operation':'private_lead_propose','scope':'a'*32,'packet':{'request':self.request,'experiment':binding}}
        with patch.object(worker,'installed_identity',return_value=self.identity),patch('backends.urllib.request.build_opener',return_value=Opener()):
            with self.assertRaisesRegex(Refused,'experiment_deadline'):worker.execute(body,settings,lifecycle=lc)
        result=ledger.snapshot(binding)
        self.assertEqual(result['counts']['reserved'],1);self.assertEqual(result['counts']['uncertain_completion'],1)
        self.assertEqual(result['state'],'CLEANUP_REQUIRED');self.assertEqual(result['stop_code'],'DEADLINE')
        self.assertEqual(result['allocation_id'],'synthetic')

    def test_lifecycle_single_allocation_and_one_readiness(self):
        provider=Provider();lc=PrivateLeadLifecycle(self.settings,provider=provider,backend=self.backend,now=self.now)
        diagnostic=DiagnosticLifecycle(lc,self.binding,self.identity,self.ledger)
        self.update(supervisor_heartbeat=1000,supervisor_pid=os.getpid(),supervisor_process=process_identity(os.getpid()))
        diagnostic.allocate(3);self.assertEqual(provider.created,1)
        with self.assertRaises(Refused):diagnostic.allocate(3)
        with patch.object(provider,'ssh_info',create=True,return_value=('127.0.0.1',22)),patch.object(provider,'ssh',create=True),patch.object(provider,'server_alive',create=True),patch.object(provider,'tunnel',create=True),patch('backends.urllib.request.build_opener',return_value=self.opener('READY')):
            diagnostic.ready()
            with self.assertRaises(Refused):diagnostic.ready()
        self.assertEqual(self.snapshot()['counts']['reserved'],1)


class ExactToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.artifact=json.loads(subprocess.check_output(['node',str(BASE/'runtime-readiness.mjs')]))
    def test_missing_failed_or_unbound_host_semantic_proof_refuses_before_compiler(self):
        for change in ('missing','failed','schema','representatives','branches','controls','accepted'):
            with self.subTest(change=change):
                value=json.loads(json.dumps(self.artifact));row=value['surfaces']['reviewer'];host=row['hostSemanticValidation']
                if change=='missing':del row['hostSemanticValidation']
                elif change=='failed':host['status']='FAIL'
                elif change=='schema':host['semanticSchemaDigest']='a'*64
                elif change=='representatives':host['representativesDigest']='a'*64
                elif change=='branches':host['positiveBranches']=0
                elif change=='controls':host['negativeControls']=[]
                elif change=='accepted':host['negativeControls'][0]['rejected']=False
                with self.assertRaisesRegex(ValueError,'HOST_SEMANTIC_VALIDATION'):exact.run(value)
    def test_all_production_full_schema_identities_and_branches(self):
        exact.verify_artifact(self.artifact);self.assertEqual(set(self.artifact['surfaces']),set(exact.SURFACES))
        for row in self.artifact['surfaces'].values():self.assertEqual(len(row['representatives']),row['branches'])
    def test_absent_compiler_identity_explicit_not_run_no_mock_proof(self):
        result=exact.run(self.artifact);self.assertEqual(result['exactCompiler'],'NOT_RUN');self.assertEqual(result['tokenMeasurement'],'NOT_RUN')
        self.assertNotEqual(result['status'],'PASS')
    def test_changed_schema_rejected_before_any_compiler(self):
        value=json.loads(json.dumps(self.artifact));value['surfaces']['reviewer']['request']['schema']['type']='array'
        with self.assertRaisesRegex(ValueError,'SCHEMA_IDENTITY'):exact.run(value)
    def test_missing_tokenizer_cannot_fall_back(self):
        result=exact.run(self.artifact,{'resolved':{}},None)
        self.assertEqual(result['status'],'NOT_RUN');self.assertEqual(result['tokenMeasurement'],'NOT_RUN')
    def test_amendment_refuses_private_lead_leases_and_unresolved_experiment(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('prelive_amendment',BASE.parent/'scripts/upgrade_work_mode.py')
        amendment=importlib.util.module_from_spec(spec);spec.loader.exec_module(amendment)
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory);state=private_dir(prefix/'state/gate/private-lead')
            (state.parent/'gpu.json').write_text(canonical({'phase':'RETIRED','retired_confirmed_at':999}))
            with database(state) as c:c.execute('insert into leases values (?,?,1,0)',('a'*32,2000))
            with patch.object(amendment.platform,'system',return_value='Darwin'),patch.object(amendment.op,'owns_process',return_value=False),patch.object(amendment.op,'process_record',return_value={}):
                with self.assertRaisesRegex(ValueError,'leases'):amendment.safe(prefix)
                with database(state) as c:c.execute('delete from leases')
                ledger=ExperimentLedger(state,lambda:1000)
                ledger.create({'experiment_id':'a'*32,'source_id':'b'*64,'install_id':'c'*64,'deadline':1900},owner_pid=os.getpid(),owner_process=process_identity(os.getpid()))
                with self.assertRaisesRegex(ValueError,'Unresolved experiment'):amendment.safe(prefix)

    def test_installed_identity_comes_from_receipt_and_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'gate').mkdir();(root/'gate/FREEZE.json').write_text('{}')
            (root/'receipt.json').write_text(json.dumps({'work_mode_source_manifest_sha256':'a'*64}))
            value=installed_identity(root/'gate');self.assertEqual(value['source_id'],'a'*64);self.assertEqual(value['install_id'],hashlib.sha256(b'{}').hexdigest())

if __name__=='__main__':unittest.main()
