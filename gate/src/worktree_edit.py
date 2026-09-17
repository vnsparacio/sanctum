"""Exact UTF-8 replacements. Observation and mutation authority are Mac-owned."""
import contextlib, fcntl, hashlib, os, secrets, stat, subprocess, tempfile
from pathlib import Path
from common import Refused, atomic, canonical, strict_json
import task_evidence
from workspace import GIT, GIT_ENV

MAX_FILE=1024*1024
RECOVER={'EDIT_SOURCE_NOT_OBSERVED','EDIT_SOURCE_STALE','EDIT_TARGET_NOT_FOUND','EDIT_TARGET_NOT_UNIQUE'}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def fail(code):return {'ok':False,'code':code,'executionState':'NOT_STARTED'}
def validate(arguments):
    if type(arguments) is not dict or set(arguments)!={'path','old_text','new_text'} or any(type(v) is not str for v in arguments.values()) or not arguments['old_text']:return 'EDIT_SCHEMA_INVALID'
    try:old=arguments['old_text'].encode('utf-8');new=arguments['new_text'].encode('utf-8')
    except UnicodeEncodeError:return 'EDIT_ENCODING_UNSUPPORTED'
    if len(old)>4096 or len(new)>8192:return 'EDIT_REPLACEMENT_TOO_LARGE'
    if b'\0' in old+new:return 'EDIT_ENCODING_UNSUPPORTED'
    try:task_evidence.path_name(arguments['path'])
    except Refused:return 'EDIT_PATH_INVALID'
    return None

@contextlib.contextmanager
def locked(settings,record):
    _,directory=task_evidence.load(settings,record)
    fd=os.open(directory/'editor.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        file=directory/'editor.json'
        state=strict_json(file.read_text()) if file.exists() else {'generation':0,'observations':{},'pending':{},'required':[]}
        yield state,directory
        atomic(file,(canonical(state)+'\n').encode())
    finally:os.close(fd)

@contextlib.contextmanager
def opened(root,path):
    """Anchor every component with O_NOFOLLOW directory descriptors."""
    try:task_evidence.path_name(path)
    except Refused:raise Refused('EDIT_PATH_INVALID') from None
    fds=[]
    try:
        current=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fds.append(current)
        for part in path.split('/')[:-1]:
            current=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=current);fds.append(current)
        name=path.split('/')[-1]
        fd=os.open(name,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=current);fds.append(fd)
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise Refused('EDIT_FILE_TYPE_UNSUPPORTED')
        if info.st_size>MAX_FILE:raise Refused('EDIT_REPLACEMENT_TOO_LARGE')
        chunks=[];remaining=MAX_FILE+1
        while remaining:
            block=os.read(fd,min(65536,remaining))
            if not block:break
            chunks.append(block);remaining-=len(block)
        raw=b''.join(chunks)
        after=os.fstat(fd)
        if identity(after)!=identity(info):raise Refused('EDIT_APPLY_RACE')
        if len(raw)>MAX_FILE:raise Refused('EDIT_REPLACEMENT_TOO_LARGE')
        if b'\0' in raw:raise Refused('EDIT_FILE_TYPE_UNSUPPORTED')
        try:raw.decode('utf-8')
        except UnicodeDecodeError:raise Refused('EDIT_ENCODING_UNSUPPORTED') from None
        yield current,name,fd,info,raw
    except OSError:raise Refused('EDIT_PATH_INVALID') from None
    finally:
        for fd in reversed(fds):os.close(fd)

def identity(info):return (info.st_dev,info.st_ino,info.st_mode,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns)

def read(settings,record,path,max_chars):
    if type(max_chars) is not int or not 1<=max_chars<=24000:raise Refused('workspace_read_limit')
    with locked(settings,record) as (state,_),opened(record['root'],path) as (_,__,fd,info,raw):
        text=raw.decode('utf-8');visible=text[:max_chars]
        observation={'task_id':record['workspace_id'],'workspace_id':record['workspace_id'],'path':path,'generation':state['generation'],'digest':sha(raw),'file_type':'UTF8_REGULAR','byte_length':len(raw),'ranges':[[0,len(visible.encode())]],'text':visible}
        token=sha(canonical(observation).encode());state['pending'][path]={'token':token,'observation':observation}
        # At most one pending read per path and a bounded task-wide inventory.
        if len(state['pending'])>128:state['pending'].pop(next(iter(state['pending'])))
        return {'path':path,'text':visible,'truncated':len(text)>max_chars,'size':len(raw),'_observation':token}

