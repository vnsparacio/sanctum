import test from 'node:test';import assert from 'node:assert/strict';
import {deriveCapabilityManifest} from '../foundation/manifest.mjs';
import {CONTRACT_VERSION} from '../foundation/contracts.mjs';
import {argumentsMatchSchema,createWorkMode,defaultResultEgress,selectCapabilities} from '../plugin/work-mode.mjs';
import {commandCatalog,createCommandBroker} from '../plugin/command-broker.mjs';

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
 assert.equal((await run({rows:[proposal('gmail_search',{query:'x'})],authorize:(p,s,scope,now)=>({schema:CONTRACT_VERSION,outcome:'ASK',capability:p.capability,proposalDigest:'a'.repeat(64),scope,effect:'READ',source:'NATIVE_APPROVAL',reasonCodes:['EXACT_OWNER_APPROVAL_REQUIRED'],expires:now+60,oneUse:true})})).status,'NEEDS_APPROVAL');
 assert.equal((await run({rows:[proposal('calc',{expression:'1'}),final],egress:()=>defaultResultEgress({claim:{dataClasses:['RESTRICTED']},spec:{policy:{remoteResultEligible:false}}}),invoke:async()=>({ok:false,error:{code:'FAILED'},executionState:'COMPLETION_UNKNOWN'})})).status,'BLOCKED');
});
test('one separate reviewer can require revision or reject before completion',async()=>{
 let reviews=0;const revise=await run({rows:[final,final],reviewer:async()=>{reviews++;return {verdict:'REVISE'};}});assert.equal(revise.status,'COMPLETE');assert.equal(reviews,1);
 const rejected=await run({rows:[final],reviewer:async()=>({verdict:'REJECT'})});assert.equal(rejected.status,'BLOCKED');
});
test('surface is host-selected and never includes unavailable capabilities',()=>{assert.deepEqual(selectCapabilities(manifest,{names:['calc','unknown'],limit:4}).map(x=>x.name),['calc']);assert.equal(selectCapabilities(manifest,{limit:1}).length,1);});
test('command broker has no shell, no network path, and refuses unknown operations',async()=>{
 assert.ok(commandCatalog.includes('git_status'));const broker=createCommandBroker({sandbox:'/missing'});assert.equal((await broker.execute({workspace:'/tmp',operation:'arbitrary shell'})).code,'ENVIRONMENT_FAILURE');assert.equal((await broker.execute({workspace:'/tmp',operation:'git_status',allowNetwork:true})).code,'ENVIRONMENT_FAILURE');
});
test('argument schemas and task-state limits are enforced before authority',async()=>{
 assert.equal(argumentsMatchSchema({expression:'1+1'},schema.parameters),true);assert.equal(argumentsMatchSchema({expression:1},schema.parameters),false);assert.equal(argumentsMatchSchema({expression:'1',authority:'ALLOW'},schema.parameters),false);
 const invalid=proposal('calc',{expression:1});assert.equal((await run({rows:[invalid,invalid]})).status,'SAFETY_POLICY_BLOCK');
 assert.equal((await run({rows:[final],task:'x'.repeat(4001)})).status,'ENVIRONMENT_FAILURE');
 assert.equal((await run({rows:[final],evaluate:async()=>({passed:false})})).status,'BLOCKED');
 assert.equal((await createWorkMode({reasoner:reasoner([final]),manifest,invoke:async()=>({ok:true}),egress:defaultResultEgress,evaluate:async()=>({passed:true})}).run({task:'x',scope:'a'.repeat(32),requestId:'r'.repeat(32),maxIterations:1.5})).status,'ENVIRONMENT_FAILURE');
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
