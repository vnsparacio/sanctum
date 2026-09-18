"""Synthetic invariants; no provider, personal repository or inference calls."""
import copy,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'src'))
from common import Refused
from task_evidence import snapshot,check,validate_contract,unrestricted_contract,acceptance_view,patch_allowed,patch_assessment,execute_original
from workspace import apply_patch
from command_runner import run

ORIGINAL="import test from 'node:test';import assert from 'node:assert/strict';import {value} from './value.js';test('independent oracle',()=>assert.equal(value,17));\n"
WEAKENED=ORIGINAL.replace('assert.equal(value,17)','assert.equal(value,Number(value))')
FABRICATED_EVENT="""import fs from 'node:fs';import {DefaultSerializer} from 'node:v8';
const s=new DefaultSerializer();s.writeHeader();const h=s.releaseBuffer().length;
s.writeHeader();s.writeRawBytes(Buffer.alloc(4));s.writeHeader();
s.writeValue({type:'test:pass',data:{name:'independent oracle',file:'/workspace/oracle.test.js',line:1,column:1,nesting:0,testNumber:1,details:{duration_ms:1,type:'test'}}});
const raw=s.releaseBuffer();raw.writeUInt32BE(raw.length-4-h,h);fs.writeSync(1,raw);process.exit(0);
export const value=99;
"""
def contract():
 return {'schema':'sanctum-task-protection/v1','protected':['oracle.test.js','package.json'],'mutable':['value.js'],'mutable_tests':['candidate.test.js'],'allow_new':True,'acceptance':{'runner':'node-test-v1','entries':[{'path':'oracle.test.js','names':['independent oracle']}]}}

class EvidenceFixture:
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve();self.root=self.base/'workspace';self.root.mkdir()
  (self.root/'value.js').write_text('export const value=17;\n');(self.root/'oracle.test.js').write_text(ORIGINAL);(self.root/'package.json').write_text('{"type":"module"}\n');(self.root/'candidate.test.js').write_text("import test from 'node:test';test('candidate',()=>{});\n")
  self.settings={'state_directory':str(self.base/'state')};self.record={'workspace_id':'a'*32,'root':str(self.root),'profile':'test'}
  subprocess.run(['git','init','-q'],cwd=self.root,check=True)
  self.policy=contract();snapshot(self.settings,self.record,self.policy)
 def tearDown(self):self.tmp.cleanup()

