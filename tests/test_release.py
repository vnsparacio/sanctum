from pathlib import Path
import importlib.util,json,os,tempfile,unittest,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('operator_tools',ROOT/'scripts/operator.py');op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)
class Setup(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.prefix=Path(self.tmp.name).resolve()/'install'
 def test_idempotent_private_isolated_configuration(self):
  op.setup(self.prefix);before=(self.prefix/'config/openclaw.json').read_bytes();op.setup(self.prefix)
  self.assertEqual(before,(self.prefix/'config/openclaw.json').read_bytes());op.verify_install(self.prefix)
  cfg=json.loads(before);self.assertEqual(cfg['tools']['profile'],'minimal');self.assertIn('exec',cfg['tools']['deny']);self.assertEqual(cfg['gateway']['bind'],'loopback')
  self.assertFalse(json.loads((self.prefix/'gate/SETTINGS.json').read_text())['gpu']['auto_start'])
  self.assertEqual((self.prefix/'state/gate/authority.key').stat().st_mode&0o777,0o600)
  self.assertEqual((self.prefix/'config/contacts.json').read_text(),'{}\n')
  self.assertEqual(op.environment(self.prefix)['VINCEAI_MCP_INPUT_DIR'],str(self.prefix/'mcp-input'))
 def test_drift_refuses_without_overwrite(self):
  op.setup(self.prefix);p=self.prefix/'config/openclaw.json';p.write_text('{}');
  with self.assertRaises(ValueError):op.setup(self.prefix)
  self.assertEqual(p.read_text(),'{}')
 def test_nonempty_prefix_is_preserved(self):
  self.prefix.mkdir(mode=0o700);p=self.prefix/'keep';p.write_text('owned')
  with self.assertRaises(ValueError):op.setup(self.prefix)
  self.assertEqual(p.read_text(),'owned')
 def test_symlink_and_broad_permissions_rejected(self):
  target=self.prefix.parent/'target';target.mkdir(mode=0o700);self.prefix.symlink_to(target,target_is_directory=True)
  with self.assertRaises(ValueError):op.private(self.prefix)
  self.prefix.unlink();self.prefix.mkdir(mode=0o755)
  with self.assertRaises(ValueError):op.private(self.prefix)
 def test_offline_timer_state_does_not_prevent_local_shutdown(self):
  op.setup(self.prefix);p=self.prefix/'state/gate/gpu.json';p.write_text(json.dumps({'phase':'OFFLINE','pod_id':None,'pod_name':None}))
  op.down(self.prefix)
  p.write_text(json.dumps({'phase':'OFFLINE','pod_id':None,'allocation_uncertain':True}))
  with self.assertRaises(ValueError):op.down(self.prefix)
 def test_no_gate_template_left_in_rendered_paths(self):
  op.setup(self.prefix)
  for n in ['SETTINGS.json','webui/pipe.py','webui/bridge.mjs']:
   text=(self.prefix/'gate'/n).read_text()
   self.assertNotIn('@GATE@',text);self.assertNotIn('@PYTHON@',text)
 def test_component_does_not_adopt_an_executable_from_path(self):
  op.setup(self.prefix)
  bin_dir=self.prefix/'fake-bin';bin_dir.mkdir()
  fake=bin_dir/'mlx_lm.server';fake.write_text('#!/bin/sh\necho SHOULD_NOT_RUN\n');fake.chmod(0o700)
  result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/component.py'),'mlx','--prefix',str(self.prefix)],env={**os.environ,'PATH':str(bin_dir)+os.pathsep+os.environ['PATH']},capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertIn('bootstrap.py mlx',result.stderr);self.assertNotIn('SHOULD_NOT_RUN',result.stdout)
 def test_bootstrap_preserves_existing_runtime(self):
  op.setup(self.prefix);runtime=self.prefix/'runtime/webui';runtime.mkdir(parents=True);marker=runtime/'owned';marker.write_text('preserve')
  result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/bootstrap.py'),'webui','--prefix',str(self.prefix)],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertIn('Nothing overwritten',result.stderr);self.assertEqual(marker.read_text(),'preserve')
if __name__=='__main__':unittest.main()

class Amendments(unittest.TestCase):
 setUp=Setup.setUp
 def test_bounded_amendment_and_rollback(self):
  spec=importlib.util.spec_from_file_location('configure_tools',ROOT/'scripts/configure.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  op.setup(self.prefix);before=(self.prefix/'config/openclaw.json').read_bytes()
  mod.configure(self.prefix,{'integrations':['messages','files'],'contacts':{'Alex Example':123}})
  op.verify_install(self.prefix);cfg=json.loads((self.prefix/'config/openclaw.json').read_text());self.assertIn('steward_move',cfg['tools']['alsoAllow']);self.assertIn('exec',cfg['tools']['deny'])
  self.assertEqual((self.prefix/'config/messages.enabled').read_text(),'enabled\n')
  log=next((self.prefix/'state/amendments').iterdir());mod.rollback(self.prefix,log);op.verify_install(self.prefix)
  self.assertEqual(before,(self.prefix/'config/openclaw.json').read_bytes())
 def test_unknown_authority_field_is_rejected_without_mutation(self):
  spec=importlib.util.spec_from_file_location('configure_tools',ROOT/'scripts/configure.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  op.setup(self.prefix);before=(self.prefix/'receipt.json').read_bytes()
  with self.assertRaises(ValueError):mod.configure(self.prefix,{'tools':['exec']})
  with self.assertRaises(ValueError):mod.configure(self.prefix,{'integrations':['shell']})
  self.assertEqual(before,(self.prefix/'receipt.json').read_bytes())

class Publication(unittest.TestCase):
 def test_finder_metadata_is_rejected(self):
  spec=importlib.util.spec_from_file_location('publication_audit',ROOT/'scripts/audit.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);(base/'.DS_Store').write_bytes(b'\x00\x80metadata')
   self.assertIn(('.DS_Store','private/generated Finder metadata'),audit.scan(base))

 def test_baseline_path_exception_is_limited_to_exact_declarations(self):
  spec=importlib.util.spec_from_file_location('publication_audit',ROOT/'scripts/audit.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);(base/'docs').mkdir();p=base/'docs/V1.1-LIVE-BASELINE.md'
   p.write_text('\n'.join(audit.BASELINE_DECLARATIONS))
   self.assertEqual(audit.scan(base),[])
   p.write_text(p.read_text()+'\n/Users/'+'example-owner/private/account')
   self.assertIn(('docs/V1.1-LIVE-BASELINE.md','owner_home'),audit.scan(base))
   p.write_text('prefix '+audit.BASELINE_DECLARATIONS[0])
   self.assertIn(('docs/V1.1-LIVE-BASELINE.md','owner_home'),audit.scan(base))
   p.write_text('\n'.join(audit.BASELINE_DECLARATIONS));(base/'other.md').write_text(audit.BASELINE_DECLARATIONS[0])
   self.assertIn(('other.md','owner_home'),audit.scan(base))
