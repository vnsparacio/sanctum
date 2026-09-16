import test from 'node:test';import assert from 'node:assert/strict';
import {deriveCapabilityManifest} from '../foundation/manifest.mjs';
import {CONTRACT_VERSION,validateToolProposal} from '../foundation/contracts.mjs';
import {bindWorkIntent,validateWorkIntent,workIntentRequest,workIntentSchema} from '../foundation/work-intent.mjs';
import {incompatibleVllmPattern,projectVllmGenerationSchema,validateVllmGenerationSchema} from '../foundation/vllm-structured-output.mjs';
import {argumentsMatchSchema,createWorkMode,defaultResultEgress,selectCapabilities} from '../plugin/work-mode.mjs';
import {commandCatalog,createCommandBroker} from '../plugin/command-broker.mjs';
import {normalizeWorkspacePacket,workCapabilityErrorCode} from '../plugin/work-command.mjs';
import {createPrivateLeadReasoner} from '../plugin/private-lead.mjs';
import {workModeTools} from '../plugin/workspace-tools.mjs';
import {preflightCurrentWorkIntentSchemas} from '../preflight-work-intent.mjs';

const schema={name:'calc',description:'Evaluate an exact arithmetic expression.',parameters:{type:'object',properties:{expression:{type:'string'}},required:['expression'],additionalProperties:false}};
const personal={name:'gmail_search',description:'Search Gmail metadata.',parameters:{type:'object',properties:{query:{type:'string'}},required:['query'],additionalProperties:false}};
const manifest=deriveCapabilityManifest({schemas:[schema,personal],declaredTools:['calc','gmail_search'],registeredTools:['calc','gmail_search'],adaptedTools:[],runtimeConfig:{tools:{alsoAllow:['calc','gmail_search']}}});
const proposal=(name,args={})=>({kind:'TOOL_PROPOSAL',capability:name,arguments:args});
const final={kind:'FINAL',text:'done'};
const reasoner=rows=>({async invoke(){const value=rows.shift();if(value instanceof Error)throw value;return value;}});
const run=({rows,invoke=async()=>({ok:true,data:{value:4},verifier:'VERIFIED'}),egress=defaultResultEgress,reviewer=null,authorize,evaluate=async()=>({passed:true,tests:1}),maxIterations=8,task='synthetic task'}={})=>createWorkMode({reasoner:reasoner(rows),manifest,invoke,egress,reviewer,authorize,evaluate}).run({task,scope:'a'.repeat(32),requestId:'r'.repeat(32),maxIterations});

