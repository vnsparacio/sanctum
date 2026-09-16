import copy
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
BASE=Path(__file__).resolve().parents[1];sys.path[:0]=[str(BASE/'src'),str(BASE)]
from common import Refused, canonical, database, strict_json
from authority import authorize
from dispatch import assess
from schema import validate
from backends import Remote, Private80BBackend, PrivateLeadBackend, LocalMultimodalBackend, extract_chat, answer_result
from lifecycle import Private80BLifecycle, PrivateLeadLifecycle
from runpod import capacity_rejected
from media import prepare, load, expand
import install
import manage


def settings(root):
    s=json.loads((BASE/'SETTINGS.json').read_text());s['state_directory']=str(root);s['python']=sys.executable;s['gpu']['auto_start']=True;return s

def audit(tier='LOCAL_4B'):
    return {'urgency':'ABSENT','stakes':'NORMAL','domains':['other_unknown'],'request_role':'explanation','uncertainty':[], 'quality':{'recommended_tier':tier,'reason_codes':['ROUTINE_LANGUAGE']},'source_need':{'classification':'NONE','reason_codes':['DETERMINISTIC_OR_SELF_CONTAINED']},'context_need':{'classification':{'attachments':'NONE','prior_context':'NONE'},'answer':{'attachments':'NONE','prior_context':'NONE'}},'needs_local_tools':False}

def packet(): return {'scope':'a'*32,'revision':0,'prompt':'synthetic question','semantic_state':{'high_stakes':False,'privacy_floor':'PERSONAL'},'attachment_summary':{'count':0,'visual_count':0,'document_count':0,'video_count':0},'disclosed':{}}
def state(): return {'scope':'a'*32,'revision':-1,'high_stakes':False,'privacy_floor':'PERSONAL','request_digest':''}

def chat(text,model=None):
    r={'choices':[{'finish_reason':'stop','message':{'content':text}}]}
    if model:r.update(model=model['canonical'],provider=model['response_provider'])
    return r

class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.root.chmod(0o700);self.s=settings(self.root)
    def tearDown(self): self.tmp.cleanup()

class Policy(Temp):
    def test_tiers_independent_of_stakes(self):
        for tier in ['LOCAL_4B','PRIVATE_80B','HOSTED_235B','OPENAI_FRONTIER']:
            self.assertEqual(assess(packet(),state(),audit(tier))['route'],tier)
    def test_complex_code_promotes_80(self):
        a=audit();a['quality']['reason_codes']=['TECHNICAL_DEBUGGING'];self.assertEqual(assess(packet(),state(),a)['route'],'PRIVATE_80B')
    def test_high_stakes_forces_openai(self):
        a=audit();a['stakes']='HIGH_STAKES';self.assertEqual(assess(packet(),state(),a)['route'],'OPENAI_FRONTIER')
    def test_high_stakes_persists(self):
        s=state();s['high_stakes']=True;self.assertEqual(assess(packet(),s,audit())['route'],'OPENAI_FRONTIER')
    def test_urgency_preempts_frontier(self):
        a=audit();a.update(urgency='PRESENT',stakes='HIGH_STAKES');self.assertEqual(assess(packet(),state(),a,True)['route'],'URGENT_SAFETY')
    def test_context_classification_blocks(self):
        a=audit();a.update(urgency='UNKNOWN',uncertainty=['missing_context']);a['context_need']['classification']['attachments']='REQUIRED';self.assertEqual(assess(packet(),state(),a)['route'],'CONTEXT_REQUIRED')
    def test_tools_stay_local(self):
        a=audit('HOSTED_235B');a['needs_local_tools']=True;self.assertEqual(assess(packet(),state(),a)['route'],'LOCAL_4B')
    def test_visual_capability_route(self):
        p=packet();p['attachment_summary'].update(count=1,visual_count=1);self.assertEqual(assess(p,state(),audit('MULTIMODAL'))['route'],'MULTIMODAL')
    def test_documents_use_private_reasoning(self):
        p=packet();p['attachment_summary'].update(count=1,document_count=1);a=audit();a['context_need']['answer']['attachments']='REQUIRED';self.assertEqual(assess(p,state(),a)['route'],'PRIVATE_80B')

    def test_irrelevant_attachment_does_not_escalate(self):
        p=packet();p['attachment_summary'].update(count=1,visual_count=1);self.assertEqual(assess(p,state(),audit())['route'],'LOCAL_4B')
    def test_schema_rejects_authority_and_wrong_types(self):
        for field,value in [('authority','yes'),('needs_local_tools',1),('stakes','probably')]:
            a=audit();a[field]=value
            with self.assertRaises(Refused):validate(a)
    def test_duplicate_json_and_nan(self):
        for raw in ['{"a":1,"a":2}','{"x":NaN}']:
            with self.assertRaises(Refused):strict_json(raw)

