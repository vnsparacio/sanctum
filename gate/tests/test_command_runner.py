import json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'src'))
from command_runner import run,verify_runner

class OciRunner(unittest.TestCase):
 def write_profile(self,timeout):
  value=json.loads(self.profile.read_text());value['profiles']['test']['timeout_seconds']=timeout;self.profile.write_text(json.dumps(value));self.profile.chmod(0o600)
 def setUp(self):
  self.docker=shutil.which('docker')
  if not self.docker:self.skipTest('Docker CLI unavailable')
  try:subprocess.run([self.docker,'version'],check=True,capture_output=True,timeout=10)
  except Exception:self.skipTest('Docker daemon unavailable')
  inspect=subprocess.run([self.docker,'image','inspect','--format','{{.Id}}','sanctum-work-runner:project3g'],capture_output=True,text=True)
  if inspect.returncode:self.skipTest('reviewed Work Mode runner unavailable')
  context=json.loads(subprocess.run([self.docker,'context','inspect'],check=True,capture_output=True,text=True).stdout)
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.root.chmod(0o700);self.workspace=self.root/'workspace';self.workspace.mkdir()
  (self.workspace/'index.test.js').write_text("import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import net from 'node:net';test('sandbox',async()=>{assert.equal(process.env.TEST_SECRET,undefined);assert.equal(fs.existsSync('/run/docker.sock'),false);assert.equal(fs.existsSync('/Users'),false);await new Promise((resolve,reject)=>{const s=net.connect({host:'1.1.1.1',port:443});const blocked=()=>{s.destroy();resolve()};s.on('error',blocked);s.setTimeout(500,blocked);s.on('connect',()=>reject(Error('ambient network')))});});\n")
  profile={'schema':'sanctum-work-mode-profiles/v1','profiles':{'test':{'docker_path':str(Path(self.docker).resolve()),'docker_host':context[0]['Endpoints']['docker']['Host'],'runner_image':'sanctum-work-runner:project3g','runner_image_id':inspect.stdout.strip(),'runner_user':f'{os.getuid()}:{os.getgid()}','platform':'linux/arm64','timeout_seconds':30,'operations':{'test':['node','--test']}}}}
  self.profile=self.root/'profile.json';self.profile.write_text(json.dumps(profile));self.profile.chmod(0o600);self.settings={'work_mode':{'profile_file':str(self.profile)}}
 def tearDown(self):
  if hasattr(self,'tmp'):self.tmp.cleanup()
 def test_real_container_has_limits_no_socket_home_secret_or_network_mount(self):
  os.environ['TEST_SECRET']='must-not-leak'
  try:result=run(self.settings,'test',str(self.workspace),'test')
  finally:os.environ.pop('TEST_SECRET',None)
  self.assertTrue(result['ok'],result);self.assertTrue(result['container_absent']);self.assertEqual(result['limits']['network'],'none');self.assertEqual(result['runner'],verify_runner(self.settings,'test'))
 def test_output_timeout_and_file_limits_fail_closed_and_cleanup(self):
  self.write_profile(10)
  (self.workspace/'index.test.js').write_text("import test from 'node:test';test('output',()=>process.stdout.write('x'.repeat(70000)));\n")
  output=run(self.settings,'test',str(self.workspace),'test');self.assertEqual(output['code'],'OUTPUT_LIMIT');self.assertTrue(output['container_absent'])
  self.write_profile(1)
  (self.workspace/'index.test.js').write_text("import test from 'node:test';test('timeout',async()=>await new Promise(r=>setTimeout(r,5000)));\n")
  timed=run(self.settings,'test',str(self.workspace),'test');self.assertEqual(timed['code'],'COMMAND_TIMEOUT');self.assertTrue(timed['container_absent'])
  self.write_profile(10)
  (self.workspace/'index.test.js').write_text("import test from 'node:test';import fs from 'node:fs';test('file',()=>fs.writeFileSync('large.bin',Buffer.alloc(70*1024*1024)));\n")
  disk=run(self.settings,'test',str(self.workspace),'test');self.assertFalse(disk['ok']);self.assertTrue(disk['container_absent']);self.assertFalse((self.workspace/'large.bin').exists())

if __name__=='__main__':unittest.main()
