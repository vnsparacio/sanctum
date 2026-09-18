"""One exact-production-schema PRIVATE_LEAD transport probe. No fallback or retry."""
from pathlib import Path
import argparse,json,os,secrets,shutil,subprocess,sys
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'src'))
from common import Refused,load_settings
from lifecycle import PrivateLeadLifecycle

SURFACES=('ordinaryIneligible','ordinaryEligible','researchIneligible','researchEligible','testOnlyIneligible','reviewer')
def production_request(node,surface):
 result=subprocess.run([node,str(BASE/'preflight-work-intent.mjs'),'--json'],capture_output=True,text=True,timeout=30)
 try:value=json.loads(result.stdout);row=value['schemas'][surface];request=row['request']
 except (json.JSONDecodeError,KeyError,TypeError):raise Refused('structured_schema_preflight') from None
 if result.returncode or value.get('ok') is not True or row.get('schemaDigest')!=request.get('schemaDigest'):raise Refused('structured_schema_preflight')
 return request,value['manifestDigest']
def main(prefix,surface):
 env=json.loads((prefix/'config/environment.json').read_text());os.environ.update({k:str(v) for k,v in env.items()})
 node=shutil.which('node')
 if not node:raise Refused('structured_schema_preflight')
 intent,manifest_digest=production_request(node,surface)
 profile=json.loads((BASE/'runtime/private-lead-interface-profile.json').read_text())
 scope=secrets.token_hex(16)
 terminal_kinds=[branch.get('properties',{}).get('kind',{}).get('const') for branch in intent['schema'].get('oneOf',[]) if branch.get('properties',{}).get('kind',{}).get('const') in {'FINAL','ESCALATION'}]
 requested='FINAL with text READY' if 'FINAL' in terminal_kinds else 'ESCALATION with reason BOUNDED_PROBE'
 request={'schema':'sanctum-capability/v1','requestId':scope,'scope':scope,'revision':0,'messages':[{'role':'system','content':'Return one semantic Work Intent from the exact schema.'},{'role':'user','content':'Return '+requested+'.'}],'manifestDigest':manifest_digest,'state':{'phase':'PLAN','iteration':0,'workIntent':intent}}
 result=PrivateLeadLifecycle(load_settings()).propose(scope,{'system':profile['prompt']['system'],'request':request})
 if result.get('status')!='OK' or result.get('result',{}).get('kind') not in {'FINAL','ESCALATION','TOOL_PROPOSAL'}:raise Refused('structured_transport_probe')
 telemetry=result.get('telemetry') or {}
 return {'status':'OK','surface':surface,'schemaVersion':intent['version'],'dialect':intent['dialect'],'schemaDigest':intent['schemaDigest'],'semanticSchemaDigest':intent['semanticSchemaDigest'],'resultKind':result['result']['kind'],'elapsedSeconds':telemetry.get('elapsed_seconds'),'promptTokens':telemetry.get('prompt_tokens'),'completionTokens':telemetry.get('completion_tokens')}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--prefix',type=Path,required=True);parser.add_argument('--surface',choices=SURFACES,default='ordinaryEligible');args=parser.parse_args()
 try:print(json.dumps(main(args.prefix.absolute(),args.surface),sort_keys=True))
 except (Refused,OSError,ValueError,KeyError,subprocess.SubprocessError) as error:raise SystemExit('REFUSED: '+(str(error) if type(error) is Refused else 'structured_transport_probe'))