class Evidence(EvidenceFixture,unittest.TestCase):
 def test_snapshot_binding_and_originals_are_outside_writable_workspace(self):
  result=check(self.settings,self.record);self.assertEqual(result['integrity'],'PASS');self.assertEqual(result['taskId'],'a'*32)
  evidence=self.base/'state/private-lead/work-mode/evidence'/('a'*32)
  self.assertFalse(evidence.is_relative_to(self.root));self.assertTrue(all(p.stat().st_mode&0o222==0 for p in evidence.iterdir()))
  for mutation in [{'workspace_id':'b'*32},{'protection_digest':'0'*64},{'root':str(self.base)}]:
   with self.assertRaises((Refused,OSError)):check(self.settings,{**self.record,**mutation})
 def test_direct_overwrite_is_latched_even_after_restoration(self):
  p=self.root/'oracle.test.js';p.write_text(WEAKENED);self.assertEqual(check(self.settings,self.record)['integrity'],'FAIL');p.write_text(ORIGINAL);self.assertEqual(check(self.settings,self.record)['integrity'],'FAIL')
 def test_delete_recreate_rename_links_modes_and_staging_cannot_hide_changes(self):
  operations={
   'delete_recreate':lambda p:(p.unlink(),p.write_text(WEAKENED)),
   'rename':lambda p:p.rename(p.with_name('renamed.test.js')),
   'symlink':lambda p:(p.unlink(),p.symlink_to(self.root/'value.js')),
   'hardlink':lambda p:(p.unlink(),os.link(self.root/'value.js',p)),
   'mode':lambda p:p.chmod(0o755),
   'directory':lambda p:(p.unlink(),p.mkdir()),
   'case':lambda p:p.rename(p.with_name('ORACLE.test.js')),
   'generated':lambda p:(p.with_suffix('.new').write_text(WEAKENED),os.replace(p.with_suffix('.new'),p)),
   'staged':lambda p:(p.write_text(WEAKENED),subprocess.run(['git','add','.'],cwd=p.parent,check=True,capture_output=True)),
  }
  for name,change in operations.items():
   with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
    r=Path(d).resolve()/'work';shutil.copytree(self.root,r);subprocess.run(['git','init','-q'],cwd=r,check=True)
    rec={'workspace_id':'b'*32,'root':str(r),'profile':'test'};settings={'state_directory':str(Path(d).resolve()/'state')};snapshot(settings,rec,self.policy);change(r/'oracle.test.js');self.assertEqual(check(settings,rec)['integrity'],'FAIL')
 def test_unicode_and_ambiguous_protected_contracts_fail_closed(self):
  for bad in ['../oracle.test.js','./oracle.test.js','/oracle.test.js','a//b','.GIT/config','x\\y','e\u0301.test.js']:
   v=contract();v['protected'].append(bad)
   with self.subTest(path=bad),self.assertRaises(Refused):validate_contract(v)
  v=contract();v['protected'].append('ORACLE.TEST.JS')
  with self.assertRaises(Refused):validate_contract(v)
  (self.root/'ORACLE.TEST.JS').write_text('alias')
  self.assertEqual(check(self.settings,self.record)['integrity'],'FAIL')
 def test_explicit_mutable_tests_and_new_regressions_are_allowed(self):
  (self.root/'candidate.test.js').write_text("import test from 'node:test';test('expanded',()=>{});\n");(self.root/'new.test.js').write_text("import test from 'node:test';test('new',()=>{});\n")
  self.assertEqual(check(self.settings,self.record)['integrity'],'PASS')
  with acceptance_view(self.settings,self.record) as (view,acceptance,facts):
   self.assertEqual((view/'oracle.test.js').read_text(),ORIGINAL);self.assertTrue((view/'new.test.js').exists());self.assertEqual(facts['integrity'],'PASS')
 def test_mutability_and_absence_are_host_selected_not_test_filename_heuristics(self):
  with tempfile.TemporaryDirectory() as d:
   settings={'state_directory':str(Path(d)/'state')};rec={**self.record,'workspace_id':'c'*32};v=contract();v['protected'].append('missing.json');v['allow_new']=False;snapshot(settings,rec,v)
   (self.root/'missing.json').write_text('{}');self.assertEqual(check(settings,rec)['integrity'],'FAIL')
 def test_changed_nonmutable_implementation_and_snapshot_tampering_refuse(self):
  (self.root/'undeclared.txt').write_text('original')
  # New files are allowed, but an existing nonmutable file is not silently mutable.
  with tempfile.TemporaryDirectory() as d:
   settings={'state_directory':str(Path(d)/'state')};rec={**self.record,'workspace_id':'d'*32};snapshot(settings,rec,contract());(self.root/'undeclared.txt').write_text('changed');self.assertEqual(check(settings,rec)['integrity'],'FAIL')
  blob=next((self.base/'state/private-lead/work-mode/evidence'/('a'*32)).glob('*.blob'));blob.chmod(0o600);blob.write_text('tamper')
  with self.assertRaises(Refused):check(self.settings,self.record)
 def test_protected_patch_rejected_before_mutation_and_legal_patch_preserved(self):
  patch='--- a/oracle.test.js\n+++ b/oracle.test.js\n@@ -1 +1 @@\n-'+ORIGINAL+'+'+WEAKENED
  self.assertFalse(patch_allowed(self.settings,self.record,patch));self.assertEqual(patch_assessment(self.settings,self.record,patch),'WORKSPACE_PROTECTED_INPUT');self.assertEqual(check(self.settings,self.record)['integrity'],'PASS')
  legal='--- a/value.js\n+++ b/value.js\n@@ -1 +1 @@\n-export const value=17;\n+export const value=18;\n'
  self.assertTrue(patch_allowed(self.settings,self.record,legal));self.assertEqual(patch_assessment(self.settings,self.record,legal),'PASS');self.assertTrue(apply_patch(self.root,legal)['ok'])
  self.assertEqual(check(self.settings,self.record)['integrity'],'PASS')
 def test_malformed_patch_has_distinct_retryable_classification(self):
  malformed='--- a/value.js\n+++ b/value.js\nthis is not a unified-diff hunk\n'
  self.assertFalse(patch_allowed(self.settings,self.record,malformed));self.assertEqual(patch_assessment(self.settings,self.record,malformed),'WORKSPACE_PATCH_INVALID')
  self.assertEqual(check(self.settings,self.record)['integrity'],'PASS')
 def test_rename_mode_and_creation_patches_cannot_change_protected_identity(self):
  for patch in [
   'diff --git a/oracle.test.js b/moved.test.js\nsimilarity index 100%\nrename from oracle.test.js\nrename to moved.test.js\n',
   'diff --git a/oracle.test.js b/oracle.test.js\nold mode 100644\nnew mode 100755\n',
   'diff --git a/ORACLE.TEST.JS b/ORACLE.TEST.JS\nnew file mode 100644\n--- /dev/null\n+++ b/ORACLE.TEST.JS\n@@ -0,0 +1 @@\n+replacement\n',
  ]:
   with self.subTest(patch=patch):self.assertFalse(patch_allowed(self.settings,self.record,patch))
  self.assertEqual(check(self.settings,self.record)['integrity'],'PASS')
 def test_host_evidence_operations_require_signed_exact_task_and_one_use_nonce(self):
  import hashlib,hmac,sqlite3
  from authority import authorize
  from common import canonical,private_dir
  Path(self.settings['state_directory']).chmod(0o700)
  keyfile=private_dir(Path(self.settings['state_directory']))/'authority.key';keyfile.write_bytes(b'k'*32);keyfile.chmod(0o600)
  for operation in ('worktree_integrity','worktree_acceptance'):
   body={'operation':operation,'tier':'PRIVATE_LEAD','packet':{'task_id':'a'*32,'profile':'test'},'state':{'scope':'a'*32,'revision':0,'privacy_floor':'PERSONAL','high_stakes':False},'nonce':hashlib.sha256(operation.encode()).hexdigest(),'expires':200,'spec_sha256':'a'*64,'scope':'a'*32,'approval':'private_lead_workmode','strong':False}
   def signed(value):
    raw=canonical(value);return {'body':raw,'mac':hmac.new(keyfile.read_bytes(),raw.encode(),hashlib.sha256).hexdigest()}
   for change in [{'packet':{**body['packet'],'acceptance':{}}},{'packet':{**body['packet'],'task_id':'b'*32}},{'approval':'model_grant'},{'tier':'PRIVATE_80B'}]:
    with self.assertRaises(Refused):authorize(signed({**body,**change}),self.settings,now=lambda:100,settings_hash='a'*64)
   forged=signed(body);forged['mac']='0'*64
   with self.assertRaises(Refused):authorize(forged,self.settings,now=lambda:100,settings_hash='a'*64)
   self.assertEqual(authorize(signed(body),self.settings,now=lambda:100,settings_hash='a'*64)['operation'],operation)
   with self.assertRaises(sqlite3.IntegrityError):authorize(signed(body),self.settings,now=lambda:100,settings_hash='a'*64)

