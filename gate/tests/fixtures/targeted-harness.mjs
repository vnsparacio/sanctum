import {syntheticProtection} from './task-evidence.mjs';
import assert from 'node:assert/strict';
import {cpSync,mkdirSync,mkdtempSync,readFileSync,readdirSync,rmSync,writeFileSync} from 'node:fs';
import {join,relative} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {createHash,randomBytes} from 'node:crypto';
import {createExecutor} from '../../plugin/core.mjs';
import {createPrivateLeadReasoner} from '../../plugin/private-lead.mjs';
import {createWorkMode,MUTABLE_WORKTREE_COMPLETION_POLICY,WORKSPACE_EVIDENCE_VERSION} from '../../plugin/work-mode.mjs';
import {createWorkCommand} from '../../plugin/work-command.mjs';
import {createWorkLedger} from '../../plugin/work-ledger.mjs';
import {deriveCapabilityManifest,publishCapabilityManifest} from '../../foundation/manifest.mjs';
import {workModeTools} from '../../plugin/workspace-tools.mjs';
import {CONTRACT_VERSION,digest} from '../../foundation/contracts.mjs';

export const root=fileURLToPath(new URL('../../../',import.meta.url));
export const names=workModeTools.map(x=>x.name),ordinary=names.filter(x=>x!=='source_first_research');
export const manifest=deriveCapabilityManifest({schemas:workModeTools.map(x=>({name:x.name,description:x.description,parameters:x.parameters})),declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
export const scope='a'.repeat(32),valid={kind:'ESCALATION',reason:'BOUNDED_INABILITY'},bad={kind:'ESCALATION',reason:'INJECTED_PRIVATE bad reason'};
export const tool=(capability,args)=>({kind:'TOOL_PROPOSAL',capability,arguments:args});
export const plan=value=>({text:JSON.stringify(value)});
export const snapshot=(bytes=0)=>async({scope,workspace,turn})=>({schema:WORKSPACE_EVIDENCE_VERSION,scope,workspace,turn,diff:{ok:true,executionState:'COMPLETED',bytes,digest:'b'.repeat(64)},status:{ok:true,executionState:'COMPLETED',bytes,digest:'c'.repeat(64)}});
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
export function checkLedger(path){
 const raw=readFileSync(path,'utf8');assert.ok(!raw.includes('INJECTED_PRIVATE'));
 const rows=raw.trim().split('\n').map(JSON.parse);let previous='0'.repeat(64);
 for(const {eventDigest,...row} of rows){assert.equal(row.previousDigest,previous);assert.equal(digest(row),eventDigest);previous=eventDigest;}
 return rows;
}
export function signedHarness(plans){
 const dir=mkdtempSync(join(tmpdir(),'sanctum-targeted-')),pkg=join(dir,'package'),transport=join(dir,'transport'),state=join(dir,'state');
 for(const p of [pkg,transport,state])mkdirSync(p,{mode:0o700});
 cpSync(join(root,'gate/src'),join(pkg,'src'),{recursive:true,filter:p=>!p.includes('__pycache__')});
 cpSync(join(root,'gate/runtime'),join(pkg,'runtime'),{recursive:true});
 cpSync(join(root,'gate/worker.py'),join(pkg,'worker.py'));
 const key=Buffer.alloc(32,7),settings=JSON.parse(readFileSync(join(root,'gate/SETTINGS.json')));
 settings.state_directory=state;settings.python=join(root,'.venv/bin/python');
 writeFileSync(join(state,'authority.key'),key,{mode:0o600});
 writeFileSync(join(pkg,'SETTINGS.json'),JSON.stringify(settings),{mode:0o600});
 const files={};function walk(path){for(const entry of readdirSync(path,{withFileTypes:true})){const file=join(path,entry.name);if(entry.isDirectory())walk(file);else files[relative(pkg,file)]=sha(readFileSync(file));}}walk(pkg);
 writeFileSync(join(pkg,'FREEZE.json'),JSON.stringify(files));
 writeFileSync(join(transport,'worker.py'),`import runpy\nrunpy.run_path(${JSON.stringify(join(root,'gate/tests/fixtures/actual_protocol_worker.py'))},init_globals={'PACKAGE_ROOT':${JSON.stringify(pkg)},'FIXTURE_ROOT':${JSON.stringify(dir)}},run_name='__main__')\n`);
 const execute=createExecutor(transport,settings,key),captures=[],responses=[],bodies=[];let attempts=0;
 const dispatch=async(body,signal)=>{
  rmSync(join(dir,'request.json'),{force:true});
  writeFileSync(join(dir,'plan.json'),JSON.stringify(plans[Math.min(attempts,plans.length-1)]));attempts++;bodies.push(body);
  const response=await execute(body,signal);responses.push(response);
  try{captures.push(JSON.parse(readFileSync(join(dir,'request.json'))));}catch{}
  return response;
 };
 const body=(_op,_tier,packet)=>({operation:'private_lead_propose',tier:'PRIVATE_LEAD',packet,state:{scope,high_stakes:false,privacy_floor:'PERSONAL',revision:0},scope,approval:'private_lead_workmode',strong:false,nonce:randomBytes(32).toString('hex'),expires:Date.now()/1000+60,spec_sha256:sha(readFileSync(join(pkg,'SETTINGS.json')))});
 const profile=JSON.parse(readFileSync(join(root,'gate/runtime/private-lead-interface-profile.json')));
 const reasoner=createPrivateLeadReasoner({execute:dispatch,body,profile});
 return {dir,pkg,settings,key,reasoner,dispatch,execute,captures,responses,bodies,get attempts(){return attempts;},get endpointDispatches(){try{return readFileSync(join(dir,'dispatches.jsonl'),'utf8').trim().split('\n').length;}catch{return 0;}},close(){rmSync(dir,{recursive:true,force:true});}};
}
export async function leadRun(plans,{capabilities=ordinary,bytes=0}={}){
 const h=signedHarness(plans);let effects=0;
 try{
  const ledger=createWorkLedger({root:join(h.dir,'ledger'),taskId:scope,key:h.key,metadata:{goal:'essential goal'}});
  const result=await createWorkMode({reasoner:h.reasoner,manifest,completionPolicy:MUTABLE_WORKTREE_COMPLETION_POLICY,workspaceState:snapshot(bytes),
   authorize:(p,s,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:p.capability,proposalDigest:digest(p),scope,effect:s.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false}),
   egress:({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']}),
   invoke:async()=>{effects++;return {ok:true,data:{text:'synthetic observation'},executionState:'COMPLETED',verifier:'VERIFIED'};},evaluate:async()=>({passed:false}),onEvent:(kind,value)=>ledger.event(kind,value)}).run({task:'essential goal',scope,capabilities});
  const rows=checkLedger(join(h.dir,'ledger',scope,'events.jsonl'));
  const replay=await h.execute(h.bodies[0]);assert.equal(replay.status,'UNAVAILABLE');assert.equal(h.endpointDispatches,h.attempts);
  return {result,rows,effects,attempts:h.attempts,endpointDispatches:h.endpointDispatches,captures:h.captures,responses:h.responses};
 }finally{h.close();}
}
export async function reviewerRun(reviewPlan){
 const h=signedHarness([plan({kind:'FINAL',text:'synthetic completion'}),reviewPlan,plan({kind:'FINAL',text:'synthetic revised completion'})]);
 let handler;const settings=structuredClone(h.settings);
 try{
  settings.work_mode.enabled=true;settings.work_mode.profile_file=join(h.dir,'profiles.json');settings.work_mode.ledger_root=join(h.dir,'ledger');
  writeFileSync(settings.work_mode.profile_file,JSON.stringify({schema:'sanctum-work-mode-profiles/v1',profiles:{synthetic:{reviewer:true,evaluators:['test']}}}),{mode:0o600});
  settings.settingsFileHash=sha(readFileSync(join(h.pkg,'SETTINGS.json')));
  publishCapabilityManifest(manifest);
  handler=createWorkCommand({api:{},base:join(root,'gate'),settings,key:h.key,remote:async(body,signal)=>{
   if(body.operation==='private_lead_propose')return h.dispatch(body,signal);
   if(body.operation==='worktree_integrity')return {status:'OK',result:await syntheticProtection({scope:body.scope})};
   if(body.operation==='worktree_create')return {status:'OK',workspace:{base_commit:'b'.repeat(40),initial_status:'',disk_bytes:1}};
   if(body.operation==='worktree_command')return {status:'OK',result:{ok:true,executionState:'COMPLETED',output_digest:'c'.repeat(64),output_bytes:1,output:'synthetic',code:'OK',elapsed_ms:1}};
   return {status:'OK',gpu:{phase:'OFFLINE'}};
  }});
  const ctx={isAuthorizedSender:true,gatewayClientScopes:['operator.admin'],sessionKey:'synthetic',args:'start synthetic -- essential goal'};
  await handler(ctx);let status;
  for(let i=0;i<500;i++){status=await handler({...ctx,args:'status'});if(status.text.includes('TERMINAL'))break;await new Promise(r=>setTimeout(r,10));}
  assert.ok(status.text.includes('TERMINAL'),status.text);
  const id=readdirSync(settings.work_mode.ledger_root)[0],rows=checkLedger(join(settings.work_mode.ledger_root,id,'events.jsonl'));
  return {status,rows,captures:h.captures,requests:h.bodies.map(body=>body.packet.request.request),attempts:h.attempts,endpointDispatches:h.endpointDispatches};
 }finally{await handler?.close();h.close();}
}
