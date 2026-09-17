from pathlib import Path
from types import SimpleNamespace
import functools,hashlib,importlib.util,json,shutil,sys,tempfile,unittest

BASE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(BASE/'src'),str(BASE)]

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

qualification=load('qualification_under_test',BASE/'qualify_work_mode.py')
probe=load('probe_under_test',BASE/'probe_work_intent.py')

class GatewayQualificationReadiness(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name);self.source=root/'source';self.prefix=root/'candidate';(self.source/'scripts').mkdir(parents=True);(self.source/'scripts/release_operator.py').write_text('synthetic\n');(self.prefix/'gate').mkdir(parents=True);(self.prefix/'gate/SETTINGS.json').write_text(json.dumps({'python':sys.executable}));(self.prefix/'receipt.json').write_text(json.dumps({'source':str(self.source)}));self.calls=[]
 def report(self,**changes):
  value={'source_integrity':'pass','runtime_pins':'pass','configuration_integrity':'pass','gateway_running':True,'gateway_identity':'match','gateway_health':'pass'};value.update(changes);return value
 def runner(self,doctor=None,up=0):
  report=doctor or self.report()
  def call(args,env,timeout=120):
   self.calls.append(args);return SimpleNamespace(returncode=up if 'up' in args else 0,stdout=json.dumps(report) if 'doctor' in args else '',stderr='')
  return call
 def readiness(self,**kwargs):
  return functools.partial(qualification.qualification_readiness,runner=self.runner(**kwargs),bridge_invoke=lambda *a,**k:qualification.WORK_HELP)
 def test_stopped_gateway_restart_failure_blocks_before_fixtures(self):
  seeded=[]
  with self.assertRaises(qualification.GatewayReadinessError) as caught:
   qualification.prepare(self.prefix,'node','bridge',{},readiness=self.readiness(up=1),schema_preflight=lambda *_:self.fail('schema preflight ran'),seed_fixtures=lambda *_:seeded.append(True))
  self.assertEqual(caught.exception.code,'GATEWAY_RESTART_FAILED');self.assertEqual(seeded,[])
 def test_supported_workflow_restarts_gateway_then_checks_doctor(self):
  result=self.readiness()(self.prefix,'node','bridge',{})
  self.assertEqual(result['workCommand'],'READY');self.assertIn('up',self.calls[0]);self.assertIn('doctor',self.calls[1]);self.assertTrue(all('manage.py' not in ' '.join(call) for call in self.calls))
 def test_unhealthy_gateway_blocks_qualification(self):
  with self.assertRaises(qualification.GatewayReadinessError) as caught:self.readiness(doctor=self.report(gateway_health='fail'))(self.prefix,'node','bridge',{})
  self.assertEqual(caught.exception.code,'GATEWAY_UNHEALTHY')
 def test_stale_or_wrong_gateway_identity_blocks_qualification(self):
  for identity in ('stale','stopped',None):
   with self.subTest(identity=identity):
    with self.assertRaises(qualification.GatewayReadinessError) as caught:self.readiness(doctor=self.report(gateway_identity=identity))(self.prefix,'node','bridge',{})
    self.assertEqual(caught.exception.code,'GATEWAY_IDENTITY_MISMATCH')
 def test_missing_work_command_blocks_qualification(self):
  ready=functools.partial(qualification.qualification_readiness,runner=self.runner(),bridge_invoke=lambda *a,**k:'Unknown command')
  with self.assertRaises(qualification.GatewayReadinessError) as caught:ready(self.prefix,'node','bridge',{})
  self.assertEqual(caught.exception.code,'WORK_COMMAND_UNAVAILABLE')
 def test_authenticated_bridge_failure_blocks_qualification(self):
  def failed(*args,**kwargs):raise RuntimeError('private transport detail')
  ready=functools.partial(qualification.qualification_readiness,runner=self.runner(),bridge_invoke=failed)
  with self.assertRaises(qualification.GatewayReadinessError) as caught:ready(self.prefix,'node','bridge',{})
  self.assertEqual(caught.exception.code,'GATEWAY_BRIDGE_FAILED')
 def test_successful_readiness_precedes_schema_and_fixture_creation(self):
  order=[]
  gateway,schemas,root=qualification.prepare(self.prefix,'node','bridge',{},readiness=lambda *a:order.append('gateway') or {'status':'ready'},schema_preflight=lambda *a:order.append('schemas') or {'status':'ready'},seed_fixtures=lambda *a:order.append('fixtures') or 'root')
  self.assertEqual(order,['gateway','schemas','fixtures']);self.assertEqual((gateway,schemas,root),({'status':'ready'},{'status':'ready'},'root'))
 def test_failure_receipt_is_content_minimized(self):
  path=qualification.record_readiness_failure(self.prefix,qualification.GatewayReadinessError('GATEWAY_UNHEALTHY'));value=json.loads(Path(path).read_text())
  self.assertEqual(set(value),{'schema','status','classification','reason','code','createdAt'});self.assertEqual(value['classification'],'HARNESS');self.assertNotIn('private transport detail',json.dumps(value))

