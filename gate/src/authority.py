"""Purpose-bound, one-use authority supplied only by the authenticated Mac gate."""
import hashlib
import hmac
import math
import re
import time
from pathlib import Path
from experiment import validate_binding
from common import BASE, Refused, canonical, database, strict_json

OPERATIONS = {'classify','infer','private_lead_propose','media','close','status','sweep','stop','resume',
              'worktree_integrity','worktree_acceptance','worktree_create','worktree_list','worktree_read','worktree_patch','worktree_command','worktree_cleanup','work_source_policy'}

def authorize(envelope, settings, now=time.time, settings_hash=None):
    if type(envelope) is not dict or set(envelope) != {'body','mac'} or type(envelope['body']) is not str or len(envelope['body'].encode()) > 200000:
        raise Refused('invalid_envelope')
    keyfile = Path(settings['state_directory']) / 'authority.key'
    if keyfile.is_symlink() or keyfile.stat().st_mode & 0o077: raise Refused('unsafe_authority_key')
    expected = hmac.new(keyfile.read_bytes(), envelope['body'].encode(), hashlib.sha256).hexdigest()
    if type(envelope['mac']) is not str or not hmac.compare_digest(expected, envelope['mac']): raise Refused('invalid_signature')
    b = strict_json(envelope['body'])
    required = {'operation','tier','packet','state','nonce','expires','spec_sha256','scope','approval','strong'}
    if type(b) is not dict or set(b) != required or b['operation'] not in OPERATIONS: raise Refused('operation_contract')
    if type(b['expires']) not in (int,float) or not math.isfinite(b['expires']) or not now() < b['expires'] <= now()+310: raise Refused('expired')
    if b['spec_sha256'] != (settings_hash or hashlib.sha256((BASE/'SETTINGS.json').read_bytes()).hexdigest()): raise Refused('settings_drift')
    if not re.fullmatch('[a-f0-9]{64}', str(b['nonce'])) or not re.fullmatch('[a-f0-9]{32}', str(b['scope'])): raise Refused('invalid_identity')
    if type(b['strong']) is not bool or type(b['packet']) is not dict: raise Refused('packet_contract')
    if b['operation'] == 'classify' and (b['tier'] != 'GEMINI_AUDIT' or b['approval'] != 'exact_disclosure'): raise Refused('classification_approval')
    if b['tier'] == 'PRIVATE_80B' and b['operation'] not in ('status','close','stop','sweep'):
        raise Refused('private_80b_retired')
    if b['operation'] == 'infer':
        if b['tier'] not in ['PRIVATE_80B','PRIVATE_LEAD','HOSTED_235B','MULTIMODAL','OPENAI_FRONTIER']: raise Refused('tier_contract')
        if b['tier'] == 'PRIVATE_80B': raise Refused('private_80b_retired')
        if b['approval'] not in ['exact_disclosure','session_private_prompt']: raise Refused('answer_approval')
        if b['approval'] == 'session_private_prompt' and (b['tier'] != 'PRIVATE_80B' or set(b['packet']) != {'prompt'}): raise Refused('session_grant_scope')
        if b['tier'] != 'OPENAI_FRONTIER' and b['state'].get('high_stakes') is not False: raise Refused('high_stakes_route')
        if b['state'].get('privacy_floor') != 'PERSONAL': raise Refused('privacy_floor')
    if b['operation'] == 'private_lead_propose':
        # This is a data-only, staged role. The signed Mac coordinator supplies
        # the bounded prompt and capability view; the model never receives an
        # approval, an executor, or authority to run its proposal.
        if b['tier'] != 'PRIVATE_LEAD' or b['approval'] != 'private_lead_workmode': raise Refused('private_lead_proposal_scope')
        if b['state'].get('privacy_floor') != 'PERSONAL' or b['state'].get('high_stakes') is not False: raise Refused('private_lead_proposal_state')
        if set(b['packet']) not in ({'request'},{'request','experiment'}) or type(b['packet']['request']) is not dict: raise Refused('private_lead_proposal_packet')
        if 'experiment' in b['packet']: validate_binding(b['packet']['experiment'])
        raw = canonical(b['packet']['request'])
        if len(raw.encode()) > min(settings['max_context_bytes'], 196608): raise Refused('private_lead_proposal_limit')
    if b['operation'].startswith('work'):
        if b['tier'] != 'PRIVATE_LEAD' or b['approval'] != 'private_lead_workmode': raise Refused('workmode_operation_scope')
        if b['state'].get('privacy_floor') != 'PERSONAL' or b['state'].get('high_stakes') is not False: raise Refused('workmode_operation_state')
        if b['state'].get('scope') != b['scope'] or type(b['state'].get('revision')) is not int or b['state']['revision'] < 0: raise Refused('workmode_operation_state')
        packet=b['packet']
        if packet.get('task_id') != b['scope'] or not re.fullmatch('[a-f0-9]{32}',str(packet.get('task_id',''))): raise Refused('workmode_task_scope')
        contracts={
            'worktree_integrity':{'task_id','profile'},'worktree_acceptance':{'task_id','profile'},
            'worktree_create':{'task_id','profile'},'worktree_list':{'task_id','path','max_entries'},
            'worktree_read':{'task_id','path','max_chars'},'worktree_patch':{'task_id','patch'},
            'worktree_command':{'task_id','operation','profile'},'worktree_cleanup':{'task_id','profile'},
            'work_source_policy':{'task_id','prompt','source_need'},
        }
        if set(packet)!=contracts[b['operation']]: raise Refused('workmode_packet_contract')
        if 'profile' in packet and not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,31}',str(packet['profile'])): raise Refused('workmode_profile')
        if b['operation']=='worktree_list' and (type(packet['path']) is not str or type(packet['max_entries']) is not int): raise Refused('workmode_packet_contract')
        if b['operation']=='worktree_read' and (type(packet['path']) is not str or type(packet['max_chars']) is not int): raise Refused('workmode_packet_contract')
        if b['operation']=='worktree_patch' and (type(packet['patch']) is not str or len(packet['patch'].encode())>48000): raise Refused('workmode_packet_contract')
        if b['operation']=='worktree_command' and packet['operation'] not in {'status','diff','test','lint','build'}: raise Refused('workmode_packet_contract')
        if b['operation']=='work_source_policy' and (type(packet['prompt']) is not str or len(packet['prompt'].encode())>32768 or packet['source_need'] not in {'WEB_HELPFUL','WEB_REQUIRED'}): raise Refused('workmode_packet_contract')
    if b['operation'] in ['classify','infer']:
        if b['state'].get('scope') != b['scope'] or type(b['state'].get('high_stakes')) is not bool: raise Refused('state_contract')
        prompt = b['packet'].get('prompt')
        if type(prompt) is not str or not prompt.strip() or len(prompt.encode()) > settings['max_context_bytes']: raise Refused('prompt_contract')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bsk-or-v1-[A-Za-z0-9]{24,}|\bAKIA[0-9A-Z]{16}\b', canonical(b['packet'])): raise Refused('credential_format')
    with database(settings['state_directory']) as c:
        c.execute('insert into nonces values (?,?)', (b['nonce'], b['expires']))
    return b
