"""Narrow staged upgrade from 9I, with a write-ahead rollback receipt.

No model configuration, tool permission, credential store or persistent volume is
changed. Invoke explicitly only after reviewing this build's acceptance report.
"""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import sqlite3
import subprocess
import sys
import time
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from common import Refused, atomic, canonical, private_dir, strict_json, verify_release

OLD=str(BASE.parent/'phase9i-openclaw-agent-handoff-v1/plugin')
NEW=str(BASE/'plugin')
CONFIG=Path.home()/'.openclaw/openclaw.json'
DB=Path.home()/'.local/share/vinceai-ui/data/webui.db'
STATE=BASE/'state'
LABEL='net.vinceai.phase10-gpu-janitor'
LAUNCH=Path.home()/'Library/LaunchAgents'/(LABEL+'.plist')
FUNCTIONS={'mac_prompt_gate_v1':('webui/pipe.py',BASE.parent/'phase9i-openclaw-agent-handoff-v1/webui/pipe.py'), 'mac_gate_text_boundary_v1':('webui/guard.py',BASE.parent/'phase9h-openwebui-gate-v2/guard.py')}

def sha(x): return hashlib.sha256(x).hexdigest()
def connection(path):
    if Path(path).is_symlink(): raise Refused('database_symlink')
    c=sqlite3.connect(path);c.row_factory=sqlite3.Row;return c

def launch_bytes():
    settings=strict_json((BASE/'SETTINGS.json').read_text())
    return plistlib.dumps({'Label':LABEL,'ProgramArguments':[settings['python'],'-B',str(BASE/'manage.py'),'sweep'],'RunAtLoad':True,'StartInterval':30,'ProcessType':'Background','StandardOutPath':'/dev/null','StandardErrorPath':'/dev/null','EnvironmentVariables':{'PYTHONDONTWRITEBYTECODE':'1','USER':os.environ.get('USER','vinceai')}})

def launch_action(action,path):
    target='gui/'+str(os.getuid())
    if action=='load': args=['bootstrap',target,str(path)]
    else: args=['bootout',target+'/'+LABEL]
    r=subprocess.run(['/bin/launchctl',*args],capture_output=True,timeout=30)
    if r.returncode and action=='load': raise Refused('janitor_load_failed')

def ensure_gpu_offline():
    from lifecycle import Private80BLifecycle
    from common import load_settings
    lc=Private80BLifecycle(load_settings());lc.sweep(immediate=True,manual=True)
    s=lc.status()
    if s['phase'] not in ['OFFLINE',None] or s['leases']: raise Refused('close_sessions_confirm_gpu_offline_first')
    # Reconcile against the provider, not just a cached local OFFLINE label.
    with lc.lock(): lc.reconcile(lc.state())

