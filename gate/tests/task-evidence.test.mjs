import test from 'node:test';
import assert from 'node:assert/strict';
import {deriveCapabilityManifest} from '../foundation/manifest.mjs';
import {CONTRACT_VERSION,digest} from '../foundation/contracts.mjs';
import {createWorkMode,MUTABLE_WORKTREE_COMPLETION_POLICY,WORKSPACE_EVIDENCE_VERSION} from '../plugin/work-mode.mjs';
import {workModeTools} from '../plugin/workspace-tools.mjs';
import {sanitizeProtectedEvidence} from '../plugin/work-ledger.mjs';
const scope='a'.repeat(32),requestId='r'.repeat(32),sha=x=>x.repeat(64);
const names=workModeTools.map(x=>x.name);
const manifest=deriveCapabilityManifest({schemas:workModeTools,declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
const original=()=>({schema:'sanctum-task-evidence/v1',taskId:scope,integrity:'PASS',snapshotDigest:sha('b'),contractDigest:sha('c'),candidateDigest:sha('d'),acceptanceRequired:true});
const facts=()=>({integrity:'PASS',snapshotDigest:sha('b'),candidateDigest:sha('d'),originalExecuted:true,originalPassed:true,candidateExecuted:true,candidatePassed:true,acceptanceRequired:true});
const final={kind:'FINAL',text:'done'},passingTest={kind:'TOOL_PROPOSAL',capability:'worktree_command',arguments:{operation:'test'}};
async function run({rows=[final],verify=async()=>original(),evaluate=async()=>({passed:true,protectedEvidence:facts()}),reviewer=null,invoke=async()=>({ok:true,executionState:'COMPLETED'}),onEvent=()=>{}}={}){
 return createWorkMode({reasoner:{invoke:async()=>rows.shift()},manifest,completionPolicy:MUTABLE_WORKTREE_COMPLETION_POLICY,
  workspaceState:async({scope,workspace,turn})=>({schema:WORKSPACE_EVIDENCE_VERSION,scope,workspace,turn,diff:{ok:true,executionState:'COMPLETED',digest:sha('e'),bytes:1},status:{ok:true,executionState:'COMPLETED',digest:sha('f'),bytes:1}}),
  verifyProtectedEvidence:verify,evaluate,reviewer,invoke,onEvent,
  authorize:(p,s,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:p.capability,proposalDigest:digest(p),scope,effect:s.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false}),
  egress:({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']})
 }).run({task:'synthetic protected task',scope,requestId,maxIterations:5,capabilities:['worktree_command']});
}
test('protected failure blocks FINAL and passing-test completion before evaluator or reviewer',async()=>{
 for(const row of [final,passingTest]){let evaluations=0,reviews=0;
  const result=await run({rows:[row],verify:async()=>({...original(),integrity:'FAIL'}),evaluate:async()=>{evaluations++;return {passed:true};},reviewer:async()=>{reviews++;return {verdict:'ACCEPT'};}});
  assert.equal(result.reason,'PROTECTED_INPUT_MODIFIED');assert.equal(result.status,'BLOCKED');assert.equal(evaluations+reviews,0);assert.equal(result.metrics.modelCalls,1);
 }
});
test('all completion paths recheck integrity after evaluator and immediately after reviewer',async()=>{
 for(const row of [final,passingTest])for(const stage of [2,3]){let calls=0,reviews=0;
  const result=await run({rows:[row],verify:async()=>({...original(),integrity:++calls===stage?'FAIL':'PASS'}),reviewer:async()=>{reviews++;return {verdict:'ACCEPT'};}});
  assert.equal(result.reason,'PROTECTED_INPUT_MODIFIED');assert.equal(reviews,stage===3?1:0);
 }
});
test('review consumed after REVISE cannot waive later integrity failure',async()=>{
 let checks=0,reviews=0;
 const result=await run({rows:[final,final],verify:async()=>({...original(),integrity:++checks===3?'FAIL':'PASS'}),reviewer:async()=>{reviews++;return {verdict:'REVISE'};}});
 assert.equal(result.reason,'PROTECTED_INPUT_MODIFIED');assert.equal(reviews,1);
});
test('evaluator exceptions cannot mask a protected mutation as a generic failure',async()=>{
 let changed=false;
 const result=await run({verify:async()=>({...original(),integrity:changed?'FAIL':'PASS'}),evaluate:async()=>{changed=true;throw Error('candidate mutation');}});
 assert.equal(result.reason,'PROTECTED_INPUT_MODIFIED');assert.equal(result.status,'BLOCKED');
});
test('missing, cross-task or stale protected facts fail closed without model correction',async()=>{
 for(const bad of [undefined,{...original(),taskId:'z'.repeat(32)},{...original(),snapshotDigest:'bad'}]){
  const result=await run({verify:async()=>bad});assert.equal(result.reason,'PROTECTED_EVIDENCE_UNAVAILABLE');assert.equal(result.metrics.modelCalls,1);
 }
 for(const key of ['candidateDigest','snapshotDigest','contractDigest']){let calls=0;
  const result=await run({verify:async()=>({...original(),...(++calls===3?{[key]:sha('f')}:{})})});assert.equal(result.reason,'PROTECTED_EVIDENCE_STALE');
 }
});
test('evaluator success cannot substitute for original execution, results or candidate tests',async()=>{
 for(const key of ['originalExecuted','originalPassed','candidateExecuted','candidatePassed']){
  let reviewed=0;const result=await run({evaluate:async()=>({passed:true,protectedEvidence:{...facts(),[key]:false}}),reviewer:async()=>{reviewed++;return {verdict:'ACCEPT'};}});
  assert.equal(result.reason,'PROTECTED_ACCEPTANCE_FAILED');assert.equal(reviewed,0);
 }
 assert.equal((await run({evaluate:async()=>({passed:true})})).reason,'PROTECTED_ACCEPTANCE_FAILED');
});
test('valid original and candidate facts allow FINAL, test completion and one review after revision',async()=>{
 for(const rows of [[final],[passingTest],[final,passingTest]]){let reviews=0;const events=[];
  const revising=rows.length===2;
  const result=await run({rows,reviewer:async()=>{reviews++;return {verdict:revising?'REVISE':'ACCEPT'};},onEvent:(kind,facts)=>events.push({kind,...facts})});
  assert.equal(result.status,'COMPLETE');assert.equal(reviews,1);assert.equal(events.filter(x=>x.stage==='BEFORE_COMPLETE').length,1);
 }
});
test('typed protected receipts expose only bounded host facts',()=>{
 const value={stage:'EVALUATION',...facts(),prompt:'private body',reason:'arbitrary text',path:'/private'};
 const clean=sanitizeProtectedEvidence(value);assert.equal(clean.prompt,undefined);assert.equal(clean.path,undefined);assert.equal(clean.reason,undefined);
 for(const invalid of [{...value,integrity:'UNKNOWN'},{...value,originalExecuted:'true'},{...value,candidateDigest:'payload'}])assert.throws(()=>sanitizeProtectedEvidence(invalid),/work_ledger_protection/);
});
