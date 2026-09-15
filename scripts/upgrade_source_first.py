"""Stopped-gateway, reversible Project 2 Source-First gate upgrade."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, shutil, time
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_operator',ROOT/'scripts/release_operator.py');op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)
FILES=('PROMPT.txt','foundation/contracts.mjs','foundation/audit.mjs','foundation/evidence.mjs','foundation/manifest.mjs','plugin/core.mjs','plugin/index.mjs','plugin/source-retrieval.mjs','src/schema.py','src/dispatch.py','src/source_policy.py','src/backends.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def atomic(path,data):
 tmp=path.with_name(path.name+'.source-first-tmp');op.write(tmp,data);os.replace(tmp,path)
def safe(prefix):
 if op.owns_process(op.process_record(prefix)):raise ValueError('Stop candidate gateway before source upgrade')
 state=prefix/'state/gate/gpu.json'
 if state.exists():
  d=json.loads(state.read_text())
  if d.get('phase')!='OFFLINE' or any(d.get(k) for k in ('pod_id','pod_name','allocation_uncertain')):raise ValueError('Unresolved GPU ownership; preserve cleanup')
def apply(prefix):
 op.verify();receipt=op.verify_install(prefix);safe(prefix)
 root=prefix/'state/amendments'/('source-first-'+str(time.time_ns()));op.private(root)
 before={}
 for name in FILES:
  target=prefix/'gate'/name
  if target.exists():
   if target.is_symlink():raise ValueError('Unsafe installed gate file')
   backup=root/'gate'/name;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup);before[name]='present'
  else:before[name]='absent'
  source=ROOT/'gate'/name
  if not source.exists() or source.is_symlink():raise ValueError('Missing reviewed source file')
 for name in ('FREEZE.json',):shutil.copy2(prefix/'gate'/name,root/'gate'/name)
 shutil.copy2(prefix/'receipt.json',root/'receipt.json')
 for name in FILES:
  target=prefix/'gate'/name;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700);atomic(target,(ROOT/'gate'/name).read_text())
 freeze=json.loads((prefix/'gate/FREEZE.json').read_text())
 for name in FILES:freeze[name]=sha(prefix/'gate'/name)
 atomic(prefix/'gate/FREEZE.json',json.dumps(freeze,indent=2)+'\n')
 receipt['files'].update({f'gate/{name}':sha(prefix/'gate'/name) for name in FILES});receipt['files']['gate/FREEZE.json']=sha(prefix/'gate/FREEZE.json')
 atomic(prefix/'receipt.json',json.dumps(receipt,indent=2)+'\n')
 atomic(root/'transaction.json',json.dumps({'schema':'sanctum-source-first-upgrade/v1','before':before,'files':list(FILES)},indent=2)+'\n');op.write(root/'complete','complete\n')
 print('Applied Source-First gate upgrade. Private rollback record: '+str(root))
def rollback(prefix,record):
 safe(prefix);record=record.absolute()
 if not record.is_relative_to((prefix/'state/amendments').absolute()):raise ValueError('Rollback record must belong to prefix')
 tx=json.loads((record/'transaction.json').read_text())
 for name,state in tx['before'].items():
  target=prefix/'gate'/name
  if state=='present':atomic(target,(record/'gate'/name).read_text())
  else:target.unlink(missing_ok=True)
 atomic(prefix/'gate/FREEZE.json',(record/'gate/FREEZE.json').read_text());atomic(prefix/'receipt.json',(record/'receipt.json').read_text())
 print('Restored prior installed gate files; private runtime state preserved.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prefix',type=Path,required=True);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--apply',action='store_true');g.add_argument('--rollback',type=Path);a=p.parse_args()
 try:apply(a.prefix.absolute()) if a.apply else rollback(a.prefix.absolute(),a.rollback)
 except (ValueError,OSError,KeyError) as e:raise SystemExit('REFUSED: '+str(e))