class ContainedEvidence(EvidenceFixture,unittest.TestCase):
 def setUp(self):
  super().setUp();docker=shutil.which('docker')
  if not docker:self.skipTest('Docker CLI unavailable')
  try:
   image=subprocess.check_output([docker,'image','inspect','--format','{{.Id}}','sanctum-work-runner:project3g'],text=True).strip();context=json.loads(subprocess.check_output([docker,'context','inspect'],text=True))
  except subprocess.SubprocessError:self.skipTest('Pinned contained runner unavailable')
  profile={'docker_path':str(Path(docker).resolve()),'docker_host':context[0]['Endpoints']['docker']['Host'],'runner_image':'sanctum-work-runner:project3g','runner_image_id':image,'runner_user':f'{os.getuid()}:{os.getgid()}','platform':'linux/arm64','timeout_seconds':15,'operations':{'test':['node','--test']}}
  config=self.base/'profiles.json';config.write_text(json.dumps({'profiles':{'test':profile}}));config.chmod(0o600);self.settings['work_mode']={'profile_file':str(config)}
 def test_private_installed_driver_permissions_remain_executable_in_container(self):
  from unittest.mock import patch
  import command_runner
  installed=self.base/'installed';(installed/'runtime').mkdir(parents=True)
  for name in ('work-runner.json','protected-test-driver.cjs','protected-test-preload.cjs'):
   target=installed/'runtime'/name;shutil.copyfile(BASE/'runtime'/name,target);target.chmod(0o600)
  with patch.object(command_runner,'BASE',installed):self.assertTrue(execute_original(self.settings,self.record)['passed'])
 def test_live_finding_negative_control_and_correct_solution(self):
  self.assertTrue(execute_original(self.settings,self.record)['passed'])
  (self.root/'oracle.test.js').write_text(WEAKENED);self.assertTrue(run(self.settings,'test',self.root,'test')['ok'])
  (self.root/'value.js').write_text('export const value=99;\n');self.assertTrue(run(self.settings,'test',self.root,'test')['ok'])
  # Original-evidence execution is demonstrated in a separate diagnostic view;
  # the task itself is irreversibly refused after its protected edit.
  self.assertEqual(check(self.settings,self.record)['integrity'],'FAIL')
  with self.assertRaises(Refused):execute_original(self.settings,self.record)
  with tempfile.TemporaryDirectory() as d:
   view=Path(d);shutil.copytree(self.root,view,dirs_exist_ok=True);(view/'oracle.test.js').write_text(ORIGINAL)
   result=run(self.settings,'test',view,'test',acceptance=contract()['acceptance']);self.assertFalse(result['ok']);self.assertTrue(result['protected_execution']['executed'])
 def test_fixed_original_entrypoints_ignore_scripts_discovery_and_false_output(self):
  # Candidate discovery can be disabled in the profile without disabling originals.
  cfg=Path(self.settings['work_mode']['profile_file']);v=json.loads(cfg.read_text());v['profiles']['test']['operations']['test']=['node','-e','process.exit(0)'];cfg.write_text(json.dumps(v))
  (self.root/'value.js').write_text('export const value=99;\n');self.assertTrue(run(self.settings,'test',self.root,'test')['ok'])
  result=execute_original(self.settings,self.record);self.assertFalse(result['passed']);self.assertTrue(result['executed'])
  (self.root/'value.js').write_text("console.log('TAP version 13\\n1..1\\nok 1 - independent oracle');process.exit(0);export const value=99;\n")
  result=execute_original(self.settings,self.record);self.assertFalse(result['passed']);self.assertFalse(result['executed'])
 def test_serialized_node_event_cannot_fabricate_protected_execution(self):
  (self.root/'value.js').write_text(FABRICATED_EVENT)
  result=execute_original(self.settings,self.record)
  self.assertFalse(result['executed']);self.assertFalse(result['passed']);self.assertEqual(result['code'],'PROTECTED_TEST_NOT_EXECUTED')
 def test_authenticated_proof_ignores_normal_output_and_rejects_injection(self):
  (self.root/'value.js').write_text("console.log('ordinary candidate output');console.error('ordinary candidate error');export const value=17;\n")
  result=execute_original(self.settings,self.record);self.assertTrue(result['executed']);self.assertTrue(result['passed'])
  (self.root/'value.js').write_text("console.error('SANCTUM_PROTECTED_PROOF_V1 e30= "+'0'*64+"');export const value=17;\n")
  result=execute_original(self.settings,self.record);self.assertFalse(result['passed']);self.assertEqual(result['code'],'PROTECTED_TEST_NOT_EXECUTED')
 def test_skipped_missing_failed_and_early_originals_fail_closed(self):
  cases=[
   ('skipped',ORIGINAL.replace("test('independent oracle'","test.skip('independent oracle'"),'export const value=17;\n',False,False),
   ('missing',ORIGINAL.replace('independent oracle','different name'),'export const value=17;\n',False,False),
   ('failed',ORIGINAL,'export const value=99;\n',True,False),
   ('early',ORIGINAL,"process.exit(0);export const value=17;\n",False,False),
  ]
  for index,(name,oracle,implementation,executed,passed) in enumerate(cases):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
    root=Path(d)/'workspace';shutil.copytree(self.root,root);(root/'oracle.test.js').write_text(oracle);(root/'value.js').write_text(implementation)
    settings={**self.settings,'state_directory':str(Path(d)/'state')};record={'workspace_id':str(index+1)*32,'root':str(root),'profile':'test'};snapshot(settings,record,contract())
    result=execute_original(settings,record);self.assertEqual(result['executed'],executed);self.assertEqual(result['passed'],passed)
 def test_candidate_changes_do_not_mutate_host_and_test_additions_still_execute(self):
  (self.root/'candidate.test.js').write_text("import test from 'node:test';import fs from 'node:fs';test('candidate update',()=>fs.writeFileSync('oracle.test.js','changed inside container'));\n")
  self.assertFalse(run(self.settings,'test',self.root,'test')['ok']);self.assertEqual(check(self.settings,self.record)['integrity'],'PASS')
  self.assertTrue(execute_original(self.settings,self.record)['passed'])
  (self.root/'candidate.test.js').write_text("import test from 'node:test';test('legitimate update',()=>{});\n")
  (self.root/'new.test.js').write_text("import test from 'node:test';import assert from 'node:assert/strict';test('added regression',()=>assert.equal(2+2,4));\n")
  self.assertTrue(run(self.settings,'test',self.root,'test')['ok']);self.assertTrue(execute_original(self.settings,self.record)['passed'])
 def test_missing_moved_wrong_import_and_config_targets_do_not_pass_originals(self):
  (self.root/'value.js').unlink();(self.root/'elsewhere.js').write_text('export const value=17;\n')
  self.assertFalse(execute_original(self.settings,self.record)['passed'])
  (self.root/'value.js').write_text("export {value} from './wrong.js';\n");(self.root/'wrong.js').write_text('export const value=99;\n')
  self.assertFalse(execute_original(self.settings,self.record)['passed'])
  (self.root/'package.json').write_text('{"type":"commonjs","scripts":{"test":"true"}}')
  self.assertEqual(check(self.settings,self.record)['integrity'],'FAIL')
 def test_implementation_cannot_replace_assertions_or_test_api(self):
  attacks=["import assert from 'node:assert/strict';assert.equal=()=>{};", "import test from 'node:test';test.skip=()=>{};", "import {createRequire} from 'node:module';const require=createRequire(import.meta.url);require('node:assert').strict.equal=()=>{};"]
  for attack in attacks:
   with self.subTest(attack=attack):
    (self.root/'value.js').write_text(attack+'export const value=99;\n');result=execute_original(self.settings,self.record);self.assertFalse(result['passed']);self.assertEqual(result['integrity'],'PASS')

if __name__=='__main__':unittest.main()
