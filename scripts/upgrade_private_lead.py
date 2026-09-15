"""Stopped-gateway, reversible staged PRIVATE_LEAD runtime amendment."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, shutil, time
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_operator',ROOT/'scripts/release_operator.py'); op=importlib.util.module_from_spec(spec); spec.loader.exec_module(op)
FILES=('SETTINGS.json','benchmark.py','manage.py','watch.py','worker.py','src/schema.py','src/authority.py','src/backends.py','src/lifecycle.py','src/runpod.py','runtime/private-releases.json','runtime/bootstrap-private-lead-vllm.sh')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def atomic(path,data):
    tmp=path.with_name(path.name+'.private-lead-tmp'); op.write(tmp,data); os.replace(tmp,path)
def safe(prefix):
    if op.owns_process(op.process_record(prefix)): raise ValueError('Stop candidate gateway before private-lead amendment')
    for name in ('gpu.json','private-lead/gpu.json'):
        p=prefix/'state/gate'/name
        if p.exists():
            d=json.loads(p.read_text())
            if d.get('phase')!='OFFLINE' or any(d.get(k) for k in ('pod_id','pod_name','allocation_uncertain')): raise ValueError('Unresolved GPU ownership; preserve cleanup')
def rendered_settings(prefix):
    data=(ROOT/'gate/SETTINGS.json').read_text()
    values={'@PYTHON@':str(ROOT/'.venv/bin/python'),'@STATE@':str(prefix/'state'),'@CONFIG@':str(prefix/'config')}
    for old,new in values.items(): data=data.replace(old,new)
    d=json.loads(data); d['private_lead']['enabled']=True; d['private_lead']['auto_start']=False
    return json.dumps(d,indent=2)+'\n'
def apply(prefix):
    op.verify(); receipt=op.verify_install(prefix); safe(prefix)
    record=prefix/'state/amendments'/('private-lead-'+str(time.time_ns())); op.private(record)
    before={}
    for name in FILES:
        target=prefix/'gate'/name; before[name]='present' if target.exists() else 'absent'
        if target.exists():
            if target.is_symlink(): raise ValueError('Unsafe installed gate file')
            backup=record/'gate'/name; backup.parent.mkdir(parents=True,exist_ok=True,mode=0o700); shutil.copy2(target,backup)
    shutil.copy2(prefix/'gate/FREEZE.json',record/'gate/FREEZE.json'); shutil.copy2(prefix/'receipt.json',record/'receipt.json')
    for name in FILES:
        target=prefix/'gate'/name; target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        data=rendered_settings(prefix) if name=='SETTINGS.json' else (ROOT/'gate'/name).read_text()
        atomic(target,data)
    freeze=json.loads((prefix/'gate/FREEZE.json').read_text())
    for name in FILES: freeze[name]=sha(prefix/'gate'/name)
    atomic(prefix/'gate/FREEZE.json',json.dumps(freeze,indent=2)+'\n')
    receipt['files'].update({'gate/'+name:sha(prefix/'gate'/name) for name in FILES}); receipt['files']['gate/FREEZE.json']=sha(prefix/'gate/FREEZE.json')
    atomic(prefix/'receipt.json',json.dumps(receipt,indent=2)+'\n')
    atomic(record/'transaction.json',json.dumps({'schema':'sanctum-private-lead-amendment/v1','before':before,'files':list(FILES)},indent=2)+'\n'); op.write(record/'complete','complete\n')
    print('Applied staged PRIVATE_LEAD amendment. Private rollback record: '+str(record))
def rollback(prefix,record):
    safe(prefix); record=record.absolute()
    if not record.is_relative_to((prefix/'state/amendments').absolute()): raise ValueError('Rollback record must belong to prefix')
    tx=json.loads((record/'transaction.json').read_text())
    for name,state in tx['before'].items():
        target=prefix/'gate'/name
        if state=='present': atomic(target,(record/'gate'/name).read_text())
        else: target.unlink(missing_ok=True)
    atomic(prefix/'gate/FREEZE.json',(record/'gate/FREEZE.json').read_text()); atomic(prefix/'receipt.json',(record/'receipt.json').read_text())
    print('Restored prior accepted private runtime files; 80B cache and state were preserved.')
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--prefix',type=Path,required=True); g=p.add_mutually_exclusive_group(required=True); g.add_argument('--apply',action='store_true'); g.add_argument('--rollback',type=Path); a=p.parse_args()
    try: apply(a.prefix.absolute()) if a.apply else rollback(a.prefix.absolute(),a.rollback)
    except (ValueError,OSError,KeyError) as e: raise SystemExit('REFUSED: '+str(e))
