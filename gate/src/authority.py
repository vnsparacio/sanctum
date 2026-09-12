"""Purpose-bound, one-use authority supplied only by the authenticated Mac gate."""
import hashlib
import hmac
import math
import re
import time
from pathlib import Path
from common import BASE, Refused, canonical, database, strict_json

OPERATIONS = {'classify','infer','media','close','status','sweep','stop','resume'}

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
    if b['operation'] == 'infer':
        if b['tier'] not in ['PRIVATE_80B','HOSTED_235B','MULTIMODAL','OPENAI_FRONTIER']: raise Refused('tier_contract')
        if b['approval'] not in ['exact_disclosure','session_private_prompt']: raise Refused('answer_approval')
        if b['approval'] == 'session_private_prompt' and (b['tier'] != 'PRIVATE_80B' or set(b['packet']) != {'prompt'}): raise Refused('session_grant_scope')
        if b['tier'] != 'OPENAI_FRONTIER' and b['state'].get('high_stakes') is not False: raise Refused('high_stakes_route')
        if b['state'].get('privacy_floor') != 'PERSONAL': raise Refused('privacy_floor')
    if b['operation'] in ['classify','infer']:
        if b['state'].get('scope') != b['scope'] or type(b['state'].get('high_stakes')) is not bool: raise Refused('state_contract')
        prompt = b['packet'].get('prompt')
        if type(prompt) is not str or not prompt.strip() or len(prompt.encode()) > settings['max_context_bytes']: raise Refused('prompt_contract')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bsk-or-v1-[A-Za-z0-9]{24,}|\bAKIA[0-9A-Z]{16}\b', canonical(b['packet'])): raise Refused('credential_format')
    with database(settings['state_directory']) as c:
        c.execute('insert into nonces values (?,?)', (b['nonce'], b['expires']))
    return b
