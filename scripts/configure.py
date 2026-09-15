"""Explicit validated configuration amendments with local write-ahead rollback."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,plistlib,re,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('release_operator',ROOT/'scripts/operator.py');op=importlib.util.module_from_spec(s);s.loader.exec_module(op)
TOOLS={'messages':['messages_chats','messages_history','messages_search'],'gmail':['gmail_search','gmail_read'],'calendar':['calendar_calendars','calendar_events','calendar_event'],'markdown':['save_local_markdown'],'files':['steward_list','steward_inspect','steward_create_folder','steward_move','steward_rename','steward_undo_last'],'browser':['browser'],'web':['web_search','web_fetch'],'mcp':['vinceai__get_current_time','vinceai__convert_to_markdown','vinceai__hub_repo_search']}

def active_janitor(prefix):
 svc=plistlib.loads((prefix/'config/gpu-janitor.plist').read_bytes())
 p=subprocess.run(['launchctl','print',f"gui/{os.getuid()}/"+svc['Label']],capture_output=True,text=True)
 return p.returncode==0 and str(prefix/'gate/manage.py') in p.stdout

def atomic(p,data):
 tmp=p.with_name(p.name+'.amend-tmp');op.write(tmp,data);os.replace(tmp,p)

def configure(prefix,proposal):
 op.verify();r=op.verify_install(prefix)
 if op.owns_process(op.process_record(prefix)):raise ValueError('Stop candidate gateway before configuration changes')
 if type(proposal) is not dict or set(proposal)-{'integrations','contacts','file_roots','accounts','gpu','notes_dir'}:raise ValueError('Unknown configuration field')
 changes={};cfg=json.loads((prefix/'config/openclaw.json').read_text())
 if 'integrations' in proposal:
  items=proposal['integrations']
  if type(items) is not list or any(type(n) is not str or n not in TOOLS for n in items):raise ValueError('Unknown integration')
  cfg['tools']['alsoAllow']=['calc','date_math','unit_convert','structured_parse']+[tool for n in sorted(set(items)) for tool in TOOLS[n]]
  if 'web' in items:
   base=prefix/'runtime/web/node_modules/@openclaw'
   for name in ('parallel','firecrawl'):
    plugin=base/(name+'-plugin');package=json.loads((plugin/'package.json').read_text())
    if package.get('name')!='@openclaw/'+name+'-plugin' or package.get('version')!='2026.8.1' or plugin.is_symlink():raise ValueError('Bootstrap the pinned optional web runtime first')
    path=str(plugin)
    if path not in cfg['plugins']['load']['paths']:cfg['plugins']['load']['paths'].append(path)
    if name not in cfg['plugins']['allow']:cfg['plugins']['allow'].append(name)
    cfg['plugins']['entries'][name]={'enabled':True}
   cfg['plugins']['entries']['parallel']['config']={'webSearch':{'apiKey':{'source':'store','provider':'default','id':'PARALLEL_API_KEY'}}}
   cfg['tools']['web']={'search':{'enabled':True,'provider':'parallel','maxResults':1},'fetch':{'enabled':True,'provider':'firecrawl','maxChars':6000,'maxCharsCap':6000}}
  elif 'web' in cfg['tools']:
   cfg['tools']['web']['search']['enabled']=False;cfg['tools']['web']['fetch']['enabled']=False
  if 'mcp' in items:
   profile=json.loads((prefix/'config/mcp-profile.json').read_text())
   profile['id']='sanctum-'+hashlib.sha256(str(prefix).encode()).hexdigest()[:12]
   profile['name']='Sanctum isolated tools'
   changes['config/mcp-profile.json']=json.dumps(profile,indent=2)+'\n'
   cfg.setdefault('mcp',{}).setdefault('servers',{})['vinceai']={'enabled':True,'transport':'stdio','command':str(ROOT/'.venv/bin/python'),'args':['-B',str(ROOT/'scripts/mcp_gateway.py'),'run','--prefix',str(prefix)],'requestTimeoutMs':90000,'connectionTimeoutMs':90000,'toolFilter':{'include':['get_current_time','convert_to_markdown','hub_repo_search'],'exclude':['mcp-*','code-mode','resources_*','prompts_*']}}
  elif 'vinceai' in cfg.get('mcp',{}).get('servers',{}):cfg['mcp']['servers']['vinceai']['enabled']=False
  changes['config/openclaw.json']=json.dumps(cfg,indent=2)+'\n'
 if 'notes_dir' in proposal:
  value=proposal['notes_dir']
  if type(value) is not str:raise ValueError('Invalid notes directory')
  path=Path(value)
  if not path.is_absolute() or not path.is_dir() or path.resolve()!=path or path.is_relative_to(ROOT):raise ValueError('Notes directory must be an existing nonsymlink directory outside source')
  env=json.loads((prefix/'config/environment.json').read_text());env['VINCEAI_NOTES_DIR']=str(path)
  changes['config/environment.json']=json.dumps(env,indent=2)+'\n'
 if 'contacts' in proposal:
  contacts=proposal['contacts']
  if type(contacts) is not dict or any(type(k) is not str or not k.strip() or type(v) is not int or not 0<=v<2**53 for k,v in contacts.items()):raise ValueError('Invalid contact mapping')
  changes['config/contacts.json']=json.dumps(contacts,indent=2)+'\n'
 if 'file_roots' in proposal:
  roots=proposal['file_roots']
  if type(roots) is not dict or set(roots)-{'desktop','downloads','documents','vinceai','pictures'}:raise ValueError('Invalid file scopes')
  for value in roots.values():
   p=Path(value)
   if not p.is_absolute() or p.is_symlink() or not p.is_dir():raise ValueError('File roots must be existing absolute directories, not symlinks')
  changes['config/file-roots.json']=json.dumps(roots,indent=2)+'\n'
 if 'accounts' in proposal:
  accounts=proposal['accounts']
  if type(accounts) is not dict or set(accounts)-{'gmail','calendar'}:raise ValueError('Invalid account kind')
  for name,value in accounts.items():
   if type(value) is not str or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Invalid account identifier')
   changes[f'config/{name}-read/account']=value+'\n'
 if 'gpu' in proposal:
  gpu=proposal['gpu'];allowed={'volume_id','datacenter','ssh_private_key','keychain_item','auto_start','local_port'}
  if type(gpu) is not dict or set(gpu)-allowed:raise ValueError('Unreviewed GPU policy change')
  settings=json.loads((prefix/'gate/SETTINGS.json').read_text())
  for k,v in gpu.items():
   if k=='auto_start':
    if type(v) is not bool:raise ValueError('auto_start must be boolean')
   elif k=='local_port':
    if type(v) is not int or not 1024<=v<=65535 or v in (r['gateway_port'],r['mlx_port'],28000):raise ValueError('Invalid or overlapping GPU tunnel port')
   elif type(v) is not str or not v or len(v)>1024 or any(c in v for c in '\n\r\0'):raise ValueError('Invalid GPU configuration')
  settings['gpu'].update(gpu)
  if settings['gpu']['auto_start']:
   if settings['gpu']['volume_id']=='CONFIGURE_VOLUME_ID' or not active_janitor(prefix):raise ValueError('Configure resource and load the prefix janitor before enabling GPU autostart')
   cli=prefix/'gate/runtime/runpodctl';pin=json.loads((prefix/'gate/runtime/RUNPODCTL.json').read_text())
   if cli.is_symlink() or op.sha(cli)!=pin['binary_sha256']:raise ValueError('Pinned Runpod CLI required')
   key=Path(settings['gpu']['ssh_private_key'])
   if not key.is_absolute() or key.is_symlink() or key.stat().st_mode&0o077:raise ValueError('Private SSH key required')
  changes['gate/SETTINGS.json']=json.dumps(settings,indent=2)+'\n'
  freeze=json.loads((prefix/'gate/FREEZE.json').read_text());freeze['SETTINGS.json']=hashlib.sha256(changes['gate/SETTINGS.json'].encode()).hexdigest();changes['gate/FREEZE.json']=json.dumps(freeze,indent=2)+'\n'
 # Enabling tools and broker access requires the same explicit operator proposal.
 for n in TOOLS:
  if n in ('messages','gmail','calendar') and 'integrations' in proposal:
   changes['config/'+n+'.enabled']='enabled\n' if n in proposal['integrations'] else 'disabled\n'
 if not changes:raise ValueError('No configuration changes requested')
 record={'before':{},'after':changes,'receipt_before':(prefix/'receipt.json').read_text()}
 for n,text in changes.items():
  p=prefix/n
  if p.is_symlink():raise ValueError('Symlink configuration target')
  record['before'][n]=p.read_text() if p.exists() else None
  r['files'][n]=hashlib.sha256(text.encode()).hexdigest()
 record['receipt_after']=json.dumps(r,indent=2)+'\n'
 log=prefix/'state/amendments'/str(time.time_ns());op.private(log);op.write(log/'transaction.json',json.dumps(record,indent=2))
 for n,text in changes.items():atomic(prefix/n,text)
 atomic(prefix/'receipt.json',record['receipt_after']);op.write(log/'complete','complete\n')
 print('Applied validated configuration fields: '+', '.join(sorted(proposal))+'. Private rollback record: '+str(log))

def rollback(prefix,log):
 if op.owns_process(op.process_record(prefix)):raise ValueError('Stop gateway before rollback')
 if not log.resolve().is_relative_to((prefix/'state/amendments').resolve()):raise ValueError('Rollback record must belong to prefix')
 r=json.loads((log/'transaction.json').read_text())
 if (prefix/'receipt.json').read_text() not in (r['receipt_before'],r['receipt_after']):raise ValueError('Receipt changed after amendment')
 for n,after in r['after'].items():
  p=prefix/n
  if p.is_symlink() or (p.read_text() if p.exists() else None) not in (r['before'][n],after):raise ValueError('Configuration changed after amendment')
 for n,before in r['before'].items():
  p=prefix/n
  if before is None:p.unlink(missing_ok=True)
  else:atomic(p,before)
 atomic(prefix/'receipt.json',r['receipt_before']);print('Restored owned configuration; runtime state preserved.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prefix',type=Path,default=ROOT/'.local');g=p.add_mutually_exclusive_group(required=True);g.add_argument('--proposal',type=Path);g.add_argument('--rollback',type=Path);a=p.parse_args()
 try:
  prefix=a.prefix.absolute()
  if a.proposal:configure(prefix,json.loads(a.proposal.read_text()))
  else:rollback(prefix,a.rollback.absolute())
 except (ValueError,OSError,KeyError) as e:raise SystemExit('REFUSED: '+str(e))
