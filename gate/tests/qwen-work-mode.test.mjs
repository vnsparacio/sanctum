import test from 'node:test';
import assert from 'node:assert/strict';
import {runQwenWorkMode} from '../plugin/qwen-work-mode.mjs';

const hash='a'.repeat(64);
const validRun={status:'OK',result:{schema:'sanctum-qwen-run/v1',taskId:'task',ok:true,code:'OK',containerAbsent:true,modelCalls:37,inferenceSeconds:120,estimatedCostUsd:0.4,elapsedSeconds:500,importReceipt:{paths:['index.js'],authorityResult:'ALLOW',candidateDigest:hash,patchDigest:hash}}};
const evidence={passed:true,diffDigest:hash,checks:[{operation:'test',ok:true}],protectedEvidence:{integrity:'PASS'}};
function fixture({run=validRun,checked=evidence,verdict='ACCEPT',gpu='OFFLINE',failReview=false}={}){
 const events=[],order=[];
 const task={id:'task',profile:'moodqwen',goal:'Fix MoodLog',telemetry:{qwenCostUsd:0,estimatedCostUsd:0,modelCalls:0,inferenceSeconds:0},ledger:{event:(name,value)=>events.push([name,value])}};
 const call=async(_task,operation)=>{order.push(operation);return operation==='close'?{status:'OK',gpu:{phase:gpu}}:run;};
 const evaluate=async()=>{order.push('evaluate');return checked;};
 const reviewer=async()=>{order.push('review');if(failReview)throw Error('unavailable');return {verdict,findings:[]};};
 const baseline=async()=>{order.push('baseline');return {ordinaryExecuted:true,ordinaryPassed:false,protectedExecuted:true,protectedPassed:true};};
 const options={task,profile:{engine:'qwen_code',max_cost_usd:1.5},call,baseline,evaluate,reviewer,signal:new AbortController().signal,now:()=>1000};
 return {options,events,order,task};
}

test('only an imported edit, Sanctum evaluation, independent review, and GPU cleanup complete',async()=>{
 const f=fixture();const result=await runQwenWorkMode(f.options);
 assert.equal(result.status,'COMPLETE');assert.equal(result.reason,'QWEN_ACCEPTED');
 assert.deepEqual(f.order,['baseline','worktree_qwen_run','evaluate','review','close']);
 assert.equal(result.metrics.modelCalls,37);
 assert.deepEqual(f.events.map(x=>x[0]),['QWEN_BASELINE','QWEN_RUN','QWEN_EVALUATION','QWEN_REVIEWER','QWEN_GPU_CLEANUP']);
 assert.equal(JSON.stringify(f.events).includes('Fix MoodLog'),false);
});
test('Qwen final output and import receipt cannot bypass protected evaluation',async()=>{
 const f=fixture({checked:{...evidence,protectedEvidence:{integrity:'FAIL'}}});
 const result=await runQwenWorkMode(f.options);
 assert.equal(result.status,'BLOCKED');assert.equal(result.reason,'EVALUATOR_REJECTED');
 assert.deepEqual(f.order,['baseline','worktree_qwen_run','evaluate','close']);
});
test('review rejection, reviewer failure, and uncertain GPU cleanup stop closed',async()=>{
 for(const [overrides,status,reason] of [
  [{verdict:'REVISE'},'BLOCKED','REVIEWER_REVISE'],
  [{failReview:true},'ENVIRONMENT_FAILURE','QWEN_WORKMODE_FAILURE'],
  [{gpu:'READY'},'ENVIRONMENT_FAILURE','GPU_CLEANUP_UNCERTAIN'],
 ]){
  const f=fixture(overrides);const result=await runQwenWorkMode(f.options);
  assert.equal(result.status,status);assert.equal(result.reason,reason);
  assert.equal(f.order.at(-1),'close');
 }
});
test('wrong task identity, missing authority, no edit, and budget exhaustion never evaluate',async()=>{
 for(const run of [
  {...validRun,result:{...validRun.result,taskId:'other'}},
  {...validRun,result:{...validRun.result,importReceipt:{...validRun.result.importReceipt,authorityResult:'DENY'}}},
  {...validRun,result:{...validRun.result,importReceipt:{...validRun.result.importReceipt,paths:[]}}},
  {...validRun,result:{...validRun.result,estimatedCostUsd:2}},
  {...validRun,result:{...validRun.result,ok:false,code:'qwen_model_call_limit'}},
 ]){
  const f=fixture({run});const result=await runQwenWorkMode(f.options);
  assert.notEqual(result.status,'COMPLETE');
  assert.deepEqual(f.order,['baseline','worktree_qwen_run','close']);
 }
});
test('engine and reviewer are selected by profile, not by task text',async()=>{
 const f=fixture();for(const change of [{engine:'other'},{reviewer:false},{stages:[{name:'x'}]}]){
  await assert.rejects(runQwenWorkMode({...f.options,profile:{...f.options.profile,...change}}));
 }
 assert.deepEqual(f.order,[]);
});
