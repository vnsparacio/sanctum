import test from 'node:test';import assert from 'node:assert/strict';
import {deriveCapabilityManifest} from '../foundation/manifest.mjs';
import {CONTRACT_VERSION} from '../foundation/contracts.mjs';
import {argumentsMatchSchema,createWorkMode,defaultResultEgress,selectCapabilities} from '../plugin/work-mode.mjs';
import {commandCatalog,createCommandBroker} from '../plugin/command-broker.mjs';
import {normalizeWorkspacePacket,workCapabilityErrorCode} from '../plugin/work-command.mjs';
import {createPrivateLeadReasoner} from '../plugin/private-lead.mjs';

const schema={name:'calc',description:'Evaluate an exact arithmetic expression.',parameters:{type:'object',properties:{expression:{type:'string'}},required:['expression'],additionalProperties:false}};
const personal={name:'gmail_search',description:'Search Gmail metadata.',parameters:{type:'object',properties:{query:{type:'string'}},required:['query'],additionalProperties:false}};
const manifest=deriveCapabilityManifest({schemas:[schema,personal],declaredTools:['calc','gmail_search'],registeredTools:['calc','gmail_search'],adaptedTools:[],runtimeConfig:{tools:{alsoAllow:['calc','gmail_search']}}});
const proposal=(name,args={},revision=0)=>({kind:'TOOL_PROPOSAL',proposal:{schema:CONTRACT_VERSION,proposalId:'proposal'+revision,requestId:'r'.repeat(32),revision,reasoner:'PRIVATE_LEAD',capability:name,capabilityDigest:manifest.byName[name].digest,arguments:args}});
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
test('schema drift, repeated invalid proposal, approval and completion uncertainty stop deterministically',async()=>{
 const invalid={kind:'TOOL_PROPOSAL',proposal:{...proposal('calc',{expression:'x'}).proposal,capabilityDigest:'0'.repeat(64)}};
 assert.equal((await run({rows:[invalid,invalid]})).status,'SAFETY_POLICY_BLOCK');
 const wrongBinding={kind:'TOOL_PROPOSAL',proposal:{...proposal('calc',{expression:'1'}).proposal,requestId:'wrong'}};
 assert.equal((await run({rows:[wrongBinding,proposal('calc',{expression:'1'},1),final]})).status,'COMPLETE');
 const laterWrong={kind:'TOOL_PROPOSAL',proposal:{...proposal('calc',{expression:'1'},2).proposal,requestId:'wrong'}};
 assert.equal((await run({rows:[wrongBinding,proposal('calc',{expression:'1'},1),laterWrong,proposal('calc',{expression:'1'},3),final],maxIterations:8})).status,'COMPLETE');
 assert.equal((await run({rows:[wrongBinding,wrongBinding]})).reason,'REPEATED_INVALID_PROPOSAL');
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
 const row={kind:'TOOL_PROPOSAL',proposal:{schema:CONTRACT_VERSION,proposalId:'test1',requestId:'r'.repeat(32),revision:0,reasoner:'PRIVATE_LEAD',capability:tool.name,capabilityDigest:tools.byName[tool.name].digest,arguments:{task_id:'a'.repeat(32),operation:'test'}}};let reviews=0,evaluations=0;
 const authorize=(p,s,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:p.capability,proposalDigest:'a'.repeat(64),scope,effect:s.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false});
 const egress=({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']});
 const result=await createWorkMode({reasoner:reasoner([row]),manifest:tools,invoke:async()=>({ok:true,code:'OK',executionState:'COMPLETED',verifier:'VERIFIED'}),authorize,egress,evaluate:async()=>{evaluations++;return {passed:true,diffDigest:'d'.repeat(64),diffStable:true,checks:[{operation:'test',ok:true,code:'OK',outputDigest:'e'.repeat(64),elapsedMs:3}]};},reviewer:async({state})=>{reviews++;assert.equal(state.tests.checks[0].operation,'test');assert.equal(state.tests.diffStable,true);return {verdict:'ACCEPT'};}}).run({task:'fix',scope:'a'.repeat(32),requestId:'r'.repeat(32),capabilities:[tool.name]});
 assert.equal(result.status,'COMPLETE');assert.equal(result.metrics.modelCalls,1);assert.equal(evaluations,1);assert.equal(reviews,1);
});
test('a successful patch makes a host test the only permitted next action',async()=>{
 const patchTool={name:'worktree_patch',description:'Patch.',parameters:{type:'object',properties:{task_id:{type:'string'},patch:{type:'string'}},required:['task_id','patch'],additionalProperties:false}};
 const testTool={name:'worktree_command',description:'Test.',parameters:{type:'object',properties:{task_id:{type:'string'},operation:{type:'string',enum:['test']}},required:['task_id','operation'],additionalProperties:false}};
 const tools=deriveCapabilityManifest({schemas:[patchTool,testTool],declaredTools:[patchTool.name,testTool.name],registeredTools:[patchTool.name,testTool.name],adaptedTools:[],runtimeConfig:{tools:{alsoAllow:[patchTool.name,testTool.name]}}});
 const row=(tool,args,revision)=>({kind:'TOOL_PROPOSAL',proposal:{schema:CONTRACT_VERSION,proposalId:'p'+revision,requestId:'r'.repeat(32),revision,reasoner:'PRIVATE_LEAD',capability:tool.name,capabilityDigest:tools.byName[tool.name].digest,arguments:args}});
 const taskId='a'.repeat(32),calls=[];const authorize=(p,s,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:p.capability,proposalDigest:'a'.repeat(64),scope,effect:s.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false});
 const egress=({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']});
 const result=await createWorkMode({reasoner:reasoner([row(patchTool,{task_id:taskId,patch:'first'},0),row(patchTool,{task_id:taskId,patch:'second'},1),row(testTool,{task_id:taskId,operation:'test'},2)]),manifest:tools,invoke:async({proposal})=>{calls.push(proposal.arguments);return {ok:true,executionState:'COMPLETED',verifier:'VERIFIED'};},authorize,egress,evaluate:async()=>({passed:true}),reviewer:null}).run({task:'fix',scope:taskId,requestId:'r'.repeat(32),capabilities:[patchTool.name,testTool.name],maxIterations:4});
 assert.equal(result.status,'COMPLETE');assert.deepEqual(calls.map(x=>x.operation??x.patch),['first','test']);assert.ok(result.state.observations.some(x=>x.code==='TEST_REQUIRED_AFTER_PATCH'));
});
test('binding repair identifies the exact host field without relaxing the second-invalid stop',async()=>{
 const badRequest={kind:'TOOL_PROPOSAL',proposal:{...proposal('calc',{expression:'1'}).proposal,requestId:'wrong'}};
 const badRevision={kind:'TOOL_PROPOSAL',proposal:{...proposal('calc',{expression:'1'},1).proposal,revision:9}};
 const fixed=proposal('calc',{expression:'1'},1);
 const repaired=await run({rows:[badRequest,fixed,final]});assert.equal(repaired.status,'COMPLETE');assert.equal(repaired.state.observations[0].code,'REQUEST_ID_MISMATCH');assert.equal(repaired.state.observations[0].expected.revision,1);
 const stopped=await run({rows:[badRequest,badRevision]});assert.equal(stopped.status,'SAFETY_POLICY_BLOCK');assert.equal(stopped.reason,'REPEATED_INVALID_PROPOSAL');
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