class Authority(Temp):
    def setUp(self):
        super().setUp();self.key=os.urandom(32);(self.root/'authority.key').write_bytes(self.key);(self.root/'authority.key').chmod(0o600)
    def body(self):return {'operation':'infer','tier':'PRIVATE_80B','packet':{'prompt':'synthetic'},'state':state(),'scope':'a'*32,'approval':'session_private_prompt','strong':False,'nonce':os.urandom(32).hex(),'expires':1100,'spec_sha256':'spec'}
    def signed(self,b):
        raw=canonical(b);return {'body':raw,'mac':hmac.new(self.key,raw.encode(),hashlib.sha256).hexdigest()}
    def auth(self,b):return authorize(self.signed(b),self.s,now=lambda:1000,settings_hash='spec')
    def test_once_only_durable_across_calls(self):
        b=self.body();self.auth(b)
        with self.assertRaises(sqlite3.IntegrityError):self.auth(b)
    def test_wrong_signature(self):
        e=self.signed(self.body());e['body']+=' '
        with self.assertRaises(Refused):authorize(e,self.s,now=lambda:1000,settings_hash='spec')
    def test_tier_approval_not_reusable(self):
        b=self.body();b['tier']='HOSTED_235B'
        with self.assertRaises(Refused):self.auth(b)
    def test_session_grant_never_history(self):
        b=self.body();b['packet']['history']=[{'role':'assistant','content':'private tool data'}]
        with self.assertRaises(Refused):self.auth(b)
    def test_expiration_settings_and_scope(self):
        for k,v in [('expires',999),('expires',1400),('spec_sha256','wrong'),('scope','remote')]:
            b=self.body();b[k]=v
            with self.assertRaises(Refused):self.auth(b)
    def test_high_stakes_cannot_use_80(self):
        b=self.body();b['state']['high_stakes']=True
        with self.assertRaises(Refused):self.auth(b)
    def test_private_lead_proposal_requires_exact_signed_scope(self):
        b=self.body();b.update(operation='private_lead_propose',tier='PRIVATE_LEAD',approval='private_lead_workmode',packet={'request':{'system':'synthetic','request':{}}})
        self.auth(b)
        for key,value in [('approval','exact_disclosure'),('tier','PRIVATE_80B'),('packet',{'request':{'system':'x','request':{}},'extra':True})]:
            bad=self.body();bad.update(operation='private_lead_propose',tier='PRIVATE_LEAD',approval='private_lead_workmode',packet={'request':{'system':'synthetic','request':{}}});bad[key]=value
            with self.assertRaises(Refused):self.auth(bad)

