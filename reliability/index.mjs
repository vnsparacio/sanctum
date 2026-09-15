import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {isDeepStrictEqual} from 'node:util';
import {utilityTools} from './schemas.mjs';
import {compile,prepare,failure} from './runtime.mjs';
import {modelResult} from './output.mjs';
import {logger} from './telemetry.mjs';
import {rules} from './registry.mjs';
import {createVerification} from './verification.mjs';
import {deriveCapabilityManifest} from '../gate/foundation/manifest.mjs';
import {validateToolProposal} from '../gate/foundation/contracts.mjs';
const ROOT=path.dirname(fileURLToPath(import.meta.url));
export function python(script,payload,signal){
 return new Promise(resolve=>{
  const child=spawn('/usr/bin/python3',[script],{stdio:['pipe','pipe','ignore'],env:{PATH:'/usr/bin:/bin',PYTHONDONTWRITEBYTECODE:'1'}});
  let raw='',size=0,settled=false;
  const finish=value=>{if(settled)return;settled=true;clearTimeout(timer);signal?.removeEventListener('abort',abort);resolve(value);};
  const abort=()=>{child.kill('SIGKILL');finish(failure('CANCELLED','Operation cancelled.'));};
  const timer=setTimeout(()=>{child.kill('SIGKILL');finish(failure('UTILITY_TIMEOUT','Local utility timed out.'));},3000);
  child.on('error',()=>finish(failure('UTILITY_UNAVAILABLE')));
  child.stdout.on('data',chunk=>{size+=chunk.length;if(size>131072){child.kill('SIGKILL');finish(failure('OUTPUT_LIMIT'));}else raw+=chunk;});
  child.on('close',()=>{try{finish(JSON.parse(raw));}catch{finish(failure('UTILITY_UNAVAILABLE'));}});
  child.stdin.on('error',()=>{});
  if(signal?.aborted){abort();return;}
  signal?.addEventListener('abort',abort,{once:true});
  child.stdin.end(JSON.stringify(payload));
 });
}
export default {
 id:'vinceai-reliability',name:'Sanctum reliability',
 register(api){
  const schemas=JSON.parse(fs.readFileSync(path.join(ROOT,'schema-snapshot.json'),'utf8'));
  const validators=compile([...schemas.filter(s=>!utilityTools.some(u=>u.name===s.name)),...utilityTools]);
  // The capture supplies schemas; current runtime configuration supplies exposure.
  // Policy metadata is Mac-owned in the shared foundation, never model supplied.
  const manifest=deriveCapabilityManifest({schemas:[...schemas.filter(s=>!utilityTools.some(u=>u.name===s.name)),...utilityTools],declaredTools:[...validators.keys()],runtimeConfig:api.runtime?.config?.current?.()??{tools:{alsoAllow:[...validators.keys()]}}});
  const record=logger(path.join(process.env.VINCEAI_STATE_DIR ?? path.join(ROOT,'state'),'failures.jsonl'),[...validators.keys()],rules.map(r=>r.id));
  // Artifact pins prevent use of stale repair schemas after an owner/runtime upgrade.
  const pins=JSON.parse(fs.readFileSync(path.join(ROOT,'runtime-pins.json'),'utf8'));
  const intact=Object.entries(pins).every(([file,hash])=>{try{return createHash('sha256').update(fs.readFileSync(path.resolve(ROOT,'..',file))).digest('hex')===hash;}catch{return false;}});
  const calls=new Map(), failures=new Map(), preparedCalls=new Map(), gatewayPrepared=new Map();
  async function escalate(tool,reason,count){
   const decision=await python(path.join(ROOT,'../router/escalation.py'),{tool,reason,incompatibilities:count});
   record({tool,code:reason,target:decision.target,outcome:decision.final_outcome});
   return decision;
  }
  // OpenClaw may load tools, middleware and lifecycle hooks in distinct registry
  // instances. Keep bounded, process-local proofs shared across those instances.
  // No payload is persisted or exposed as a model tool.
  const verificationKey=Symbol.for('vinceai.reliability.exact-verification.v1');
  const verification=globalThis[verificationKey]??=createVerification({escalate,record});
  api.on('before_agent_finalize',(event,ctx)=>verification.finalize(event,ctx),{priority:2000});
  api.on('reply_payload_sending',event=>verification.delivery(event),{priority:2000});
  api.on('agent_end',(event,ctx)=>verification.end(event.runId??ctx?.runId));
  api.on('before_tool_call',async(event,ctx)=>{
   if(verification.proposed(ctx?.runId??event.runId,event.toolName))return {block:true,blockReason:JSON.stringify(failure('VERIFICATION_FAILED','Exact-answer verification failed. No further tools may execute in this run.'))};
   if(!intact){record({tool:event.toolName,code:'UNKNOWN_SCHEMA',outcome:'BLOCKED'});return {block:true,blockReason:JSON.stringify(failure('SCHEMA_SNAPSHOT_STALE','Operator must recapture schemas after a runtime upgrade.'))};}
   const proposal=validateToolProposal({schema:'sanctum-capability/v1',proposalId:String(event.toolCallId??ctx?.toolCallId??'unknown'),requestId:String(ctx?.runId??event.runId??'local'),revision:0,reasoner:'LOCAL_4B',capability:event.toolName,capabilityDigest:manifest.byName.get(event.toolName)?.digest??'0'.repeat(64),arguments:event.params},manifest);
   if(!proposal.ok){record({tool:event.toolName,code:proposal.code,outcome:'BLOCKED'});return {block:true,blockReason:JSON.stringify(failure(proposal.code))};}
   let p=prepare(event.toolName,event.params,validators);
   const key=`${ctx?.runId??event.runId??'unknown'}:${event.toolCallId??ctx?.toolCallId??'unknown'}`;
   const prior=preparedCalls.get(key);preparedCalls.delete(key);
   if(prior&&p.ok)p={...p,attempts:prior.attempts,rules:prior.rules,firstValid:prior.firstValid};
   if(calls.size>1024)calls.clear();calls.set(key,p);
   record({tool:event.toolName,code:p.code,attempts:p.attempts,rules:p.rules,repair_success:p.ok&&p.attempts===1,outcome:p.ok?(p.attempts?'REPAIRED':'VALID'):'BLOCKED'});
   if(!p.ok){const decision=await escalate(event.toolName,'TOOL_VALIDATION_FAILED');return {block:true,blockReason:JSON.stringify({...failure(p.code),escalation:decision})};}
   // The operator tools.invoke path skips owned preparation and shallow-merges
   // hook params. Retain this exact validated proposal, never a later rewrite.
   if(p.attempts&&utilityTools.some(t=>t.name===event.toolName)){
    const id=event.toolCallId??ctx?.toolCallId;
    if(id){if(gatewayPrepared.size>1024)gatewayPrepared.clear();gatewayPrepared.set(id,{tool:event.toolName,merged:{...event.params,...p.params},canonical:p.params});}
   }
   if(p.attempts)return {params:p.params};
  },{priority:2000});
  for(const utility of utilityTools)api.registerTool({...utility,label:utility.name,
   prepareBeforeToolCallParams(args,ctx){
    // OpenClaw merges hook params; field-removing aliases must run at its owned
    // preparation boundary so old keys cannot survive beside canonical fields.
    const p=prepare(utility.name,args,validators);
    if(p.ok&&p.attempts){
     const key=`${ctx?.hookContext?.runId??'unknown'}:${ctx?.toolCallId??'unknown'}`;
     if(preparedCalls.size>1024)preparedCalls.clear();preparedCalls.set(key,p);
     return p.params;
    }
    return args; // Invalid proposals still reach the fail-closed policy hook.
   },
   async execute(_id,args,signal){
   const cached=gatewayPrepared.get(_id);gatewayPrepared.delete(_id);
   if(cached?.tool===utility.name&&isDeepStrictEqual(args,cached.merged))args=cached.canonical;
   const prepared=prepare(utility.name,args,validators);
   if(!prepared.ok)return modelResult(utility.name,failure(prepared.code));
   const result=modelResult(utility.name,await python(path.join(ROOT,'utilities.py'),{tool:utility.name,args:prepared.params},signal));
   verification.proof(_id,utility.name,prepared.params,result.details);
   return result;
  }},{optional:true});
  api.registerAgentToolResultMiddleware(async(event,ctx)=>{
   verification.result(ctx?.runId,event.toolCallId,event.toolName,event.result?.details);
   const result=modelResult(event.toolName,event.result);
   const key=`${ctx?.runId??'unknown'}:${event.toolCallId}`;const p=calls.get(key);calls.delete(key);
   if(p?.rules.length){result.details.repair={rules:p.rules,attempts:p.attempts};if(p.rules.includes('bounded_limit'))result.details.truncated=true;result.content[0].text=JSON.stringify(result.details);}
   const failed=result.isError;
   record({tool:event.toolName,attempts:p?.attempts,rules:p?.rules,status:failed?'error':'ok',outcome:failed?'FAILED':'SUCCESS'});
   if(failed&&result.details?.error?.code==='INCOMPATIBLE_ARGUMENT'){
    const run=ctx?.runId;if(run){const k=`${run}:${event.toolName}`;const n=(failures.get(k)??0)+1;if(failures.size>1024)failures.clear();failures.set(k,n);if(n===2)result.details.escalation=await escalate(event.toolName,'TOOL_INCOMPATIBILITY_REPEATED',n);}
    result.content[0].text=JSON.stringify(result.details);
   }
   return {result};
  },{runtimes:['openclaw']});
  // Read-only metadata for trusted diagnostics/tests; it contains schemas and
  // policy labels, never private runtime state or approval material.
  api.capabilityManifest=manifest;
 }
};