test('Work Mode runs one proposal at a time and requires independently allowed result egress',async()=>{
 const calls=[];const result=await run({rows:[proposal('calc',{expression:'2+2'}),final],invoke:async x=>{calls.push(x);return {ok:true,data:{value:4},verifier:'VERIFIED'};}});
 assert.equal(result.status,'COMPLETE');assert.equal(calls.length,1);assert.equal(result.state.observations[0].capability,'calc');
});
test('personal result egress is withheld and the model cannot receive it',async()=>{
 const result=await run({rows:[proposal('gmail_search',{query:'synthetic'}),final],invoke:async()=>({ok:true,data:{messages:[]}})});
 assert.equal(result.status,'COMPLETE');assert.equal(result.state.observations[0].kind,'RESULT_WITHHELD');
});
test('semantic schema, repeated invalid proposal, approval and completion uncertainty stop deterministically',async()=>{
 const invalid={kind:'TOOL_PROPOSAL',capability:'calc',arguments:{expression:'x',authority:'ALLOW'}};
 assert.equal((await run({rows:[invalid,invalid]})).status,'SAFETY_POLICY_BLOCK');
 const forbidden={kind:'TOOL_PROPOSAL',capability:'calc',arguments:{expression:'1'},requestId:'wrong'};
 assert.equal((await run({rows:[forbidden,proposal('calc',{expression:'1'}),final]})).status,'COMPLETE');
 assert.equal((await run({rows:[forbidden,forbidden]})).reason,'REPEATED_INVALID_PROPOSAL');
 assert.equal((await run({rows:[proposal('gmail_search',{query:'x'})],authorize:(p,s,scope,now)=>({schema:CONTRACT_VERSION,outcome:'ASK',capability:p.capability,proposalDigest:'a'.repeat(64),scope,effect:'READ',source:'NATIVE_APPROVAL',reasonCodes:['EXACT_OWNER_APPROVAL_REQUIRED'],expires:now+60,oneUse:true})})).status,'NEEDS_APPROVAL');
 assert.equal((await run({rows:[proposal('calc',{expression:'1'}),final],egress:()=>defaultResultEgress({claim:{dataClasses:['RESTRICTED']},spec:{policy:{remoteResultEligible:false}}}),invoke:async()=>({ok:false,error:{code:'FAILED'},executionState:'COMPLETION_UNKNOWN'})})).status,'BLOCKED');
});
test('one separate reviewer can require revision or reject before completion',async()=>{
 let reviews=0;const revise=await run({rows:[final,final],reviewer:async()=>{reviews++;return {verdict:'REVISE'};}});assert.equal(revise.status,'COMPLETE');assert.equal(reviews,1);
 const rejected=await run({rows:[final],reviewer:async()=>({verdict:'REJECT'})});assert.equal(rejected.status,'BLOCKED');
});
test('a model-requested passing test triggers host evaluation and one reviewer without more model edits',async()=>{
 const tool={name:'worktree_command',description:'Run a host test.',parameters:{type:'object',properties:{task_id:{type:'string'},operation:{type:'string',enum:['test']}},required:['task_id','operation'],additionalProperties:false}};
 const tools=deriveCapabilityManifest({schemas:[tool],declaredTools:[tool.name],registeredTools:[tool.name],adaptedTools:[],runtimeConfig:{tools:{alsoAllow:[tool.name]}}});
 const row={kind:'TOOL_PROPOSAL',capability:tool.name,arguments:{operation:'test'}};let reviews=0,evaluations=0;
 const authorize=(p,s,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:p.capability,proposalDigest:'a'.repeat(64),scope,effect:s.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false});
 const egress=({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']});
 const result=await createWorkMode({reasoner:reasoner([row]),manifest:tools,invoke:async()=>({ok:true,code:'OK',executionState:'COMPLETED',verifier:'VERIFIED'}),authorize,egress,evaluate:async()=>{evaluations++;return {passed:true,diffDigest:'d'.repeat(64),diffStable:true,checks:[{operation:'test',ok:true,code:'OK',outputDigest:'e'.repeat(64),elapsedMs:3}]};},reviewer:async({state})=>{reviews++;assert.equal(state.tests.checks[0].operation,'test');assert.equal(state.tests.diffStable,true);return {verdict:'ACCEPT'};}}).run({task:'fix',scope:'a'.repeat(32),requestId:'r'.repeat(32),capabilities:[tool.name]});
 assert.equal(result.status,'COMPLETE');assert.equal(result.metrics.modelCalls,1);assert.equal(evaluations,1);assert.equal(reviews,1);
});
test('a successful patch makes a host test the only permitted next action',async()=>{
 const patchTool={name:'worktree_patch',description:'Patch.',parameters:{type:'object',properties:{task_id:{type:'string'},patch:{type:'string'}},required:['task_id','patch'],additionalProperties:false}};
 const testTool={name:'worktree_command',description:'Test.',parameters:{type:'object',properties:{task_id:{type:'string'},operation:{type:'string',enum:['test']}},required:['task_id','operation'],additionalProperties:false}};
 const tools=deriveCapabilityManifest({schemas:[patchTool,testTool],declaredTools:[patchTool.name,testTool.name],registeredTools:[patchTool.name,testTool.name],adaptedTools:[],runtimeConfig:{tools:{alsoAllow:[patchTool.name,testTool.name]}}});
 const row=(tool,args)=>({kind:'TOOL_PROPOSAL',capability:tool.name,arguments:args});
 const taskId='a'.repeat(32),calls=[];const authorize=(p,s,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:p.capability,proposalDigest:'a'.repeat(64),scope,effect:s.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false});
 const egress=({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']});
 const result=await createWorkMode({reasoner:reasoner([row(patchTool,{patch:'first'}),row(patchTool,{patch:'second'}),row(testTool,{operation:'test'})]),manifest:tools,invoke:async({proposal})=>{calls.push(proposal.arguments);return {ok:true,executionState:'COMPLETED',verifier:'VERIFIED'};},authorize,egress,evaluate:async()=>({passed:true}),reviewer:null}).run({task:'fix',scope:taskId,requestId:'r'.repeat(32),capabilities:[patchTool.name,testTool.name],maxIterations:4});
 assert.equal(result.status,'COMPLETE');assert.deepEqual(calls.map(x=>x.operation??x.patch),['first','test']);assert.ok(result.state.observations.some(x=>x.code==='CAPABILITY_NOT_VISIBLE'));
});
test('host bindings are derived once and forbidden injection consumes the correction turn',async()=>{
 const badRequest={kind:'TOOL_PROPOSAL',capability:'calc',arguments:{expression:'1'},revision:9};
 const fixed=proposal('calc',{expression:'1'});
 const repaired=await run({rows:[badRequest,fixed,final]});assert.equal(repaired.status,'COMPLETE');assert.equal(repaired.state.observations[0].code,'FORBIDDEN_HOST_FIELD');assert.equal(repaired.state.correction,undefined);
 const stopped=await run({rows:[badRequest,badRequest]});assert.equal(stopped.status,'SAFETY_POLICY_BLOCK');assert.equal(stopped.reason,'REPEATED_INVALID_PROPOSAL');
});
test('malformed reasoner results consume the one schema-correction turn instead of claiming runtime loss',async()=>{
 const corrected=await run({rows:[Error('reasoner_result_shape'),proposal('calc',{expression:'1'},1),final]});assert.equal(corrected.status,'COMPLETE');assert.equal(corrected.state.observations[0].code,'REASONER_RESULT_SCHEMA');assert.equal(corrected.metrics.modelCalls,3);
 const stopped=await run({rows:[Error('reasoner_result_shape'),Error('reasoner_result_shape')]});assert.equal(stopped.status,'SAFETY_POLICY_BLOCK');assert.equal(stopped.reason,'REPEATED_INVALID_PROPOSAL');assert.equal(stopped.metrics.modelCalls,2);
 const unavailable=await run({rows:[Error('transport')]});assert.equal(unavailable.status,'ENVIRONMENT_FAILURE');assert.equal(unavailable.reason,'PRIVATE_LEAD_UNAVAILABLE');
});
test('PRIVATE_LEAD adapter preserves the worker schema-failure classification',async()=>{
 const profile={status:'accepted-characterized',logical_profile:'PRIVATE_LEAD',prompt:{system:'synthetic'}};
 const request={schema:CONTRACT_VERSION,requestId:'r'.repeat(32),scope:'a'.repeat(32),revision:0,messages:[{role:'user',content:'synthetic'}],manifestDigest:'b'.repeat(64),state:{phase:'PLAN'}};
 const adapter=createPrivateLeadReasoner({profile,body:()=>({}),execute:async()=>({status:'UNAVAILABLE',reason:'private_lead_result_schema'})});
 await assert.rejects(adapter.invoke(request,new AbortController().signal),/reasoner_result_shape/);
});
test('surface is host-selected and never includes unavailable capabilities',()=>{assert.deepEqual(selectCapabilities(manifest,{names:['calc','unknown'],limit:4}).map(x=>x.name),['calc']);assert.equal(selectCapabilities(manifest,{limit:1}).length,1);});
test('Work Mode reveals only enumerated workspace repair codes',()=>{assert.equal(workCapabilityErrorCode('workspace_patch_shape'),'WORKSPACE_PATCH_SHAPE');assert.equal(workCapabilityErrorCode('arbitrary backend text'),'WORK_CAPABILITY_FAILED');});
test('Work Mode fills owner-controlled defaults before signing workspace packets',()=>{
 assert.deepEqual(normalizeWorkspacePacket('worktree_list',{task_id:'a'.repeat(32)}),{task_id:'a'.repeat(32),path:'',max_entries:100});
 assert.deepEqual(normalizeWorkspacePacket('worktree_read',{task_id:'a'.repeat(32),path:'index.js'}),{task_id:'a'.repeat(32),path:'index.js',max_chars:12000});
});
test('command broker has no shell, no network path, and refuses unknown operations',async()=>{
 assert.ok(commandCatalog.includes('status'));const broker=createCommandBroker({invoke:async()=>{throw Error('must not run')},taskId:'a'.repeat(32),profile:'test'});assert.equal((await broker.execute({workspace:'a'.repeat(32),operation:'arbitrary shell'})).code,'WORKSPACE_CONTAINMENT');assert.equal((await broker.execute({workspace:'a'.repeat(32),operation:'status',allowNetwork:true})).code,'WORKSPACE_CONTAINMENT');
});
test('argument schemas and task-state limits are enforced before authority',async()=>{
 assert.equal(argumentsMatchSchema({expression:'1+1'},schema.parameters),true);assert.equal(argumentsMatchSchema({expression:1},schema.parameters),false);assert.equal(argumentsMatchSchema({expression:'1',authority:'ALLOW'},schema.parameters),false);
 const invalid=proposal('calc',{expression:1});assert.equal((await run({rows:[invalid,invalid]})).status,'SAFETY_POLICY_BLOCK');
 assert.equal((await run({rows:[final],task:'x'.repeat(4001)})).status,'ENVIRONMENT_FAILURE');
 assert.equal((await run({rows:[final],evaluate:async()=>({passed:false})})).status,'BLOCKED');
 assert.equal((await createWorkMode({reasoner:reasoner([final]),manifest,invoke:async()=>({ok:true}),egress:defaultResultEgress,evaluate:async()=>({passed:true})}).run({task:'x',scope:'a'.repeat(32),requestId:'r'.repeat(32),maxIterations:1.5})).status,'ENVIRONMENT_FAILURE');
 assert.equal((await run({rows:[final],maxIterations:16})).status,'COMPLETE');
 assert.equal((await run({rows:[final],maxIterations:17})).status,'ENVIRONMENT_FAILURE');
});
test('semantic schema excludes host fields and translates only captured bindings',()=>{
 const work={name:'worktree_read',description:'Read.',parameters:{type:'object',properties:{task_id:{type:'string',pattern:'^[a-f0-9]{32}$'},path:{type:'string',minLength:1,maxLength:512},max_chars:{type:'integer',minimum:1,maximum:24000}},required:['task_id','path'],additionalProperties:false}};
 const m=deriveCapabilityManifest({schemas:[work],registeredTools:[work.name],adaptedTools:[],runtimeConfig:{tools:{alsoAllow:[work.name]}}}),spec=m.byName[work.name];
 const intent=workIntentRequest([spec]);assert.equal(intent.version,'sanctum-work-intent/v1');assert.equal(intent.schema.oneOf[0].properties.arguments.properties.task_id,undefined);
 assert.equal(validateWorkIntent({kind:'TOOL_PROPOSAL',capability:work.name,arguments:{path:'index.js'}},{specs:[spec]}).ok,true);
 assert.equal(validateWorkIntent({kind:'TOOL_PROPOSAL',capability:work.name,arguments:{path:null}},{specs:[spec]}).code,'ARGUMENT_SCHEMA');
 assert.equal(validateWorkIntent({kind:'TOOL_PROPOSAL',capability:work.name,arguments:{path:'index.js'},task_id:'x'},{specs:[spec]}).code,'FORBIDDEN_HOST_FIELD');
 assert.equal(validateWorkIntent({kind:'TOOL_PROPOSAL',capability:'hidden',arguments:{}},{specs:[spec]}).code,'CAPABILITY_NOT_VISIBLE');
 const full={schema:CONTRACT_VERSION,proposalId:'p',requestId:'r'.repeat(32),revision:0,reasoner:'PRIVATE_LEAD',capability:work.name,capabilityDigest:spec.digest,arguments:{task_id:'a'.repeat(32),path:'index.js'}};
 assert.equal(validateToolProposal(full,m,()=>true).ok,true);
});
test('pinned generation projection omits only incompatible regex while host path validation stays authoritative',()=>{
 const names=workModeTools.map(x=>x.name),m=deriveCapabilityManifest({schemas:workModeTools.map(x=>({name:x.name,description:x.description,parameters:x.parameters})),declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
 const specs=['worktree_list','worktree_read','worktree_patch','worktree_command'].map(x=>m.byName[x]);
 const authoritative=workIntentSchema(specs),pathPattern=authoritative.oneOf.find(x=>x.properties?.capability?.const==='worktree_read').properties.arguments.properties.path.pattern;
 assert.equal(pathPattern,'^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\u0000).+$');
 const first=workIntentRequest(specs),second=workIntentRequest(specs);assert.deepEqual(first,second);assert.equal(first.dialect,'vllm-0.20.1-outlines');assert.equal(validateVllmGenerationSchema(first.schema).ok,true);
 const generatedPath=first.schema.oneOf.find(x=>x.properties?.capability?.const==='worktree_read').properties.arguments.properties.path;
 assert.equal(generatedPath.pattern,undefined);assert.equal(generatedPath.minLength,1);assert.equal(generatedPath.maxLength,512);assert.equal(argumentsMatchSchema({path:'../../secret'},first.schema.oneOf.find(x=>x.properties?.capability?.const==='worktree_read').properties.arguments),true);
 for(const path of ['/absolute','../secret','a/../../secret','bad\u0000name','x'.repeat(513)])assert.equal(validateWorkIntent({kind:'TOOL_PROPOSAL',capability:'worktree_read',arguments:{path}},{specs}).ok,false,path);
 assert.equal(validateWorkIntent({kind:'TOOL_PROPOSAL',capability:'worktree_read',arguments:{path:'src/index.js'}},{specs}).ok,true);
 const generatedEscalation=first.schema.oneOf.find(x=>x.properties?.kind?.const==='ESCALATION');assert.equal(generatedEscalation.properties.reason.pattern,undefined);assert.equal(validateWorkIntent({kind:'ESCALATION',reason:'lowercase reason'},{specs}).ok,false);assert.equal(validateWorkIntent({kind:'ESCALATION',reason:'OWNER_DECISION_REQUIRED'},{specs}).ok,true);
 assert.equal(incompatibleVllmPattern(pathPattern),'REGEX_LOOKAROUND');assert.equal(incompatibleVllmPattern('^[A-Z]+$'),'REGEX_PREFIX_CONTEXT');assert.equal(validateVllmGenerationSchema({type:'string',pattern:'^(?!/)x'}).ok,false);
 const projected=projectVllmGenerationSchema(authoritative);assert.ok(projected.omitted.some(x=>x.keyword==='pattern'&&x.reason==='REGEX_LOOKAROUND'));assert.ok(projected.omitted.some(x=>x.keyword==='pattern'&&x.reason==='REGEX_PREFIX_CONTEXT'));
});
test('production preflight covers every real surface and schema identity changes with visibility',()=>{
 const result=preflightCurrentWorkIntentSchemas();assert.equal(result.ok,true);assert.deepEqual(result.schemas.all.capabilities,workModeTools.map(x=>x.name));assert.equal(result.schemas.all.branches,workModeTools.length+2);
 for(const row of Object.values(result.schemas)){assert.equal(validateVllmGenerationSchema(row.request.schema).ok,true);assert.equal(row.request.schemaDigest,row.schemaDigest);assert.ok(row.request.schema.oneOf.some(x=>x.properties?.kind?.const==='FINAL'));assert.ok(row.request.schema.oneOf.some(x=>x.properties?.kind?.const==='ESCALATION'));}
 assert.notEqual(result.schemas.ordinary.schemaDigest,result.schemas.research.schemaDigest);assert.notEqual(result.schemas.ordinary.schemaDigest,result.schemas.testOnly.schemaDigest);
 const actual=workIntentRequest(result.schemas.ordinary.capabilities.map(name=>{const names=workModeTools.map(x=>x.name);return deriveCapabilityManifest({schemas:workModeTools.map(x=>({name:x.name,description:x.description,parameters:x.parameters})),declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}}).byName[name]}));assert.deepEqual(actual,result.schemas.ordinary.request);
 assert.throws(()=>projectVllmGenerationSchema({type:'object',$ref:'#/bad'}),/structured_schema_keyword/);
});
test('semantic rejection cannot reach canonical authority or execution',async()=>{
 const names=workModeTools.map(x=>x.name),m=deriveCapabilityManifest({schemas:workModeTools.map(x=>({name:x.name,description:x.description,parameters:x.parameters})),declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
 const bad={kind:'TOOL_PROPOSAL',capability:'worktree_read',arguments:{path:'../../secret'}};let authority=0,execution=0;
 const result=await createWorkMode({reasoner:reasoner([bad,bad]),manifest:m,invoke:async()=>{execution++;return {ok:true}},authorize:()=>{authority++;return {}},egress:defaultResultEgress,evaluate:async()=>({passed:true})}).run({task:'synthetic',scope:'a'.repeat(32),requestId:'r'.repeat(32),capabilities:['worktree_read']});
 assert.equal(result.reason,'REPEATED_INVALID_PROPOSAL');assert.equal(authority,0);assert.equal(execution,0);
 const spec=m.byName.worktree_read,intent=validateWorkIntent({kind:'TOOL_PROPOSAL',capability:'worktree_read',arguments:{path:'src/index.js'}},{specs:[spec]});
 const candidate=bindWorkIntent(intent,{proposalId:'p',requestId:'r'.repeat(32),turn:0,reasoner:'PRIVATE_LEAD',scope:'a'.repeat(32),specDigests:{worktree_read:'0'.repeat(64)}});assert.equal(validateToolProposal(candidate,m,()=>true).ok,false);
});
test('structured decoding rejection is distinct and never retries or falls back',async()=>{
 const profile={status:'accepted-characterized',logical_profile:'PRIVATE_LEAD',prompt:{system:'synthetic'}};let calls=0;
 const adapter=createPrivateLeadReasoner({profile,body:()=>({}),execute:async()=>{calls++;return {status:'UNAVAILABLE',reason:'structured_decoding_http_400'};}});
 const request={schema:CONTRACT_VERSION,requestId:'r'.repeat(32),scope:'a'.repeat(32),revision:0,messages:[{role:'user',content:'synthetic'}],manifestDigest:'b'.repeat(64),state:{phase:'PLAN'}};
 await assert.rejects(adapter.invoke(request,new AbortController().signal),error=>error.message==='structured_decoding_unavailable'&&error.httpStatus===400);assert.equal(calls,1);
 const result=await createWorkMode({reasoner:adapter,manifest,invoke:async()=>{throw Error('must not execute')},egress:defaultResultEgress,evaluate:async()=>({passed:true})}).run({task:'synthetic',scope:'a'.repeat(32),requestId:'r'.repeat(32),capabilities:['calc']});
 assert.equal(result.status,'ENVIRONMENT_FAILURE');assert.equal(result.reason,'STRUCTURED_DECODING_UNAVAILABLE');assert.equal(calls,2);assert.equal(result.metrics.modelCalls,0);
});
test('a changed host workspace fingerprint rejects a delayed mutation before authority',async()=>{
 const patch={name:'worktree_patch',parameters:{type:'object',properties:{task_id:{type:'string'},patch:{type:'string'}},required:['task_id','patch'],additionalProperties:false}};
 const m=deriveCapabilityManifest({schemas:[patch],registeredTools:[patch.name],adaptedTools:[],runtimeConfig:{tools:{alsoAllow:[patch.name]}}});let n=0,authorised=0;
 const result=await createWorkMode({reasoner:reasoner([{kind:'TOOL_PROPOSAL',capability:patch.name,arguments:{patch:'x'}}]),manifest:m,workspaceState:async()=>({tree:++n}),invoke:async()=>({ok:true}),authorize:()=>{authorised++;return {};},egress:defaultResultEgress,evaluate:async()=>({passed:true})}).run({task:'x',scope:'a'.repeat(32),requestId:'r'.repeat(32),capabilities:[patch.name]});
 assert.equal(result.reason,'WORKSPACE_STATE_CHANGED');assert.equal(authorised,0);
});
test('host evaluator, reviewer, authority, result, and egress failures close deterministically',async()=>{
 assert.equal((await run({rows:[final],evaluate:async()=>{throw Error('fail');}})).reason,'EVALUATOR_UNAVAILABLE');
 assert.equal((await run({rows:[final],reviewer:async()=>{throw Error('fail');}})).reason,'REVIEWER_UNAVAILABLE');
 assert.equal((await run({rows:[proposal('calc',{expression:'1'})],authorize:()=>{throw Error('fail');}})).reason,'AUTHORITY_UNAVAILABLE');
 assert.equal((await run({rows:[proposal('calc',{expression:'1'})],invoke:async()=>({ok:true,data:()=>{}})})).reason,'RESULT_SCHEMA');
 assert.equal((await run({rows:[proposal('calc',{expression:'1'})],egress:()=>{throw Error('fail');}})).reason,'EGRESS_UNAVAILABLE');
});
test('graded fixture matrix has bounded, deterministic terminal outcomes',async()=>{
 const fixtures=['local bug','failing test','multi-file change','schema mismatch','refactor','dependency config','ambiguous debugging','approval required','malicious repository instruction','impossible unsafe task'];
 for(const fixture of fixtures){const outcome=fixture==='approval required'?'NEEDS_APPROVAL':fixture.includes('malicious')||fixture.includes('impossible')?'BLOCKED':'COMPLETE';const rows=outcome==='COMPLETE'?[proposal('calc',{expression:'1'}),final]:outcome==='NEEDS_APPROVAL'?[proposal('gmail_search',{query:'synthetic'})]:[{kind:'ESCALATION',reason:'SAFETY_POLICY_BLOCK'}];const authorize=outcome==='NEEDS_APPROVAL'?(p,s,scope,now)=>({schema:CONTRACT_VERSION,outcome:'ASK',capability:p.capability,proposalDigest:'a'.repeat(64),scope,effect:'READ',source:'NATIVE_APPROVAL',reasonCodes:['EXACT_OWNER_APPROVAL_REQUIRED'],expires:now+60,oneUse:true}):undefined;const result=await run({rows,authorize});assert.equal(result.status,outcome,fixture);}
});
test('task wall-clock budget aborts an in-flight model call',async()=>{
 const blocking={invoke(_request,signal){return new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true}));}};
 const result=await createWorkMode({reasoner:blocking,manifest,invoke:async()=>({ok:true}),egress:defaultResultEgress,evaluate:async()=>({passed:true})}).run({task:'bounded',scope:'a'.repeat(32),requestId:'r'.repeat(32),maxTaskSeconds:1});
 assert.equal(result.status,'BUDGET_EXHAUSTED');assert.equal(result.reason,'TASK_TIME_BUDGET');
});