def install(config=CONFIG,db=DB,state=STATE,launch=LAUNCH,runner=launch_action,verify=verify_release,hook=lambda _:None):
    verify();state=private_dir(state);config=Path(config);launch=Path(launch)
    receipt=state/'install-receipt.json'
    if receipt.exists(): raise Refused('receipt_exists_rollback_first')
    if config.is_symlink() or launch.exists() or launch.is_symlink(): raise Refused('installation_target_changed')
    raw=config.read_bytes();cfg=strict_json(raw);paths=cfg['plugins']['load']['paths']
    if paths.count(OLD)!=1 or NEW in paths: raise Refused('expected_phase9i_missing')
    if cfg['plugins'].get('entries',{}).get('hybrid-ai-prompt-gate',{}).get('enabled') is not True: raise Refused('gate_not_enabled')
    c=connection(db)
    try:
        c.execute('begin immediate');before={};after={}
        for name,(relative,previous) in FUNCTIONS.items():
            row=c.execute('select * from function where id=?',(name,)).fetchone()
            if not row or not row['is_active'] or row['content']!=previous.read_text(): raise Refused('baseline_function_drift')
            before[name]=dict(row);after[name]=(BASE/relative).read_text()
        launch_data=launch_bytes()
        record={'config':str(config.resolve()),'database':str(Path(db).resolve()),'launch':str(launch.absolute()),'before':before,'after':after,'launch_sha256':sha(launch_data),'phase':'PREPARED'}
        atomic(state/'openclaw.before.json',raw)
        atomic(receipt,canonical(record).encode())
        key=state/'authority.key'
        if not key.exists(): atomic(key,os.urandom(32))
        if key.is_symlink() or key.stat().st_mode & 0o077: raise Refused('unsafe_authority_key')
        # Receipt already exists before the first live mutation, even if the
        # process dies between the filesystem update and SQLite commit.
        hook('prepared')
        cfg['plugins']['load']['paths']=[NEW if p==OLD else p for p in paths]
        if config.read_bytes()!=raw: raise Refused('config_changed_during_install')
        atomic(config,(json.dumps(cfg,indent=2)+'\n').encode());hook('config')
        for name,value in after.items(): c.execute('update function set content=?,updated_at=? where id=?',(value,int(time.time()),name))
        c.commit();hook('database')
        launch.parent.mkdir(parents=True,exist_ok=True)
        atomic(launch,launch_data);hook('launch_file');runner('load',launch);hook('launch_loaded')
        record['phase']='INSTALLED';atomic(receipt,canonical(record).encode())
        return {'installed':True,'restart_gateway_and_webui_required':True,'tool_permissions_changed':False,'model_defaults_changed':False}
    finally:c.close()

def rollback(state=STATE,runner=launch_action,gpu_check=ensure_gpu_offline,hook=lambda _:None):
    state=private_dir(state);receipt=state/'install-receipt.json';r=strict_json(receipt.read_text())
    gpu_check()  # Keep the janitor installed if shutdown is unconfirmed.
    config=Path(r['config']);launch=Path(r['launch'])
    if config.is_symlink() or launch.is_symlink(): raise Refused('rollback_target_symlink')
    raw=config.read_bytes();cfg=strict_json(raw);paths=cfg['plugins']['load']['paths']
    if not ((paths.count(OLD)==1 and NEW not in paths) or (paths.count(NEW)==1 and OLD not in paths)): raise Refused('plugin_path_drift')
    if launch.exists() and sha(launch.read_bytes())!=r['launch_sha256']: raise Refused('janitor_changed')
    c=connection(r['database'])
    try:
        c.execute('begin immediate')
        for name,before in r['before'].items():
            row=c.execute('select * from function where id=?',(name,)).fetchone()
            if not row or row['content'] not in [before['content'],r['after'][name]]: raise Refused('gate_function_drift')
        for name,before in r['before'].items(): c.execute('update function set content=?,updated_at=? where id=?',(before['content'],before['updated_at'],name))
        cfg['plugins']['load']['paths']=[OLD if p==NEW else p for p in paths]
        if config.read_bytes()!=raw: raise Refused('config_changed_during_rollback')
        atomic(config,(json.dumps(cfg,indent=2)+'\n').encode());hook('config')
        c.commit();hook('database')
        runner('unload',launch);launch.unlink(missing_ok=True)
        receipt.rename(state/('install-receipt.rolled-back-'+str(time.time_ns())+'.json'))
        return {'rolled_back_to':'phase9i','restart_gateway_and_webui_required':True,'unrelated_settings_preserved':True}
    finally:c.close()

if __name__=='__main__':
    raise SystemExit('Historical upgrade adapter: use scripts/operator.py; no production migration is automatic.')
    try:
        if sys.argv[1:]==['install']: result=install()
        elif sys.argv[1:]==['rollback']: result=rollback()
        else: raise Refused('use_install_or_rollback')
        print(canonical(result))
    except Exception as e: raise SystemExit('REFUSED: '+(str(e) if type(e) is Refused else 'local_installation_error_rollback_receipt_preserved'))