class QualificationContracts(unittest.TestCase):
 def test_every_unchanged_case_has_explicit_minimum_oracle_contract(self):
  from task_evidence import validate_contract
  for name,_,_ in (*qualification.CASES,qualification.ADVERSARIAL):
   contract=validate_contract(qualification.protection_contract(name));self.assertEqual(contract['protected'],['index.test.js','package.json']);self.assertEqual(contract['mutable'],'*');self.assertTrue(contract['allow_new'])
   for entry in contract['acceptance']['entries']:
    self.assertIn(entry['path'],qualification.FILES[name])
    for test_name in entry['names']:self.assertIn("test('"+test_name+"'",qualification.FILES[name][entry['path']])
 def test_terminal_status_cannot_hide_missing_or_failed_host_evidence(self):
  facts={'protectedIntegrity':'PASS','originalExecuted':True,'originalPassed':True,'candidateExecuted':True,'candidatePassed':True,'evaluatorPassed':True}
  self.assertTrue(qualification.protection_passed('COMPLETE',facts))
  for key in facts:
   value={**facts,key:'FAIL' if key=='protectedIntegrity' else False};self.assertFalse(qualification.protection_passed('COMPLETE',value))
  for terminal in ['BLOCKED','NEEDS_APPROVAL']:
   self.assertTrue(qualification.protection_passed(terminal,{**facts,'originalExecuted':False}));self.assertFalse(qualification.protection_passed(terminal,{**facts,'protectedIntegrity':'FAIL'}))
 def test_missing_or_modified_profile_contract_refuses_before_live_run(self):
  with tempfile.TemporaryDirectory() as d:
   prefix=Path(d);(prefix/'config').mkdir();path=prefix/'config/work-mode.json';profiles={name:{'task_protection':qualification.protection_contract(name)} for name in qualification.PROTECTED_CASES}
   path.write_text(json.dumps({'profiles':profiles}));qualification.validate_protection_profiles(prefix)
   profiles['grade06']['task_protection']['protected']=[];path.write_text(json.dumps({'profiles':profiles}))
   with self.assertRaises(RuntimeError):qualification.validate_protection_profiles(prefix)
 def test_graded_fixtures_and_expected_outcomes_are_unchanged(self):
  payload={'cases':qualification.CASES,'adversarial':qualification.ADVERSARIAL,'files':qualification.FILES};digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  self.assertEqual(digest,'e67ed7a5798f3fdae524ba5f570021f6a7b7874d54cb725b1feffeaa308aa831');self.assertEqual(len(qualification.CASES)+1,11)
 def test_exact_schema_probe_surfaces_and_generation_requests_are_unchanged(self):
  self.assertEqual(probe.SURFACES,('ordinaryIneligible','ordinaryEligible','researchIneligible','researchEligible','testOnlyIneligible','reviewer'))
  node=shutil.which('node');self.assertIsNotNone(node)
  for surface in probe.SURFACES:
   request,manifest=probe.production_request(node,surface);self.assertEqual(request['schemaDigest'],hashlib.sha256(json.dumps(request['schema'],sort_keys=True,separators=(',',':')).encode()).hexdigest());self.assertEqual(len(manifest),64)

if __name__=='__main__':unittest.main()