class Transport(Temp):
    def test_minimal_classifier_packet_and_provider_policy(self):
        sent=[]
        def send(url,p,headers,**kw): sent.append(p);return chat(canonical(audit()),self.s['models']['GEMINI_AUDIT'])
        Remote(self.s,send,lambda:'test').classify(packet(),'one','audit only')
        p=sent[0];self.assertEqual(len(p['messages']),2);self.assertNotIn('history',canonical(p));self.assertNotIn('tools',p)
        self.assertTrue(p['provider']['zdr']);self.assertFalse(p['provider']['allow_fallbacks']);self.assertEqual(p['provider']['data_collection'],'deny')
    def test_frontier_is_openai_only(self):
        sent=[]
        def send(url,p,headers,**kw):sent.append((url,p));return chat(canonical({'answer':'test','escalation':'NONE'}),self.s['models']['OPENAI_FRONTIER'])
        Remote(self.s,send,lambda:'test').infer('OPENAI_FRONTIER',{'prompt':'synthetic'},'two')
        self.assertEqual(sent[0][1]['provider']['only'],['azure']);self.assertNotIn('tools',sent[0][1])
    def test_direct_openai_store_false(self):
        self.s['frontier_transport']='openai';self.s['direct_openai_retention_authorized']=True;sent=[]
        def send(url,p,headers,**kw):
            sent.append((url,p));return {'status':'completed','model':p['model'],'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'{"answer":"test","escalation":"NONE"}'}]}]}
        Remote(self.s,send,direct_key=lambda:'test').infer('OPENAI_FRONTIER',{'prompt':'synthetic'},'direct')
        self.assertEqual(sent[0][0],'https://api.openai.com/v1/responses');self.assertFalse(sent[0][1]['store']);self.assertNotIn('tools',sent[0][1])
    def test_no_retry_and_budget_reserved_on_timeout(self):
        calls=[]
        def fail(*a,**k):calls.append(1);raise Refused('timeout')
        with self.assertRaises(Refused):Remote(self.s,fail,lambda:'test').infer('HOSTED_235B',{'prompt':'synthetic'},'timeout')
        self.assertEqual(len(calls),1)
        with database(self.root) as c:self.assertGreater(c.execute('select charged from network').fetchone()[0],0)
    def test_budget_blocks_before_network(self):
        self.s['max_request_usd']=0
        with self.assertRaises(Refused):Remote(self.s,lambda *a,**k:self.fail('network')).infer('HOSTED_235B',{'prompt':'test'},'budget')
    def test_wrong_provider_and_tools_rejected(self):
        m=self.s['models']['HOSTED_235B'];r=chat('ok',m);r['provider']='Other'
        with self.assertRaises(Refused):extract_chat(r,m)
        r=chat('ok');r['choices'][0]['message']['tool_calls']=[{'name':'shell'}]
        with self.assertRaises(Refused):extract_chat(r)
    def test_text_only_rejects_images(self):
        with self.assertRaises(Refused):Remote(self.s).infer('HOSTED_235B',{'prompt':'x','images':[{}]},'bad')
        with self.assertRaises(Refused):Private80BBackend(self.s).infer({'prompt':'x','images':[{}]})
    def test_80_readiness_requires_alias_and_smoke(self):
        def send(url,p=None,*args,**kw):return {'data':[{'id':'vinceai-qwen80b'}]} if url.endswith('/models') else chat('READY')
        self.assertTrue(Private80BBackend(self.s,send).health_check(smoke=True))
        with self.assertRaises(Refused):Private80BBackend(self.s,lambda *a,**k:{'data':[{'id':'wrong'}]}).health_check()
    def test_private_lead_has_its_own_alias_and_loopback_port(self):
        self.s['private_lead']['enabled']=True
        calls=[]
        def send(url,p=None,*args,**kw):
            if not url.endswith('/models'): calls.append(p)
            return {'data':[{'id':'sanctum-private-lead-qwen35-122b'}]} if url.endswith('/models') else chat('READY')
        self.assertTrue(PrivateLeadBackend(self.s,send).health_check(smoke=True))
        self.assertEqual(calls[0]['chat_template_kwargs'],{'enable_thinking':False})
        self.assertEqual(PrivateLeadBackend(self.s).url,'http://127.0.0.1:18002/v1')
    def test_private_lead_proposal_is_data_only_and_thinking_off(self):
        self.s['private_lead']['enabled']=True;calls=[];response={'kind':'FINAL','text':'synthetic'}
        def send(url,p=None,*args,**kw):
            if url.endswith('/models'): return {'data':[{'id':'sanctum-private-lead-qwen35-122b'}]}
            calls.append(p);return chat(canonical(response))
        result=PrivateLeadBackend(self.s,send).propose({'system':'synthetic','request':{'state':{}}})
        self.assertEqual(result['status'],'OK');self.assertEqual(result['result'],response);self.assertEqual(result['telemetry']['result_kind'],'FINAL');self.assertIn('elapsed_seconds',result['telemetry']);self.assertEqual(calls[0]['chat_template_kwargs'],{'enable_thinking':False});self.assertNotIn('tools',calls[0])
    def test_private_lead_proposal_refuses_invalid_request(self):
        with self.assertRaises(Refused):PrivateLeadBackend(self.s).propose({'request':{}})
    def test_answer_schema_no_authority_fields(self):
        with self.assertRaises(Refused):answer_result('{"answer":"run this","escalation":"NONE","execute":true}')
    def test_grounded_answer_schema_is_selected_for_profiled_evidence(self):
        sent=[];grounded={'kind':'GROUNDED_FINAL','text':'documented','grounding':'GROUNDED','citations':[{'sourceId':'s1','url':'https://example.test'}],'inferences':[],'missingReasons':[],'escalation':'NONE'}
        def send(url,p,headers,**kw):sent.append(p);return chat(canonical(grounded),self.s['models']['HOSTED_235B'])
        result=Remote(self.s,send,lambda:'test').infer('HOSTED_235B',{'prompt':'current','evidence':{'profile':'HOSTED_RICH'}},'grounded')
        self.assertEqual(result['grounded'],grounded);self.assertEqual(sent[0]['response_format']['json_schema']['schema']['properties']['kind']['enum'],['GROUNDED_FINAL'])

class FakeProvider:
    def ensure_guard(self):pass
    def __init__(self):self.rows=[];self.created=0;self.deleted=[];self.booted=False;self.fail_create=False;self.lost_response=False;self.available=True;self.fail_delete=False;self.calls=[]
    def pods(self):return copy.deepcopy(self.rows)
    def preflight(self):return {'available':self.available,'hourly_usd':2}
    def create(self,name):
        self.created+=1
        if self.fail_create:raise Refused('uncertain')
        self.rows=[{'id':'pod1','name':name}]
        if self.lost_response:raise Refused('uncertain')
        return self.rows[0]
    def delete(self,pod):
        self.deleted.append(pod)
        if not self.fail_delete:self.rows=[]
    def ssh_info(self,pod):return ('127.0.0.2',22)
    def ssh(self,*args):pass
    def bootstrap_server(self,*args):self.booted=True;self.calls.append('bootstrap')
    def server_alive(self,*args):
        if not self.booted:raise Refused('server_down')
    def tunnel(self,*args):self.calls.append('tunnel')
    def close_tunnel(self,*args):self.calls.append('tunnel_close')
class FakeBackend:
    def __init__(self):self.calls=[];self.fail=False
    def health_check(self,smoke=False):
        self.calls.append('health')
        if self.fail:raise Refused('not_ready')
    def infer(self,p):self.calls.append('infer');return {'status':'OK','text':'synthetic','escalation':'NONE'}
    def propose(self,p):self.calls.append('propose');return {'status':'OK','result':{'kind':'FINAL','text':'synthetic'}}
class Lifecycle(Temp):
    def setUp(self):
        super().setUp();self.time=1000;self.p=FakeProvider();self.b=FakeBackend();self.lc=Private80BLifecycle(self.s,self.p,self.b,lambda:self.time,self.advance)
    def advance(self,n):self.time+=n
    def test_capacity_rejection_recovers_without_duplicate_compute(self):
        original=self.p.create;attempts=[]
        def create(name):
            attempts.append(name)
            if len(attempts)==1:raise Refused('gpu_capacity_unavailable')
            return original(name)
        self.p.create=create
        self.lc.infer('a',{})
        self.assertEqual(len(attempts),2);self.assertEqual(self.p.created,1);self.assertEqual(self.lc.status()['phase'],'READY')
    def test_capacity_rejection_is_bounded_and_cancellable(self):
        self.s['gpu']['capacity_wait_seconds']=20
        def create(name):raise Refused('gpu_capacity_unavailable')
        self.p.create=create
        with self.assertRaisesRegex(Refused,'capacity_timeout'):self.lc.infer('a',{})
        self.assertFalse(self.lc.state()['allocation_uncertain']);self.assertIsNone(self.lc.state()['pod_id'])
        self.lc.sweep(manual=True)
        self.assertEqual(self.lc.status()['phase'],'OFFLINE')
        with self.assertRaisesRegex(Refused,'manual_stop'):self.lc.infer('a',{})
    def test_only_exact_create_capacity_rejection_is_retryable(self):
        e={'code':'graphql_error','error':'failed to create pod: graphql error: There are no longer any instances available with the requested specifications. Please refresh and try again.'}
        self.assertTrue(capacity_rejected(['pod','create'],e))
        self.assertFalse(capacity_rejected(['pod','list'],e))
        self.assertFalse(capacity_rejected(['pod','create'],{**e,'error':'timeout: '+e['error']}))
        self.assertFalse(capacity_rejected(['pod','create'],None))
    def test_create_ready_reuse_close_preserves_volume(self):
        self.lc.infer('a',{'prompt':'one'});self.lc.infer('a',{'prompt':'two'});self.assertEqual(self.p.created,1);self.assertEqual(self.lc.status()['phase'],'READY')
        self.lc.release('a',close=True);self.assertEqual(self.p.deleted,['pod1']);self.assertEqual(self.lc.status()['phase'],'OFFLINE');self.assertNotIn('delete_volume',dir(self.p))
    def test_new_allocation_clears_prior_allocation_telemetry(self):
        self.lc.save(self.lc.state(),ready_at=1,first_inference_at=2,last_inference_at=3,delete_requested_at=4,absent_confirmed_at=5,allocation_id='old')
        self.lc.infer('a',{})
        state=self.lc.state();self.assertEqual(state['allocation_id'],'pod1')
        self.assertIsNone(state['delete_requested_at']);self.assertIsNone(state['absent_confirmed_at'])
        self.assertEqual(state['ready_at'],self.time);self.assertIsNone(state['first_inference_at']);self.assertIsNone(state['last_inference_at'])
    def test_final_lease_only_terminates(self):
        self.lc.infer('a',{});self.lc.infer('b',{});self.lc.release('a',close=True);self.assertEqual(self.p.deleted,[]);self.lc.release('b',close=True);self.assertEqual(self.p.deleted,['pod1'])
    def test_close_during_query_deletes_as_final_request_releases(self):
        self.lc.acquire('a');self.lc.ensure_ready('a');self.lc.release('a',close=True)
        self.assertEqual(self.p.deleted,[])
        self.lc.release('a');self.assertEqual(self.p.deleted,['pod1'])
    def test_lost_create_response_adopted(self):
        self.p.lost_response=True;self.lc.infer('a',{});self.assertEqual(self.p.created,1);self.assertEqual(self.lc.status()['phase'],'READY')
    def test_uncertain_create_never_duplicates(self):
        self.p.fail_create=True
        for _ in range(2):
            with self.assertRaises(Refused):self.lc.infer('a',{})
        self.assertEqual(self.p.created,1)
    def test_crash_after_create_recovered(self):
        self.p.rows=[{'id':'pod1','name':'vinceai-qwen80b-phase10-intent'}]
        self.lc.save(self.lc.state(),pod_name=self.p.rows[0]['name'],allocation_uncertain=True,started_at=self.time,hourly_usd=2)
        self.lc.infer('a',{});self.assertEqual(self.p.created,0);self.assertTrue(self.p.booted)
    def test_stale_process_lease_and_idle_grace(self):
        self.lc.acquire('a');self.lc.ensure_ready('a');self.advance(91);self.lc.sweep();self.assertEqual(self.p.deleted,[]);self.advance(61);self.lc.sweep();self.assertEqual(self.p.deleted,['pod1'])
    def test_dead_session_lease_expires(self):
        self.lc.infer('a',{});self.advance(901);self.lc.sweep();self.advance(61);self.lc.sweep();self.assertEqual(self.p.deleted,['pod1'])
    def test_stop_blocks_autorestart(self):
        self.lc.infer('a',{});self.lc.sweep(manual=True)
        with self.assertRaises(Refused):self.lc.infer('a',{})
        self.assertEqual(self.p.created,1)
    def test_manual_stop_persists_while_lock_busy(self):
        with self.lc.lock():self.lc.sweep(manual=True)
        self.assertTrue((self.root/'manual-stop').exists())
        with self.assertRaises(Refused):self.lc.infer('a',{})
    def test_readiness_failure_never_queries_and_cleans(self):
        self.b.fail=True;self.s['gpu']['readiness_seconds']=10
        with self.assertRaises(Refused):self.lc.infer('a',{})
        self.assertNotIn('infer',self.b.calls);self.assertEqual(self.p.deleted,['pod1'])
    def test_delete_unconfirmed_not_offline(self):
        self.lc.infer('a',{});self.p.fail_delete=True
        with self.assertRaises(Refused):self.lc.release('a',close=True)
        self.assertEqual(self.lc.status()['phase'],'DEGRADED');self.assertEqual(self.lc.state()['pod_id'],'pod1')
    def test_external_delete_disables_restart(self):
        self.lc.infer('a',{});self.p.rows=[]
        with self.assertRaises(Refused):self.lc.infer('a',{})
        self.assertTrue(self.lc.state()['manual_stop']);self.assertEqual(self.p.created,1)
    def test_untracked_pod_refused(self):
        self.p.rows=[{'id':'other','name':'vinceai-qwen80b-manual'}]
        with self.assertRaises(Refused):self.lc.infer('a',{})
        self.assertEqual(self.p.created,0)
    def test_runtime_limit_closes_idle_leases(self):
        self.lc.infer('a',{});self.advance(7201);self.lc.sweep();self.assertEqual(self.p.deleted,['pod1']);self.assertTrue(self.lc.state()['manual_stop'])
    def test_concurrent_ensure_single_creation(self):
        errors=[]
        def run(scope):
            try:self.lc.infer(scope,{})
            except Exception as e:errors.append(e)
        threads=[threading.Thread(target=run,args=(str(i),)) for i in range(3)]
        for t in threads:t.start()
        for t in threads:t.join(5)
        self.assertFalse(errors);self.assertEqual(self.p.created,1)
    def test_lead_refuses_coexisting_80b_pod(self):
        self.s['private_lead']['enabled']=True; self.s['private_lead']['auto_start']=True
        self.p.rows=[{'id':'old','name':'vinceai-qwen80b-stage-existing'}]
        lead=PrivateLeadLifecycle(self.s,self.p,self.b,lambda:self.time,self.advance)
        with self.assertRaisesRegex(Refused,'untracked_or_duplicate_pod'): lead.infer('lead',{})
    def test_explicit_signed_lead_proposal_can_start_while_background_autostart_stays_off(self):
        self.s['private_lead']['enabled']=True;self.s['private_lead']['auto_start']=False
        lead=PrivateLeadLifecycle(self.s,self.p,self.b,lambda:self.time,self.advance)
        self.assertEqual(lead.propose('lead',{})['status'],'OK');self.assertEqual(self.p.created,1);self.assertIn('propose',self.b.calls)

class Janitor(Temp):
    def test_default_sweep_attempts_both_releases_without_one_masking_the_other(self):
        calls=[]
        class Fake:
            def __init__(self,release):self.release=release
            def sweep(self):
                calls.append(self.release)
                if self.release=='PRIVATE_80B':raise Refused('other_release_active')
            def status(self):return {'phase':'READY'}
        original=manage.lifecycle;manage.lifecycle=lambda _settings,release:Fake(release)
        self.addCleanup(setattr,manage,'lifecycle',original)
        result=manage.sweep_all(self.s)
        self.assertEqual(calls,list(manage.RELEASES));self.assertEqual(result['PRIVATE_80B']['phase'],'UNAVAILABLE');self.assertEqual(result['PRIVATE_LEAD']['phase'],'READY')

    def test_default_sweep_fails_if_neither_release_can_be_reconciled(self):
        class Fake:
            def sweep(self):raise Refused('provider_unavailable')
        original=manage.lifecycle;manage.lifecycle=lambda _settings,_release:Fake()
        self.addCleanup(setattr,manage,'lifecycle',original)
        with self.assertRaisesRegex(Refused,'janitor_all_releases_failed'):manage.sweep_all(self.s)

class Media(Temp):
    def test_image_strips_exif_and_no_source_path(self):
        from PIL import Image
        path=self.root/'private-name.jpg';im=Image.new('RGB',(20,20),'red');exif=Image.Exif();exif[270]='secret metadata';im.save(path,exif=exif)
        p=prepare([path],self.s);m=load(p['token'],p['digest'],'scope',self.s,bind=True)
        self.assertNotIn('private-name',canonical(m));self.assertNotIn('secret metadata',canonical(m));self.assertEqual(m['summary']['visual_count'],1)
    def test_scope_binding_and_hash_drift(self):
        path=self.root/'source.txt';path.write_text('synthetic');p=prepare([path],self.s);load(p['token'],p['digest'],'a',self.s,bind=True)
        with self.assertRaises(Refused):load(p['token'],p['digest'],'b',self.s,bind=True)
        with self.assertRaises(Refused):load(p['token'],'wrong','a',self.s)
    def test_expansion_is_explicit_only(self):
        path=self.root/'source.txt';path.write_text('private document');p=prepare([path],self.s);load(p['token'],p['digest'],'a',self.s,bind=True)
        self.assertEqual(expand({'prompt':'test'},'a',self.s),{'prompt':'test'})
        e=expand({'prompt':'test','media_ref':{'token':p['token'],'digest':p['digest']}},'a',self.s);self.assertEqual(e['documents'][0]['text'],'private document');self.assertNotIn('token',e)
    def test_unsupported_and_symlink(self):
        path=self.root/'source.html';path.write_text('<script>bad</script>')
        with self.assertRaises(Refused):prepare([path],self.s)
        link=self.root/'link.txt';link.symlink_to(path)
        with self.assertRaises(Refused):prepare([link],self.s)

class Installer(Temp):
    def setUp(self):
        super().setUp();self.config=self.root/'config.json';self.db=self.root/'webui.db';self.launch=self.root/'launch.plist';self.inst=self.root/'installed'
        previous_functions=install.FUNCTIONS
        self.addCleanup(setattr,install,'FUNCTIONS',previous_functions)
        install.FUNCTIONS={}
        for name,(relative,_) in previous_functions.items():
            previous=self.root/(name+'.py');previous.write_text('# synthetic previous '+name+'\n')
            install.FUNCTIONS[name]=(relative,previous)
        self.config.write_text(json.dumps({'plugins':{'load':{'paths':[install.OLD,'untouched']},'entries':{'hybrid-ai-prompt-gate':{'enabled':True}}},'secret':'fixture'}))
        with sqlite3.connect(self.db) as c:
            c.execute('create table function(id text primary key,content text,is_active integer,updated_at integer)')
            for name,(_,previous) in install.FUNCTIONS.items():c.execute('insert into function values (?,?,1,123)',(name,previous.read_text()))
    def do_install(self,hook=lambda _:None):return install.install(self.config,self.db,self.inst,self.launch,runner=lambda *a:None,verify=lambda:None,hook=hook)
    def rollback(self):return install.rollback(self.inst,runner=lambda *a:None,gpu_check=lambda:None)
    def test_install_and_rollback_preserves_unrelated(self):
        self.do_install();cfg=json.loads(self.config.read_text());cfg['new_setting']=42;cfg['plugins']['load']['paths'].append('another');self.config.write_text(json.dumps(cfg));self.rollback();cfg=json.loads(self.config.read_text());self.assertEqual(cfg['new_setting'],42);self.assertEqual(cfg['secret'],'fixture');self.assertIn('another',cfg['plugins']['load']['paths']);self.assertIn(install.OLD,cfg['plugins']['load']['paths']);self.assertFalse(self.launch.exists())
    def test_crash_every_install_boundary_is_recoverable(self):
        for boundary in ['prepared','config','database','launch_file','launch_loaded']:
            with self.subTest(boundary=boundary):
                def fail(stage):
                    if stage==boundary:raise RuntimeError('crash')
                with self.assertRaises(RuntimeError):self.do_install(fail)
                self.rollback();self.assertIn(install.OLD,json.loads(self.config.read_text())['plugins']['load']['paths'])
    def test_baseline_drift_refuses_before_mutation(self):
        with sqlite3.connect(self.db) as c:c.execute("update function set content='changed'")
        before=self.config.read_bytes()
        with self.assertRaises(Refused):self.do_install()
        self.assertEqual(before,self.config.read_bytes())
    def test_rollback_refuses_changed_gate(self):
        self.do_install()
        with sqlite3.connect(self.db) as c:c.execute("update function set content='new user change'")
        with self.assertRaises(Refused):self.rollback()
    def test_rollback_keeps_janitor_when_compute_uncertain(self):
        self.do_install()
        def refuse():raise Refused('still_running')
        with self.assertRaises(Refused):install.rollback(self.inst,gpu_check=refuse)
        self.assertTrue(self.launch.exists())

if __name__=='__main__':unittest.main()

class IsolatedTunnel(Temp):
    def test_private_lead_guard_uses_release_specific_state_root(self):
        from runpod import Runpod
        self.assertEqual(Runpod(self.s).guard_root(),self.root)
        self.assertEqual(Runpod(self.s,self.s['private_lead']).guard_root(),self.root/'private-lead')

    def test_private_backend_and_ssh_use_the_same_loopback_port(self):
        from runpod import Runpod
        from unittest.mock import patch
        from types import SimpleNamespace
        self.s['gpu']['local_port']=28001
        self.assertEqual(Private80BBackend(self.s).url,'http://127.0.0.1:28001/v1')
        provider=Runpod(self.s)
        with patch.object(provider,'socket_path',return_value=str(self.root/'test.sock')), patch.object(provider,'ssh_args',return_value=['ssh']), patch('runpod.subprocess.run',side_effect=[SimpleNamespace(returncode=1),SimpleNamespace(returncode=0)]) as run:
            provider.tunnel('synthetic-pod','192.0.2.1',22)
        args=run.call_args.args[0]
        self.assertEqual(args[args.index('-L')+1],'127.0.0.1:28001:127.0.0.1:8000')
    def test_invalid_tunnel_port_never_reaches_a_transport(self):
        from runpod import Runpod
        for value in [True,0,80,65536,'28001']:
            self.s['gpu']['local_port']=value
            with self.assertRaises(Refused):Private80BBackend(self.s)
            with self.assertRaises(Refused):Runpod(self.s)
