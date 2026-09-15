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
  import plistlib
  self.assertEqual(plistlib.loads((self.prefix/'config/gpu-janitor.plist').read_bytes())['EnvironmentVariables']['USER'],os.environ.get('USER','vinceai'))
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
   base=Path(td);(base/'docs').mkdir();p=base/'docs/V1.1-LIVE-BASELINE.md';lines=audit.APPROVED_LOCATION_DECLARATIONS['docs/V1.1-LIVE-BASELINE.md']
   p.write_text('\n'.join(lines))
   self.assertEqual(audit.scan(base),[])
   p.write_text(p.read_text()+'\n/Users/'+'example-owner/private/account')
   self.assertIn(('docs/V1.1-LIVE-BASELINE.md','owner_home'),audit.scan(base))
   p.write_text('prefix '+lines[0])
   self.assertIn(('docs/V1.1-LIVE-BASELINE.md','owner_home'),audit.scan(base))
   p.write_text('\n'.join(lines));(base/'other.md').write_text(lines[0])
   self.assertIn(('other.md','owner_home'),audit.scan(base))
   agents=base/'AGENTS.md';agents.write_text('\n'.join(audit.APPROVED_LOCATION_DECLARATIONS['AGENTS.md']))
   self.assertEqual(audit.scan(base),[('other.md','owner_home')])
   (base/'other.md').unlink();agents.write_text(agents.read_text()+' extra')
   self.assertIn(('AGENTS.md','owner_home'),audit.scan(base))

class IntegrationAmendments(unittest.TestCase):
 setUp=Setup.setUp
 def module(self):
  spec=importlib.util.spec_from_file_location('integration_config',ROOT/'scripts/configure.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
 def test_isolated_mcp_notes_and_tunnel_rollback(self):
  op.setup(self.prefix);before=(self.prefix/'receipt.json').read_bytes();notes=self.prefix.parent/'notes';notes.mkdir()
  self.module().configure(self.prefix,{'integrations':['mcp'],'notes_dir':str(notes),'gpu':{'local_port':28001}})
  op.verify_install(self.prefix);cfg=json.loads((self.prefix/'config/openclaw.json').read_text());server=cfg['mcp']['servers']['vinceai']
  self.assertEqual(server['toolFilter']['include'],['get_current_time','convert_to_markdown','hub_repo_search'])
  self.assertIn(str(self.prefix),server['args']);self.assertIn('exec',cfg['tools']['deny'])
  self.assertTrue(json.loads((self.prefix/'config/mcp-profile.json').read_text())['id'].startswith('sanctum-'))
  self.assertEqual(op.environment(self.prefix)['VINCEAI_NOTES_DIR'],str(notes));self.assertFalse(json.loads((self.prefix/'gate/SETTINGS.json').read_text())['gpu']['auto_start'])
  self.module().rollback(self.prefix,next((self.prefix/'state/amendments').iterdir()));self.assertEqual(before,(self.prefix/'receipt.json').read_bytes())
 def test_reject_source_symlink_and_overlapping_port_without_mutation(self):
  op.setup(self.prefix);before=(self.prefix/'receipt.json').read_bytes();link=self.prefix.parent/'link';link.symlink_to(self.prefix)
  for proposal in [{'notes_dir':str(ROOT)},{'notes_dir':str(link)},{'notes_dir':'relative'},{'gpu':{'local_port':True}},{'gpu':{'local_port':28080}},{'gpu':{'local_port':28000}},{'gpu':{'local_port':70000}},{'integrations':['mcp'],'command':'exec'}]:
   with self.assertRaises(ValueError):self.module().configure(self.prefix,proposal)
   self.assertEqual(before,(self.prefix/'receipt.json').read_bytes())
 def test_mcp_profile_signature_covers_transport_mounts_and_tools(self):
  spec=importlib.util.spec_from_file_location('mcp_gateway',ROOT/'scripts/mcp_gateway.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  base=json.loads((ROOT/'mcp-integration/config/profile.json').read_text())
  for field,value in [('endpoint','https://example.com'),('tools',['unreviewed']),('image','unreviewed')]:
   changed=json.loads(json.dumps(base));changed['servers'][0][field]=value;self.assertNotEqual(mod.signature(base),mod.signature(changed))
  changed=json.loads(json.dumps(base));changed['servers'][2]['snapshot']['server']['volumes']=['/:/mcp-input'];self.assertNotEqual(mod.signature(base),mod.signature(changed))
