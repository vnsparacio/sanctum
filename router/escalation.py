"""Deterministic escalation policy. Operator/runtime API; never a model-visible tool.
Uses existing source privacy and routing policy. No network implementation is enabled.
"""
from dataclasses import dataclass, field
from pathlib import Path
import json,sys
from router import load_policy, route_request
from provenance import load_registry, tool_to_source

HERE=Path(__file__).resolve().parent
REASONS={'TOOL_VALIDATION_FAILED','TOOL_INCOMPATIBILITY_REPEATED','VERIFICATION_FAILED','TOOL_PLAN_FAILED','COMPLEX_STRUCTURED_TASK','SEMANTIC_QUALITY_REQUIRED'}

@dataclass(frozen=True)
class TrustedContext:
    # Must be constructed by local host code, never from model-provided classifications.
    sources: tuple= ('unknown',)
    session_privacy: str='UNKNOWN'
    task: str='tool_select'
    tags: tuple=()
    quality: str='normal'
    context_tokens: int=0
    current_tier: str='4b'


def decide(context, *, reason=None, incompatibilities=0, provider_config=None):
    if not isinstance(context,TrustedContext): raise TypeError('trusted context required')
    policy=load_policy(HERE/'policy.json')
    config=provider_config or {'80b':None,'235b':None}
    if reason is not None and reason not in REASONS: raise ValueError('unknown reason')
    if context.current_tier not in ('4b','80b','235b'): raise ValueError('invalid tier')
    sources=list(context.sources) or ['unknown']
    if context.session_privacy!='CLEAN': sources.append('credentials' if context.session_privacy=='RESTRICTED' else 'unknown')
    task=context.task
    if reason in ('TOOL_VALIDATION_FAILED','TOOL_PLAN_FAILED','VERIFICATION_FAILED'): task='analyze'
    if reason=='TOOL_INCOMPATIBILITY_REPEATED' and incompatibilities<2: reason=None
    decision=route_request(policy,sources,list(context.tags),task,context.context_tokens,context.quality,'unavailable','available')
    if reason is None and decision['difficulty']!='EASY': reason='SEMANTIC_QUALITY_REQUIRED' if decision['difficulty']=='VERY_HARD' else 'COMPLEX_STRUCTURED_TASK'
    required=reason is not None
    if not required: target=None
    elif context.current_tier=='235b': target=None
    elif context.current_tier=='80b' or reason=='SEMANTIC_QUALITY_REQUIRED' or decision['difficulty']=='VERY_HARD': target='235b'
    else: target='80b'
    privacy_allowed=decision['hosted_egress_allowed'] and decision['privacy']=='PUBLIC' and context.session_privacy=='CLEAN'
    configured=bool(target and config.get(target))
    outcome='LOCAL_CONTINUES' if not required else 'TIER_EXHAUSTED' if target is None else 'PRIVACY_BLOCKED' if not privacy_allowed else 'PROVIDER_NOT_CONFIGURED' if not configured else 'DRY_RUN_READY'
    return {'initial_model':'qwen-4b','current_tier':context.current_tier,'escalated':False,'escalation_required':required,'reason':reason,'target':target,'privacy':decision['privacy'],'privacy_allowed':privacy_allowed,'provider_configured':configured,'remote_call_permitted':False,'final_outcome':outcome}


def dispatch(context, *, reason, payload, provider_config=None, mock=None):
    """Dry-run/mock transport only. A configured endpoint is not egress authorization.
    Production activation must bind the existing exact-request approval/egress executor.
    Mock receives no prompt/body, so test code cannot accidentally forward private content.
    """
    d=decide(context,reason=reason,provider_config=provider_config)
    if d['final_outcome']=='DRY_RUN_READY' and mock is not None:
        mock({'target':d['target'],'reason':d['reason']})
        return {**d,'final_outcome':'MOCK_COMPLETED','mock_called':True}
    return d

if __name__=='__main__':
    try:
        event=json.loads(sys.stdin.read(4097))
        registry=load_registry(HERE/'source_registry.json')
        source,_=tool_to_source(registry,event.get('tool','unknown'),'private')
        # Hook contexts cannot prove current prompt declassification: fail closed.
        context=TrustedContext(sources=(source,),session_privacy='UNKNOWN')
        print(json.dumps(decide(context,reason=event['reason'],incompatibilities=event.get('incompatibilities',0))))
    except Exception:
        print(json.dumps({'initial_model':'qwen-4b','escalated':False,'remote_call_permitted':False,'final_outcome':'POLICY_UNAVAILABLE'}))
