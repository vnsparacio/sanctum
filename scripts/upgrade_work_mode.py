"""Stopped-gateway, reversible Project 3G Work Mode amendment."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,platform,shutil,sqlite3,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_operator',ROOT/'scripts/release_operator.py');op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)

FILES=(
 'SETTINGS.json','manage.py','worker.py','src/authority.py','src/backends.py','src/command_runner.py','src/lifecycle.py','src/workspace.py',
 'foundation/contracts.mjs','foundation/manifest.mjs','foundation/evidence.mjs','foundation/work-intent.mjs','plugin/index.mjs','plugin/core.mjs',
 'plugin/private-lead.mjs','plugin/source-retrieval.mjs','plugin/work-mode.mjs','plugin/work-command.mjs','plugin/command-broker.mjs',
 'plugin/work-ledger.mjs','plugin/workspace-tools.mjs','plugin/openclaw.plugin.json','plugin/package.json',
 'runtime/private-lead-interface-profile.json','runtime/private-releases.json','runtime/bootstrap-vllm.sh',
 'runtime/work-runner.json','runtime/work-runner.Dockerfile','webui/bridge.mjs','webui/pipe.py')
WORK_TOOLS=['worktree_list','worktree_read','worktree_patch','worktree_command','source_first_research']
BROKER_ALLOW=WORK_TOOLS+['web_search','web_fetch']
BROKER_DENY=['exec','process','shell','write','edit','apply_patch','sessions_*','gateway','nodes','cron','terminal','browser','gmail_*','messages_*','calendar_*','steward_*','save_local_markdown','vinceai__*']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def atomic(path,data):
 tmp=path.with_name(path.name+'.project3g-tmp');op.write(tmp,data);os.replace(tmp,path)
def safe(prefix):
 if platform.system()!='Darwin':raise ValueError('Project 3G live amendment requires macOS')
 if op.owns_process(op.process_record(prefix)):raise ValueError('Stop candidate gateway before Work Mode amendment')
 for name in ('gpu.json','private-lead/gpu.json'):
  path=prefix/'state/gate'/name
  if path.exists():
   value=json.loads(path.read_text())
   if value.get('phase')!='OFFLINE' or any(value.get(k) for k in ('pod_id','pod_name','allocation_uncertain')):raise ValueError('Unresolved GPU ownership; preserve cleanup')
 db=prefix/'state/gate/control.sqlite'
 if db.exists():
  with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
   if conn.execute('select count(*) from leases').fetchone()[0]:raise ValueError('Close all private leases first')
 plist=prefix/'config/gpu-janitor.plist'
 if not plist.is_file() or plist.is_symlink():raise ValueError('Independent janitor configuration unavailable')
 label=json.loads(json.dumps(__import__('plistlib').loads(plist.read_bytes())))['Label']
 if subprocess.run(['/bin/launchctl','print',f'gui/{os.getuid()}/{label}'],capture_output=True).returncode:raise ValueError('Independent janitor is not loaded')
def docker_details():
 located=shutil.which('docker')
 if not located:raise ValueError('Pinned Docker CLI unavailable')
 try:docker=str(Path(located).resolve(strict=True))
 except OSError:raise ValueError('Pinned Docker CLI unavailable') from None
 if not Path(docker).is_file() or Path(docker).is_symlink() or not Path(docker).is_absolute():raise ValueError('Pinned Docker CLI unavailable')
 subprocess.run([docker,'version'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
 context=json.loads(subprocess.run([docker,'context','inspect'],check=True,capture_output=True,text=True,timeout=20).stdout)
 host=context[0]['Endpoints']['docker']['Host']
 if not isinstance(host,str) or not host.startswith('unix://'):raise ValueError('Work Mode requires a local Unix Docker endpoint')
 tag='sanctum-work-runner:project3g'
 subprocess.run([docker,'build','--pull','--platform','linux/arm64','--tag',tag,'--file',str(ROOT/'gate/runtime/work-runner.Dockerfile'),str(ROOT/'gate/runtime')],check=True,timeout=1800)
 image=subprocess.run([docker,'image','inspect','--format','{{.Id}}',tag],check=True,capture_output=True,text=True,timeout=20).stdout.strip()
 if not image.startswith('sha256:'):raise ValueError('Runner image identity unavailable')
 return str(Path(docker).resolve()),host,tag,image
def rendered_settings(prefix):
 data=(ROOT/'gate/SETTINGS.json').read_text()
 for old,new in {'@PYTHON@':str(ROOT/'.venv/bin/python'),'@STATE@':str(prefix/'state'),'@CONFIG@':str(prefix/'config')}.items():data=data.replace(old,new)
 value=json.loads(data);installed=json.loads((prefix/'gate/SETTINGS.json').read_text())
 for section in ('gpu','private_lead'):
  for key in ('volume_id','datacenter','ssh_private_key','keychain_item','max_hourly_usd'):
   if key in installed.get(section,{}):value[section][key]=installed[section][key]
 value['private_lead']['enabled']=True;value['private_lead']['auto_start']=False;value['work_mode']['enabled']=True
 return json.dumps(value,indent=2)+'\n'
def rendered_file(prefix,name):
 if name=='SETTINGS.json':return rendered_settings(prefix)
 data=(ROOT/'gate'/name).read_text();tokens={'@PYTHON@':str(ROOT/'.venv/bin/python'),'@STATE@':str(prefix/'state'),'@CONFIG@':str(prefix/'config'),'@GATE@':str(prefix/'gate'),'@OPENCLAW@':str(ROOT/'node_modules/openclaw'),'@NODE@':str(Path(shutil.which('node')).resolve())}
 for old,new in tokens.items():data=data.replace(old,new)
 return data
def openclaw_config(prefix):
 path=prefix/'config/openclaw.json';value=json.loads(path.read_text());agents=value.setdefault('agents',{});agents['ownership']='explicit';entries=agents.setdefault('entries',{})
 main=entries.setdefault('main',{});tools=main.setdefault('tools',{});tools['deny']=sorted(set(tools.get('deny',[])+WORK_TOOLS))
 entries['workmode-broker']={'name':'Sanctum Work Mode semantic broker','workspace':str(prefix/'state/workspace'),'skills':[],'tools':{'profile':'minimal','allow':BROKER_ALLOW,'deny':BROKER_DENY,'elevated':{'enabled':False},'fs':{'workspaceOnly':True}}}
 top=value.setdefault('tools',{});top['alsoAllow']=list(dict.fromkeys(top.get('alsoAllow',[])+WORK_TOOLS))
 return json.dumps(value,indent=2)+'\n'
def work_profile(prefix,docker,host,tag,image):
 staging=op.private(prefix/'state/gate/private-lead/work-mode/staging');op.private(prefix/'state/gate/private-lead/work-mode/tasks');op.private(prefix/'state/gate/private-lead/work-mode/workspaces')
 common={'disk_bytes':8*1024**3,'docker_path':docker,'docker_host':host,'runner_image':tag,'runner_image_id':image,'runner_user':f'{os.getuid()}:{os.getgid()}','platform':'linux/arm64','timeout_seconds':120,'operations':{'status':['git','status','--porcelain=v1'],'diff':['git','diff','--binary'],'test':['node','--test'],'lint':['node','--check','index.js'],'build':['node','--check','index.js']},'evaluators':['test'],'capabilities':WORK_TOOLS,'max_iterations':16,'max_model_calls':16,'max_task_seconds':1200,'max_tokens':100000,'max_gpu_seconds':900,'max_cost_usd':1.5,'reviewer':True}
 profiles={'sanctum':{**common,'repository':str(ROOT),'staging_root':str(staging),'operations':{**common['operations'],'test':['node','--test','gate/tests'],'lint':['node','--check','gate/plugin/index.mjs'],'build':['node','--check','gate/plugin/index.mjs']}}}
 fixtures=op.private(prefix/'state/gate/private-lead/work-mode/qualification')
 for number in range(1,11):
  name=f'grade{number:02d}';profiles[name]={**common,'repository':str(fixtures/name/'repo'),'staging_root':str(op.private(fixtures/name/'staging'))}
 profiles['adversarial']={**common,'repository':str(fixtures/'adversarial/repo'),'staging_root':str(op.private(fixtures/'adversarial/staging')),'reviewer':False}
 return json.dumps({'schema':'sanctum-work-mode-profiles/v1','profiles':profiles},indent=2)+'\n'
def apply(prefix):
 op.verify();receipt=op.verify_install(prefix);safe(prefix);docker,host,tag,image=docker_details()
 record=prefix/'state/amendments'/('work-mode-'+str(time.time_ns()));op.private(record)
 targets=[('gate/'+name,prefix/'gate'/name) for name in FILES]+[('config/openclaw.json',prefix/'config/openclaw.json'),('config/work-mode.json',prefix/'config/work-mode.json')]
 before={}
 for name,target in targets:
  before[name]='present' if target.exists() else 'absent'
  if target.exists():
   if target.is_symlink():raise ValueError('Unsafe amendment target')
   backup=record/name;backup.parent.mkdir(parents=True,exist_ok=True,mode=0o700);shutil.copy2(target,backup)
 shutil.copy2(prefix/'gate/FREEZE.json',record/'gate/FREEZE.json');shutil.copy2(prefix/'receipt.json',record/'receipt.json')
 for name in FILES:
  target=prefix/'gate'/name;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700);atomic(target,rendered_file(prefix,name))
 atomic(prefix/'config/openclaw.json',openclaw_config(prefix));atomic(prefix/'config/work-mode.json',work_profile(prefix,docker,host,tag,image))
 freeze=json.loads((prefix/'gate/FREEZE.json').read_text())
 for name in FILES:freeze[name]=sha(prefix/'gate'/name)
 atomic(prefix/'gate/FREEZE.json',json.dumps(freeze,indent=2)+'\n')
 for name,target in targets:receipt['files'][name]=sha(target)
 receipt['files']['gate/FREEZE.json']=sha(prefix/'gate/FREEZE.json');atomic(prefix/'receipt.json',json.dumps(receipt,indent=2)+'\n')
 tx={'schema':'sanctum-work-mode-amendment/v1','before':before,'files':[name for name,_ in targets],'runner_image':tag,'runner_image_id':image,'source_commit':subprocess.run(['/usr/bin/git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()}
 atomic(record/'transaction.json',json.dumps(tx,indent=2)+'\n');op.write(record/'complete','complete\n')
 print('Applied Project 3G Work Mode amendment. Private rollback record: '+str(record))
def rollback(prefix,record):
 safe(prefix);record=record.absolute()
 if not record.is_relative_to((prefix/'state/amendments').absolute()):raise ValueError('Rollback record must belong to prefix')
 tx=json.loads((record/'transaction.json').read_text())
 if tx.get('schema')!='sanctum-work-mode-amendment/v1':raise ValueError('Wrong rollback transaction')
 for name,state in tx['before'].items():
  target=prefix/name
  if state=='present':atomic(target,(record/name).read_text())
  else:target.unlink(missing_ok=True)
 atomic(prefix/'gate/FREEZE.json',(record/'gate/FREEZE.json').read_text());atomic(prefix/'receipt.json',(record/'receipt.json').read_text())
 print('Restored the pre-Project-3G candidate. Private task receipts and runner image were retained.')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--prefix',type=Path,required=True);group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--apply',action='store_true');group.add_argument('--rollback',type=Path);args=parser.parse_args()
 try:apply(args.prefix.absolute()) if args.apply else rollback(args.prefix.absolute(),args.rollback)
 except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:raise SystemExit('REFUSED: '+str(error))
