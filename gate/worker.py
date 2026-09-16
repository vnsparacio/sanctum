"""Single authenticated operation. Only local control-plane code can sign it."""
import os
from pathlib import Path
import signal
import sys
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from common import Refused, canonical, load_settings, strict_json, verify_release
from authority import authorize
from backends import Remote, LocalMultimodalBackend
from dispatch import assess
from lifecycle import Private80BLifecycle, PrivateLeadLifecycle
from media import load, expand
from command_runner import run as run_command
from source_policy import minimize_query
from workspace import create_worktree, list_entries, read_text, apply_patch, inspect_worktree, cleanup_worktree
from common import atomic, canonical, private_dir, strict_json

def work_root(settings): return private_dir(Path(settings['state_directory'])/'private-lead'/'work-mode'/'workspaces')
def work_record(settings,task_id):
    path=work_root(settings)/(task_id+'.json')
    if path.is_symlink() or not path.exists(): raise Refused('worktree_unavailable')
    value=strict_json(path.read_text())
    if value.get('workspace_id')!=task_id: raise Refused('worktree_identity')
    return value
def work_profile(settings,name):
    path=Path(settings['work_mode']['profile_file'])
    if path.is_symlink() or path.stat().st_mode&0o077: raise Refused('work_profile_permissions')
    value=strict_json(path.read_text());profile=value.get('profiles',{}).get(name)
    if type(profile) is not dict: raise Refused('work_profile_unknown')
    return profile


def execute(b, settings, remote=None, lifecycle=None):
    op=b['operation']; scope=b['scope']
    if op=='worktree_create':
        p=b['packet'];profile=work_profile(settings,p['profile']);root=work_root(settings);record_path=root/(scope+'.json')
        if record_path.exists() or record_path.is_symlink(): raise Refused('worktree_exists')
        workspace=create_worktree(profile['repository'],profile['staging_root'],scope,profile['disk_bytes'])
        workspace['profile']=p['profile'];atomic(record_path,canonical(workspace).encode())
        return {'status':'OK','workspace':{'workspace_id':scope,'base_commit':workspace['base_commit'],'initial_status':workspace['initial_status'],'disk_bytes':workspace['disk_bytes']}}
    if op=='worktree_list':
        p=b['packet'];return {'status':'OK','result':list_entries(work_record(settings,scope)['root'],p['path'],p['max_entries'])}
    if op=='worktree_read':
        p=b['packet'];return {'status':'OK','result':read_text(work_record(settings,scope)['root'],p['path'],p['max_chars'])}
    if op=='worktree_patch':
        p=b['packet'];return {'status':'OK','result':apply_patch(work_record(settings,scope)['root'],p['patch'])}
    if op=='worktree_command':
        p=b['packet'];record=work_record(settings,scope)
        if record['profile']!=p['profile']:raise Refused('worktree_profile_mismatch')
        if p['operation'] in {'status','diff'}:return {'status':'OK','result':inspect_worktree(record['root'],p['operation'])}
        return {'status':'OK','result':run_command(settings,p['profile'],record['root'],p['operation'])}
    if op=='worktree_cleanup':
        p=b['packet'];record=work_record(settings,scope);profile=work_profile(settings,p['profile'])
        if record['profile']!=p['profile']:raise Refused('worktree_profile_mismatch')
        result=cleanup_worktree(profile['repository'],record);(work_root(settings)/(scope+'.json')).unlink()
        return {'status':'OK','result':result}
    if op=='work_source_policy':
        p=b['packet'];draft=minimize_query(p['prompt'])
        return {'status':'OK','result':{'query':draft.query,'sensitivity':draft.sensitivity,'queryMode':draft.mode,'reasonCodes':list(draft.reason_codes),'digest':draft.digest,'sourceNeed':p['source_need']}}
    if op=='media':
        p=load(b['packet']['token'],None,scope,settings,bind=True)
        return {'status':'OK','digest':p['digest'],'summary':p['summary']}
    if op=='classify':
        packet=dict(b['packet']); packet['disclosed']=expand(packet.get('disclosed',{}),scope,settings)
        # No token, file path or private snapshot identifiers are sent to Gemini.
        audit=(remote or Remote(settings)).classify(packet,b['nonce'],(BASE/'PROMPT.txt').read_text())
        return assess(b['packet'],b['state'],audit,b['strong'])
    if op=='infer':
        packet=expand(b['packet'],scope,settings)
        if len(canonical({k:v for k,v in packet.items() if k!='images'}).encode())>settings['max_context_bytes']: raise Refused('answer_context_limit')
        if b['tier']=='PRIVATE_80B': return (lifecycle or Private80BLifecycle(settings)).infer(scope,packet)
        if b['tier']=='PRIVATE_LEAD': return (lifecycle or PrivateLeadLifecycle(settings)).infer(scope,packet)
        if b['tier']=='MULTIMODAL' and settings['multimodal']['transport']=='local': return LocalMultimodalBackend(settings).infer(packet)
        return (remote or Remote(settings)).infer(b['tier'],packet,b['nonce'])
    if op=='private_lead_propose':
        return (lifecycle or PrivateLeadLifecycle(settings)).propose(scope,b['packet']['request'])
    lc=lifecycle or (PrivateLeadLifecycle(settings) if b['tier']=='PRIVATE_LEAD' else Private80BLifecycle(settings))
    if op=='close': lc.release(scope,close=True)
    elif op=='sweep': lc.sweep()
    elif op=='stop': lc.sweep(immediate=True,manual=True)
    elif op=='resume': lc.resume()
    return {'status':'OK','gpu':lc.status()}


def main():
    os.umask(0o077); verify_release(); settings=load_settings()
    raw=sys.stdin.buffer.read(220001)
    if len(raw)>220000: raise Refused('input_limit')
    body=authorize(strict_json(raw),settings)
    # SIGTERM interrupts bootstrap/query and unwinds the lease finally block.
    def stop(*_): raise Refused('operation_cancelled')
    signal.signal(signal.SIGTERM,stop)
    return execute(body,settings)

if __name__=='__main__':
    try: print(canonical(main()))
    except Exception as e:
        # Refused messages are enumerated local codes. Never echo arbitrary errors.
        safe=str(e) if type(e) is Refused and str(e).replace('_','').isalnum() else 'operation_unavailable'
        print(canonical({'status':'UNAVAILABLE','reason':safe})); sys.exit(1)
