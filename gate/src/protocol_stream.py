"""Bounded content-JSON transport. Diagnostics contain fixed structural facts only."""
import http.client,math,time,urllib.error
from common import Refused,strict_json

def finite_json(raw):
    """Check parsed numeric values, including exponent overflow, without coercion."""
    value=strict_json(raw);pending=[value]
    while pending:
        item=pending.pop()
        if type(item) is float and not math.isfinite(item):raise Refused('nonfinite_json')
        if type(item) is dict:pending.extend(item.values())
        elif type(item) is list:pending.extend(item)
    return value

def safe_diagnostic(value):
    """Re-allowlist at the worker output boundary, including exception attributes."""
    value=value if type(value) is dict else {}
    allowed={'stage':('STREAM','JSON_PARSE','BACKEND_RESULT'),
      'validatorVersion':('stream/v1','json/v1','backend-result/v1'),
      'resultKind':('FINAL','ESCALATION','TOOL_PROPOSAL'),
      'field':('root',),'keyword':('syntax','duplicateKey','nonfinite','completion','toolCalls','refusal','choices','limit','enum','type'),
      'receivedType':('object','array','string','number','boolean','null','undefined'),
      'streamStatus':('COMPLETE','INCOMPLETE','NOT_STREAMED'),
      'finishStatus':('stop','length','tool_calls','content_filter'),
      'parseStatus':('BEFORE_PARSE','PARSED','FAILED'),'normalization':('UNCHANGED','NOT_REACHED')}
    result={'schema':'sanctum-protocol-diagnostic/v1'}
    for key,choices in allowed.items():result[key]=value.get(key) if value.get(key) in choices else 'UNKNOWN'
    for key in ('stringLength','unknownFieldCount'):
        number=value.get(key);result[key]=min(number,65537) if type(number) is int and number>=0 else None
    result['patternMatch']=value.get('patternMatch') if type(value.get('patternMatch')) is bool else None
    result['missingField']=value.get('missingField') is True
    return result

def rejection(code,stage,keyword,*,stream_status='UNKNOWN',finish=None,parsed=False,value=None):
    kind=value.get('kind') if type(value) is dict else None
    diagnostic={'schema':'sanctum-protocol-diagnostic/v1','stage':stage,
      'validatorVersion':{'STREAM':'stream/v1','JSON_PARSE':'json/v1','BACKEND_RESULT':'backend-result/v1'}[stage],
      'resultKind':kind if kind in ('FINAL','ESCALATION','TOOL_PROPOSAL') else 'UNKNOWN',
      'field':'root','keyword':keyword,'receivedType':{dict:'object',list:'array',str:'string',int:'number',float:'number',bool:'boolean',type(None):'null'}.get(type(value),'UNKNOWN'),
      'stringLength':min(len(value),65537) if type(value) is str else None,
      'patternMatch':None,'missingField':False,'unknownFieldCount':None,
      'streamStatus':stream_status,'finishStatus':finish if finish in ('stop','length','tool_calls','content_filter') else 'UNKNOWN',
      'parseStatus':'PARSED' if parsed else 'FAILED' if stage=='JSON_PARSE' else 'BEFORE_PARSE','normalization':'NOT_REACHED'}
    error=Refused(code);error.diagnostic=diagnostic;return error

def completion_stream(response):
    parts=[];size=0;wire_size=0;first=None;finish=None;usage={};done=False
    def fail(keyword):return rejection('answer_incomplete','STREAM',keyword,stream_status='INCOMPLETE',finish=finish)
    lines=iter(response)
    while True:
        try:raw=next(lines)
        except StopIteration:break
        except urllib.error.HTTPError:raise
        except (OSError,http.client.IncompleteRead):raise fail('completion') from None
        wire_size+=len(raw)
        if len(raw)>131072 or wire_size>2097152:raise fail('limit')
        try:line=raw.decode('utf-8','strict').strip()
        except UnicodeError:raise fail('syntax') from None
        if not line.startswith('data:'):continue
        data=line[5:].strip()
        if data=='[DONE]':done=True;break
        try:row=finite_json(data)
        except (ValueError,RecursionError) as error:
            raise fail('nonfinite' if type(error) is Refused and str(error)=='nonfinite_json' else 'syntax') from None
        if type(row) is not dict or row.get('error'):raise fail('syntax')
        if type(row.get('usage')) is dict:usage=row['usage']
        choices=row.get('choices',[])
        if type(choices) is not list or len(choices)>1:raise fail('choices')
        if not choices:continue
        choice=choices[0]
        if type(choice) is not dict or choice.get('index',0)!=0:raise fail('choices')
        delta=choice.get('delta') or {}
        if type(delta) is not dict:raise fail('type')
        if delta.get('tool_calls') or delta.get('function_call'):raise fail('toolCalls')
        if delta.get('refusal'):raise fail('refusal')
        piece=delta.get('content')
        if piece is not None and type(piece) is not str:raise fail('type')
        if piece:
            if finish is not None:raise fail('completion')
            if first is None:first=time.monotonic()
            parts.append(piece);size+=len(piece)
            if size>65536:raise fail('limit')
        if choice.get('finish_reason') is not None:
            if finish is not None:raise fail('completion')
            finish=choice['finish_reason']
    if not done or finish!='stop':raise fail('completion')
    return ''.join(parts),usage,first,{'streamStatus':'COMPLETE','finishStatus':'stop'}

def parse_result(text,status):
    try:value=finite_json(text)
    except (ValueError,RecursionError) as error:
        keyword={'duplicate_json_key':'duplicateKey','nonfinite_json':'nonfinite'}.get(str(error),'syntax') if type(error) is Refused else 'syntax'
        raise rejection('private_lead_result_schema','JSON_PARSE',keyword,stream_status=status['streamStatus'],finish=status['finishStatus']) from None
    if type(value) is not dict or value.get('kind') not in ('FINAL','ESCALATION','TOOL_PROPOSAL'):
        raise rejection('private_lead_result_schema','BACKEND_RESULT','enum',stream_status=status['streamStatus'],finish=status['finishStatus'],parsed=True,value=value)
    return value