def observe(settings,record,path,token):
    """Called only by the host after result egress and context-size checks."""
    with locked(settings,record) as (state,_):
        pending=state['pending'].pop(path,None)
        if not pending or pending['token']!=token:raise Refused('workspace_observation_invalid')
        state['observations'][path]=pending['observation']
        if len(state['observations'])>128:state['observations'].pop(next(iter(state['observations'])))
        if path in state['required']:state['required'].remove(path)
    return {'ok':True}

def canonical_diff(path,before,after):
    # Git renders the exact two byte strings without repository attributes,
    # textconv, external drivers, newline conversion, or user configuration.
    with tempfile.TemporaryDirectory(prefix='sanctum-edit-diff-') as tmp:
        base=Path(tmp)
        for prefix,raw in (('a',before),('b',after)):
            p=base/prefix/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        result=subprocess.run(GIT+['diff','--no-index','--no-ext-diff','--no-textconv','--binary','--no-prefix','--',f'a/{path}',f'b/{path}'],cwd=base,env=GIT_ENV,capture_output=True,timeout=30)
        if result.returncode!=1 or not result.stdout or len(result.stdout)>48000:raise Refused('EDIT_REPLACEMENT_TOO_LARGE')
        return result.stdout

def mutation_authority(settings,record,diff):
    # Reuse the existing actual-mutation authority/protection assessment.
    assessment=task_evidence.patch_assessment(settings,record,diff.decode('utf-8'))
    return {'outcome':'ALLOW' if assessment=='PASS' else 'DENY','canonical_diff_digest':sha(diff),'reason':assessment}

def apply(settings,record,arguments,authorize=mutation_authority):
    error=validate(arguments)
    if error:return fail(error)
    path=arguments['path'];old=arguments['old_text'].encode();new=arguments['new_text'].encode()
    result=None
    try:
        with locked(settings,record) as (state,directory):
            result=_apply(settings,record,arguments,state,directory,authorize,old,new)
            if result.get('ok') or result.get('code') in RECOVER:
                if path not in state['required']:state['required'].append(path)
                state['observations'].pop(path,None)
        return result
    except Exception:
        uncertain=result is not None and (result.get('ok') or result.get('executionState')=='COMPLETION_UNKNOWN')
        return {'ok':False,'code':'EDIT_STATE_UNAVAILABLE','executionState':'COMPLETION_UNKNOWN' if uncertain else 'NOT_STARTED'}

