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


def execute(b, settings, remote=None, lifecycle=None):
    op=b['operation']; scope=b['scope']
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
    lc=lifecycle or Private80BLifecycle(settings)
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
