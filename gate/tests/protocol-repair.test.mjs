import {syntheticProtection} from './fixtures/task-evidence.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {deriveCapabilityManifest} from '../foundation/manifest.mjs';
import {workModeTools} from '../plugin/workspace-tools.mjs';
import {createWorkMode,MUTABLE_WORKTREE_COMPLETION_POLICY,WORKSPACE_EVIDENCE_VERSION} from '../plugin/work-mode.mjs';
import {createPrivateLeadReasoner} from '../plugin/private-lead.mjs';
import {preflightCurrentWorkIntentSchemas} from '../preflight-work-intent.mjs';
import {CONTRACT_VERSION,digest} from '../foundation/contracts.mjs';
import {validateReasonerResult,validateToolProposal} from '../foundation/contracts.mjs';
import {bindWorkIntent,validateWorkIntent} from '../foundation/work-intent.mjs';
import {decisionSurface} from '../foundation/decision-surface.mjs';
import {schemaDiagnostic,sanitizeProtocolDiagnostic} from '../foundation/protocol-diagnostics.mjs';
import {argumentsMatchSchema} from '../plugin/work-mode.mjs';
import {createWorkLedger} from '../plugin/work-ledger.mjs';
import {mkdtempSync,readFileSync,rmSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import Ajv from 'ajv';
import {fileURLToPath} from 'node:url';
import {runProtocolMicroprobes} from '../protocol-microprobe.mjs';
import {createExecutor} from '../plugin/core.mjs';
const names=workModeTools.map(x=>x.name);
const manifest=deriveCapabilityManifest({schemas:workModeTools.map(x=>({name:x.name,description:x.description,parameters:x.parameters})),declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
const evidence=async({scope,workspace,turn})=>({schema:WORKSPACE_EVIDENCE_VERSION,scope,workspace,turn,diff:{ok:true,executionState:'COMPLETED',bytes:0,digest:'a'.repeat(64)},status:{ok:true,executionState:'COMPLETED',bytes:0,digest:'b'.repeat(64)}});
const config={verifyProtectedEvidence:syntheticProtection,manifest,completionPolicy:MUTABLE_WORKTREE_COMPLETION_POLICY,workspaceState:evidence,invoke:async()=>({ok:true}),egress:()=>({}),evaluate:async()=>({passed:false})};
test('preflight schema is the exact runtime schema, including branch order',async()=>{
 for(const [surface,capabilities] of [['ordinaryIneligible',names.filter(x=>x!=='source_first_research')],['researchIneligible',names.filter(x=>x!=='worktree_patch')]]){
  let captured;
  await createWorkMode({...config,reasoner:{async invoke(request){captured=request;return {kind:'ESCALATION',reason:'SYNTHETIC'};}}}).run({task:'synthetic',scope:'s',capabilities});
  assert.deepEqual(captured.state.workIntent,preflightCurrentWorkIntentSchemas().schemas[surface].request);
 }
});
test('first generic validator exposes structural failure without content',async()=>{
 const secret='synthetic private value';
 const adapter=createPrivateLeadReasoner({execute:async()=>({status:'OK',result:{kind:'ESCALATION',reason:secret}}),profile:{status:'accepted-characterized',logical_profile:'PRIVATE_LEAD',prompt:{system:'synthetic'}},body:()=>({})});
 const request={schema:CONTRACT_VERSION,requestId:'r',scope:'s',revision:0,messages:[{role:'user',content:'synthetic'}],manifestDigest:'a'.repeat(64),state:{}};
 await assert.rejects(adapter.invoke(request),error=>{assert.equal(error.diagnostic?.stage,'GENERIC_RESULT');assert.equal(error.diagnostic?.field,'reason');assert.equal(error.diagnostic?.keyword,'pattern');assert.ok(!JSON.stringify(error.diagnostic).includes(secret));return true;});
});
test('oversized accumulated context stops before sending an omitted goal',async()=>{
 let calls=0;
 const result=await createWorkMode({...config,invoke:async()=>({ok:true,data:{text:'x'.repeat(10800)},executionState:'COMPLETED',verifier:'VERIFIED'}),egress:({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']}),authorize:(p,s,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:p.capability,proposalDigest:digest(p),scope,effect:s.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false}),reasoner:{async invoke(request){calls++;assert.equal(JSON.parse(request.messages[1].content).task,'essential goal');return {kind:'TOOL_PROPOSAL',capability:'worktree_read',arguments:{path:'index.js'}};}}}).run({task:'essential goal',scope:'a'.repeat(32),capabilities:['worktree_read']});
 assert.equal(result.reason,'MODEL_CONTEXT_LIMIT');assert.equal(calls,6);
});

const positives=[{kind:'ESCALATION',reason:'BOUNDED_INABILITY'},{kind:'FINAL',text:'synthetic'},...Object.entries({worktree_list:{},worktree_read:{path:'index.js'},worktree_edit:{path:'index.js',old_text:'old',new_text:'--- a/index.js\n+++ b/index.js\n@@ -1 +1 @@\n-old\n+new\n'},worktree_patch:{patch:'--- a/index.js\n+++ b/index.js\n@@ -1 +1 @@\n-old\n+new\n'},worktree_command:{operation:'test'},source_first_research:{source_need:'WEB_REQUIRED'}}).map(([capability,args])=>({kind:'TOOL_PROPOSAL',capability,arguments:args}))];
test('every semantic branch survives the adapter and canonical binding',async()=>{
 const built=decisionSurface({manifest,names,limit:6,terminalKinds:['FINAL','ESCALATION']});
 for(const value of positives){
  const adapter=createPrivateLeadReasoner({execute:async()=>({status:'OK',result:value}),profile:{status:'accepted-characterized',logical_profile:'PRIVATE_LEAD',prompt:{system:'synthetic'}},body:()=>({})});
  const request={schema:CONTRACT_VERSION,requestId:'r',scope:'a'.repeat(32),revision:0,messages:[{role:'user',content:'synthetic'}],manifestDigest:manifest.digest,state:{workIntent:built.request}};
  const result=await adapter.invoke(request);assert.deepEqual(result,value);
  const checked=validateWorkIntent(result,{specs:built.specs,terminalKinds:built.terminalKinds});assert.equal(checked.ok,true);
  if(value.kind==='TOOL_PROPOSAL'){
   const bound=bindWorkIntent(checked,{scope:request.scope,proposalId:'p',requestId:'r',reasoner:'PRIVATE_LEAD',turn:0,specDigests:Object.fromEntries(built.specs.map(x=>[x.name,x.digest]))});
   assert.equal(validateToolProposal(bound,manifest,args=>argumentsMatchSchema(args,manifest.byName[value.capability].arguments)).ok,true);
  }
 }
});
test('terminal differential matrix documents projection, NUL and Unicode length gaps',()=>{
 const built=decisionSurface({manifest,names,terminalKinds:['FINAL','ESCALATION']}),ajv=new Ajv({strict:false});
 const generation=ajv.compile(built.request.schema),semantic=ajv.compile(built.authoritativeSchema);
 const cases=[
  [{kind:'ESCALATION',reason:'A'},[true,true,true,true]],
  [{kind:'ESCALATION',reason:'A'.repeat(80)},[true,true,true,true]],
  ...['','a',' A','A ','A'.repeat(81),'雪','A\0'].map(reason=>[{kind:'ESCALATION',reason},[true,false,false,false]]),
  [{kind:'ESCALATION',reason:'A\n'},[true,false,false,false]],
  ...[{}, {reason:null},{reason:1},{reason:[]},{reason:{}}].map(extra=>[{kind:'ESCALATION',...extra},[false,false,false,false]]),
  [{kind:'ESCALATION',reason:'A',secret:'synthetic'},[false,false,false,false]],
  [{kind:'FINAL',text:''},[true,false,false,false]],
  [{kind:'FINAL',text:'a'.repeat(32768)},[true,true,true,true]],
  [{kind:'FINAL',text:'a'.repeat(32769)},[true,false,false,false]],
  [{kind:'FINAL',text:'\0'},[true,true,false,true]],
  [{kind:'FINAL',text:'😀'.repeat(20000)},[true,true,false,false]],
 ];
 for(const [value,expected] of cases)assert.deepEqual([generation(value),semantic(value),validateReasonerResult(value,{supportsWorkIntents:true}).ok,validateWorkIntent(value,{specs:built.specs,terminalKinds:built.terminalKinds}).ok],expected);
});
test('all corresponding surfaces and argument constraints share exact identities',()=>{
 for(const [label,row] of Object.entries(preflightCurrentWorkIntentSchemas().schemas)){
  const built=decisionSurface({manifest,names:row.capabilities,limit:row.capabilities.length,testOnly:label==='testOnlyIneligible',reviewer:label==='reviewer',terminalKinds:label==='reviewer'?['FINAL']:label.endsWith('Ineligible')?['ESCALATION']:['FINAL','ESCALATION']});
  assert.deepEqual(built.request,row.request);assert.deepEqual(built.capabilities,row.capabilities);
  const validator=new Ajv({strict:false}).compile(built.request.schema);
  for(const value of positives.filter(x=>x.kind==='TOOL_PROPOSAL'?built.capabilities.includes(x.capability):built.terminalKinds.includes(x.kind)))assert.equal(validator(value),true,label);
 }
 const built=decisionSurface({manifest,names:['worktree_command'],testOnly:true,terminalKinds:['ESCALATION']});
 assert.equal(validateWorkIntent({kind:'TOOL_PROPOSAL',capability:'worktree_command',arguments:{operation:'build'}},{specs:built.specs,testOnly:true,terminalKinds:built.terminalKinds}).ok,false);
});
test('structural diagnostics name the actual predicate and never disclose unknown keys or values',()=>{
 const built=decisionSurface({manifest,names,limit:6,terminalKinds:['ESCALATION']});
 for(const [args,keyword,field] of [[{},'required','path'],[{path:''},'minLength','path'],[{path:'a'.repeat(513)},'maxLength','path'],[{path:'../synthetic'},'pattern','path'],[{path:3},'type','path'],[{path:'index.js',max_chars:0},'minimum','max_chars'],[{path:'index.js',max_chars:24001},'maximum','max_chars'],[{path:'index.js','synthetic private key':'synthetic private value'},'additionalProperties','arguments']]){
  const diagnostic=schemaDiagnostic({kind:'TOOL_PROPOSAL',capability:'worktree_read',arguments:args},built.authoritativeSchema);
  assert.equal(diagnostic.keyword,keyword);assert.equal(diagnostic.field,field);assert.ok(!JSON.stringify(diagnostic).includes('synthetic private'));
 }
 const sanitized=sanitizeProtocolDiagnostic({stage:'synthetic private stage',field:'synthetic private key',resultKind:'synthetic private enum',stringLength:1e9,unknownFieldCount:1e9,error:'synthetic private error'});
 assert.ok(!JSON.stringify(sanitized).includes('synthetic private'));assert.equal(sanitized.stringLength,65537);
});
test('worker diagnostics reach the single correction and allowlisted hash-chained ledger',async()=>{
 const root=mkdtempSync(join(tmpdir(),'sanctum-protocol-')),taskId='b'.repeat(32),requests=[];
 try{
  const ledger=createWorkLedger({root,taskId,key:Buffer.alloc(32,7),metadata:{goal:'synthetic private goal'},now:()=>1});
  const adapter=createPrivateLeadReasoner({execute:async()=>({status:'UNAVAILABLE',reason:'private_lead_result_schema',diagnostic:{stage:'JSON_PARSE',validatorVersion:'json/v1',keyword:'syntax',field:'root',error:'synthetic private error','synthetic private key':'synthetic private value'}}),profile:{status:'accepted-characterized',logical_profile:'PRIVATE_LEAD',prompt:{system:'synthetic'}},body:(_op,_tier,packet)=>{requests.push(packet.request.request);return {};}});
  const result=await createWorkMode({...config,reasoner:adapter,onEvent:(kind,value)=>ledger.event(kind,value)}).run({task:'synthetic private goal',scope:taskId,capabilities:['worktree_read']});
  assert.equal(result.reason,'REPEATED_INVALID_PROPOSAL');assert.equal(result.metrics.modelCalls,2);
  assert.equal(JSON.parse(requests[1].messages[1].content).state.correction.diagnostic.stage,'JSON_PARSE');
  const raw=readFileSync(join(root,taskId,'events.jsonl'),'utf8');assert.ok(!raw.includes('synthetic private'));
  const rows=raw.trim().split('\n').map(JSON.parse);assert.equal(rows.filter(x=>x.kind==='PROTOCOL_DIAGNOSTIC').length,2);
  let previous='0'.repeat(64);for(const row of rows){const {eventDigest,...base}=row;assert.equal(base.previousDigest,previous);assert.equal(digest(base),eventDigest);previous=eventDigest;}
 }finally{rmSync(root,{recursive:true,force:true});}
});

test('signed worker microprobes use production requests, parser, adapter and host checks',async()=>{
 const root=mkdtempSync(join(tmpdir(),'sanctum-signed-probes-')),source=fileURLToPath(new URL('../../',import.meta.url)),key=Buffer.alloc(32,7),profile=JSON.parse(readFileSync(new URL('../runtime/private-lead-interface-profile.json',import.meta.url)));
 const settings=JSON.parse(readFileSync(new URL('../SETTINGS.json',import.meta.url)));settings.state_directory=root;settings.python=join(source,'.venv/bin/python');
 writeFileSync(join(root,'settings.json'),JSON.stringify(settings),{mode:0o600});writeFileSync(join(root,'authority.key'),key,{mode:0o600});
 writeFileSync(join(root,'worker.py'),`import runpy\nrunpy.run_path(${JSON.stringify(join(source,'gate/tests/fixtures/protocol_worker.py'))},init_globals={'FIXTURE_ROOT':${JSON.stringify(root)},'SOURCE_ROOT':${JSON.stringify(source)}},run_name='__main__')\n`,{mode:0o600});
 const remote=createExecutor(root,settings,key);let nonce=0;
 const writeStream=value=>writeFileSync(join(root,'stream.txt'),[...JSON.stringify(value)].map(content=>'data: '+JSON.stringify({choices:[{index:0,delta:{content},finish_reason:null}]})+'\n\n').join('')+'data: '+JSON.stringify({choices:[{index:0,delta:{},finish_reason:'stop'}]})+'\n\ndata: [DONE]\n\n',{mode:0o600});
 const body=(_op,_tier,packet)=>({operation:'private_lead_propose',tier:'PRIVATE_LEAD',packet,state:{scope:'a'.repeat(32),high_stakes:false,privacy_floor:'PERSONAL',revision:0},scope:'a'.repeat(32),approval:'private_lead_workmode',strong:false,nonce:(++nonce).toString(16).padStart(64,'0'),expires:Date.now()/1000+60,spec_sha256:'a'.repeat(64)});
 try{
  for(const probe of ['inspection','postPatch','inability']){
   const expected=probe==='inspection'?{kind:'TOOL_PROPOSAL',capability:'worktree_read',arguments:{path:'index.js'}}:probe==='postPatch'?{kind:'TOOL_PROPOSAL',capability:'worktree_command',arguments:{operation:'test'}}:{kind:'ESCALATION',reason:'UNAVAILABLE_CAPABILITY'};
   writeStream(expected);let inferenceCalls=0,actions=0,seeded=false;const requests=[];
   const adapter=createPrivateLeadReasoner({execute:async(...args)=>{inferenceCalls++;return remote(...args);},profile,body});
   const reasoner={async invoke(request){
    if(probe==='postPatch'&&!seeded){seeded=true;return {kind:'TOOL_PROPOSAL',capability:'worktree_edit',arguments:{path:'index.js',old_text:'old',new_text:'synthetic host seed'}};}
    requests.push(request);return adapter.invoke(request);
   }};
   const work=await createWorkMode({...config,reasoner,authorize:(p,s,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:p.capability,proposalDigest:digest(p),scope,effect:s.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false}),invoke:async({proposal})=>{actions++;if(proposal.capability==='worktree_edit')return {ok:true,executionState:'COMPLETED',verifier:'VERIFIED'};assert.equal(proposal.capability,expected.capability);assert.equal(proposal.arguments.task_id,'a'.repeat(32));return {ok:true,executionState:'COMPLETED',verifier:'VERIFIED'};},egress:({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']}),evaluate:async()=>({passed:true})}).run({task:probe==='inspection'?'Read index.js to inspect its exported function.':probe==='postPatch'?'Run the required test for the host-seeded synthetic patch.':'The required external capability is unavailable; report inability.',scope:'a'.repeat(32),capabilities:['worktree_list','worktree_read','worktree_edit','worktree_patch','worktree_command'],maxModelCalls:probe==='postPatch'?2:1});
   assert.equal(inferenceCalls,1);assert.equal(requests.length,1);
   if(probe==='inability'){assert.equal(work.reason,'MODEL_ESCALATION');assert.equal(actions,0);}
   else if(probe==='postPatch'){assert.equal(actions,2);assert.equal(work.status,'COMPLETE');assert.deepEqual(requests[0].state.workIntent,preflightCurrentWorkIntentSchemas().schemas.testOnlyIneligible.request);}
   else {assert.equal(actions,1);assert.equal(work.reason,'MODEL_CALL_BUDGET');assert.deepEqual(requests[0].state.workIntent,preflightCurrentWorkIntentSchemas().schemas.ordinaryIneligible.request);}
  }
  const micro=await runProtocolMicroprobes({manifest,reasoner:createPrivateLeadReasoner({execute:remote,profile,body}),beforeProbe:id=>writeStream(id==='inspection'?{kind:'TOOL_PROPOSAL',capability:'worktree_read',arguments:{path:'index.js'}}:id==='postPatch'?{kind:'TOOL_PROPOSAL',capability:'worktree_command',arguments:{operation:'test'}}:{kind:'ESCALATION',reason:'UNAVAILABLE_CAPABILITY'})});
  assert.equal(micro.passed,true);assert.equal(micro.calls,3);assert.equal(micro.agenticTaskCompletion,false);assert.equal(micro.rows[1].hostSeededPatch,true);
  // An invalid terminal traverses the signed worker and gets one correction only.
  writeStream({kind:'ESCALATION',reason:'synthetic private reason'});let calls=0;
  const adapter=createPrivateLeadReasoner({execute:async(...args)=>{calls++;return remote(...args);},profile,body});
  const result=await createWorkMode({...config,reasoner:adapter}).run({task:'synthetic',scope:'a'.repeat(32),capabilities:['worktree_read']});
  assert.equal(calls,2);assert.equal(result.reason,'REPEATED_INVALID_PROPOSAL');assert.equal(result.state.correction.diagnostic.keyword,'pattern');
 }finally{rmSync(root,{recursive:true,force:true});}
});

test('microprobe runner stops on wrong semantic choice or repeated invalidity without sampling again',async()=>{
 for(const value of [{kind:'ESCALATION',reason:'PREMATURE'},{kind:'TOOL_PROPOSAL',capability:'worktree_list',arguments:{}},{kind:'ESCALATION',reason:'bad reason'}]){
  let calls=0;
  const report=await runProtocolMicroprobes({manifest,reasoner:{async invoke(){calls++;return value;}}});
  assert.equal(report.passed,false);assert.equal(report.rows.length,1);assert.equal(calls,value.reason==='bad reason'?2:1);
 }
});