def _apply(settings,record,args,state,directory,authorize,old,new):
    path=args['path'];value,_=task_evidence.load(settings,record);contract=value['contract']
    fold=path.casefold()
    if any(fold==p.casefold() or fold.startswith(p.casefold()+'/') or p.casefold().startswith(fold+'/') for p in contract['protected']):return fail('EDIT_PROTECTED_INPUT')
    if contract['mutable']!='*' and path not in contract['mutable']+contract['mutable_tests']:return fail('EDIT_PATH_NOT_MUTABLE')
    temp=None;written=False
    try:
        with opened(record['root'],path) as (parent,name,fd,info,raw):
            observation=state['observations'].get(path)
            if path in state['required'] or not observation:return fail('EDIT_SOURCE_NOT_OBSERVED')
            if observation['task_id']!=record['workspace_id'] or observation['workspace_id']!=record['workspace_id']:return fail('EDIT_SOURCE_NOT_OBSERVED')
            if sha(raw)!=observation['digest']:return fail('EDIT_SOURCE_STALE')
            # Count overlapping matches too; no choice of occurrence is inferred.
            matches=[];start=0
            while len(matches)<2:
                at=raw.find(old,start)
                if at<0:break
                matches.append(at);start=at+1
            if not matches:return fail('EDIT_TARGET_NOT_FOUND')
            if len(matches)!=1:return fail('EDIT_TARGET_NOT_UNIQUE')
            if old not in observation['text'].encode():return fail('EDIT_SOURCE_NOT_OBSERVED')
            if old==new:return fail('EDIT_NO_CHANGE')
            at=matches[0];candidate=raw[:at]+new+raw[at+len(old):]
            if len(candidate)>MAX_FILE:return fail('EDIT_REPLACEMENT_TOO_LARGE')
            before=task_evidence.check(settings,record)
            if before['integrity']!='PASS':return fail('EDIT_PROTECTED_INPUT')
            diff=canonical_diff(path,raw,candidate)
            decision=authorize(settings,record,diff)
            if decision.get('outcome')!='ALLOW' or decision.get('canonical_diff_digest')!=sha(diff):return fail('EDIT_AUTHORITY_DENIED')
            temp='.sanctum-edit-'+secrets.token_hex(16)
            out=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            try:
                with os.fdopen(out,'wb',closefd=False) as stream:stream.write(candidate);stream.flush()
                os.fchmod(out,stat.S_IMODE(info.st_mode));os.fsync(out)
            finally:os.close(out)
            # Every supported host workspace operation shares the task lock.
            # Candidate commands have a copy, never a live host mount.
            # Exclude only this host-created temporary from the final inventory.
            rows=task_evidence.inventory(record['root']);rows.pop('/'.join(path.split('/')[:-1]+[temp]),None)
            if task_evidence.digest(task_evidence.content_identity(rows))!=before['candidateDigest']:return fail('EDIT_APPLY_RACE')
            expected=task_evidence.content_identity(rows)
            expected[path]={**expected[path],'digest':sha(candidate),'size':len(candidate)}
            artifact='edit-'+str(state['generation']+1)
            atomic(directory/(artifact+'.proposal.json'),(canonical(args)+'\n').encode())
            atomic(directory/(artifact+'.before'),raw)
            with opened(record['root'],path) as (p2,n2,f2,i2,r2):
                if identity(i2)!=identity(info) or r2!=raw or identity(os.fstat(parent))[:2]!=identity(os.fstat(p2))[:2]:return fail('EDIT_APPLY_RACE')
                os.replace(temp,name,src_dir_fd=parent,dst_dir_fd=parent);temp=None;written=True
            state['generation']+=1
            after=task_evidence.check(settings,record)
            if after['candidateDigest']!=task_evidence.digest(expected):return {'ok':False,'code':'EDIT_APPLY_RACE','executionState':'COMPLETION_UNKNOWN'}
            if after['integrity']!='PASS':return {'ok':False,'code':'PROTECTED_INPUT_MODIFIED','executionState':'COMPLETION_UNKNOWN'}
            with opened(record['root'],path) as (_,__,___,____,actual):
                if actual!=candidate:return {'ok':False,'code':'EDIT_APPLY_RACE','executionState':'COMPLETION_UNKNOWN'}
            receipt={'old_digest':sha(raw),'new_digest':sha(candidate),'canonical_diff_digest':sha(diff),'workspace_generation':state['generation'],'proposal_digest':sha(canonical(args).encode()),'authority_result':decision['outcome'],'host_invention_count':0,'fuzzy_match_count':0,'diff_correspondence':True}
            # Private diff is an audit artifact, never an authority grant.
            atomic(directory/('edit-'+str(state['generation'])+'.diff'),diff)
            atomic(directory/('edit-'+str(state['generation'])+'.json'),(canonical(receipt)+'\n').encode())
            return {'ok':True,'code':'OK','executionState':'COMPLETED','receipt':receipt}
    except Refused as error:
        code=str(error) if str(error).startswith('EDIT_') else 'EDIT_PROTECTED_INPUT'
        return {'ok':False,'code':code,'executionState':'COMPLETION_UNKNOWN' if written else 'NOT_STARTED'}
    except Exception:return {'ok':False,'code':'EDIT_APPLY_RACE','executionState':'COMPLETION_UNKNOWN' if written else 'NOT_STARTED'}
    finally:
        if temp:
            # parent may already be closed by the context manager; use a fresh
            # anchored directory only if it is still the same directory.
            try:
                with opened(record['root'],path) as (p,_,__,___,____):os.unlink(temp,dir_fd=p)
            except (OSError,Refused):pass
