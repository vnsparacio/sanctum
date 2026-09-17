import test from 'node:test';
import assert from 'node:assert/strict';
import {leadRun,reviewerRun,plan,valid,bad,tool,manifest,ordinary,scope,snapshot} from './fixtures/targeted-harness.mjs';
import {preflightCurrentWorkIntentSchemas} from '../preflight-work-intent.mjs';
import {createWorkMode,MUTABLE_WORKTREE_COMPLETION_POLICY} from '../plugin/work-mode.mjs';
import {CONTRACT_VERSION,digest} from '../foundation/contracts.mjs';
import {workIntentSchema,validateWorkIntent} from '../foundation/work-intent.mjs';

const pattern='^[A-Z][A-Z0-9_:-]{0,79}$';
const request=sent=>JSON.parse(sent.messages[1].content);
const context=sent=>{const value=request(sent).messages[1].content;assert.equal(typeof value,'object');assert.ok(value&&!Array.isArray(value));return value;};
const diagnostics=rows=>rows.filter(x=>x.kind==='PROTOCOL_DIAGNOSTIC');
function ruleCheck(value){
 const text=JSON.stringify(value);assert.ok(text.includes(pattern));
 for(const phrase of ['1–80','ASCII A–Z','0–9','underscore','colon','hyphen','spaces','line terminators','extra prose'])assert.ok(text.includes(phrase),phrase);
}

test('R1 initial and correction HTTP requests communicate the retained reason rule',async()=>{
 const run=await leadRun([plan(bad),plan(valid)]);
 assert.equal(run.result.status,'BLOCKED');assert.equal(run.result.reason,'MODEL_ESCALATION');assert.equal(run.attempts,2);assert.equal(run.effects,0);
 for(const sent of run.captures){const body=context(sent);ruleCheck(body.state.resultRequirements);assert.equal(body.task,'essential goal');assert.equal(body.capabilities.length,4);assert.ok(!JSON.stringify(body.state.resultRequirements).includes('INJECTED_PRIVATE'));}
 ruleCheck(context(run.captures[1]).state.correction.resultRequirements);
 assert.equal(run.result.state.correction,undefined);
});
test('R1 guidance matches host acceptance on all applicable runtime surfaces',async()=>{
 const schema=workIntentSchema([],{terminalKinds:['ESCALATION']});assert.equal(schema.oneOf[0].properties.reason.pattern,pattern);
 for(const [prefix,capabilities] of [['ordinary',ordinary],['research',['worktree_list','worktree_read','source_first_research','worktree_command']]])for(const bytes of [0,1]){
  const run=await leadRun([plan(valid)],{capabilities,bytes});ruleCheck(context(run.captures[0]).state.resultRequirements);
  assert.deepEqual(request(run.captures[0]).state.workIntent,preflightCurrentWorkIntentSchemas().schemas[prefix+(bytes?'Eligible':'Ineligible')].request);
 }
 const post=await leadRun([plan(tool('worktree_patch',{patch:'synthetic'})),plan(valid)]);ruleCheck(context(post.captures[1]).state.resultRequirements);assert.deepEqual(request(post.captures[1]).state.workIntent,preflightCurrentWorkIntentSchemas().schemas.testOnlyIneligible.request);
 for(const reason of ['A','A'.repeat(80),'A09_:-'])assert.equal(validateWorkIntent({kind:'ESCALATION',reason},{terminalKinds:['ESCALATION']}).ok,true);
 for(const reason of ['','a','A'.repeat(81),'A ','A\n','A\r','A\u2028','A\u2029','雪'])assert.equal(validateWorkIntent({kind:'ESCALATION',reason},{terminalKinds:['ESCALATION']}).ok,false);
});
test('R1 valid nonterminal result clears correction before a subsequent independent correction',async()=>{
 const run=await leadRun([plan(bad),plan(tool('worktree_read',{path:'index.js'})),plan(bad),plan(valid)]);
 assert.equal(run.result.reason,'MODEL_ESCALATION');assert.equal(run.attempts,4);assert.equal(run.effects,1);
 const body=context(run.captures[2]);assert.equal(body.state.correction,null);assert.equal(body.state.observations.at(-1).result.provenance,'MAC_CAPABILITY');ruleCheck(body.state.resultRequirements);
 assert.equal(context(run.captures[3]).state.correction.attempt,1);
 const repeated=await leadRun([plan(bad),plan(bad)]);assert.equal(repeated.attempts,2);assert.equal(repeated.result.reason,'REPEATED_INVALID_PROPOSAL');assert.equal(repeated.effects,0);
});
test('R1 guidance and active correction count toward the exact context boundary',async()=>{
 async function run(extra,correcting){let actions=0;const requests=[];
  const result=await createWorkMode({manifest,completionPolicy:MUTABLE_WORKTREE_COMPLETION_POLICY,workspaceState:snapshot(),
   reasoner:{async invoke(q){requests.push(q);return requests.length<=6?tool('worktree_read',{path:'index.js'}):correcting&&requests.length===7?bad:valid;}},
   authorize:(p,s,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:p.capability,proposalDigest:digest(p),scope,effect:s.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false}),
   egress:({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']}),
   invoke:async()=>({ok:true,executionState:'COMPLETED',verifier:'VERIFIED',data:{text:'x'.repeat(9500+Math.floor(extra/6)+(++actions===6?extra%6:0))}}),evaluate:async()=>({passed:false})}).run({task:'essential goal',scope,capabilities:ordinary,maxIterations:16});
  return {result,requests};
 }
 for(const correcting of [false,true]){
  const index=correcting?7:6,base=await run(0,correcting),size=base.requests[index].messages[1].content.length;
  for(const target of [63999,64000,64001]){const r=await run(target-size,correcting);
   if(target<=64000){const body=JSON.parse(r.requests[index].messages[1].content);assert.equal(r.requests[index].messages[1].content.length,target);ruleCheck(body.state.resultRequirements);if(correcting)ruleCheck(body.state.correction.resultRequirements);assert.equal(body.task,'essential goal');assert.equal(body.state.observations.find(x=>x.kind==='RESULT').result.provenance,'MAC_CAPABILITY');}
   else {assert.equal(r.requests.length,index);assert.equal(r.result.reason,'MODEL_CONTEXT_LIMIT');}
  }
 }
});

const overflow='{"kind":"TOOL_PROPOSAL","capability":"worktree_read","arguments":{"path":"index.js","max_chars":1e400}}';
test('R2 overflow takes JSON_PARSE nonfinite through the real worker and shared correction',async()=>{
 const run=await leadRun([{text:overflow},plan(valid)]);
 assert.equal(run.attempts,2);assert.equal(run.endpointDispatches,2);assert.equal(run.effects,0);assert.equal(run.result.reason,'MODEL_ESCALATION');
 assert.equal(run.responses[0].reason,'private_lead_result_schema');assert.equal(diagnostics(run.rows)[0].diagnostic.stage,'JSON_PARSE');assert.equal(diagnostics(run.rows)[0].diagnostic.keyword,'nonfinite');
 for(const first of [plan(bad),{text:'{"INJECTED_PRIVATE_KEY":'},plan(tool('worktree_read',{path:3}))]){
  const mixed=await leadRun([first,{text:overflow}]);assert.equal(mixed.attempts,2);assert.equal(mixed.effects,0);assert.equal(mixed.result.reason,'REPEATED_INVALID_PROPOSAL');assert.equal(diagnostics(mixed.rows).at(-1).diagnostic.keyword,'nonfinite');
 }
});
test('R2 nonfinite event metadata is transport rejection without correction',async()=>{
 for(const value of ['1e400','-1e400','NaN','Infinity','-Infinity']){
  const run=await leadRun([{wire:'data: {"usage":{"prompt_tokens":'+value+'},"choices":[]}\n\ndata: [DONE]\n\n'},plan(valid)]);
  assert.equal(run.attempts,1);assert.equal(run.effects,0);assert.equal(run.result.reason,'PRIVATE_LEAD_UNAVAILABLE');assert.equal(run.result.state.correction,undefined);
  const diagnostic=diagnostics(run.rows)[0]?.diagnostic;assert.equal(diagnostic?.stage,'STREAM');assert.equal(diagnostic?.keyword,'nonfinite');
 }
});
test('R3 interrupted reads retain fixed facts and never retry or execute',async()=>{
 for(const error of ['OSError','TimeoutError','IncompleteRead'])for(const after of [0,1,2]){
  const wire=after===1?'data: {"choices":[{"delta":{"content":"{\\"kind\\":"},"finish_reason":null}]}\n\n':undefined;
  const run=await leadRun([{...plan(valid),...(wire?{wire}:{}),interruptAfter:after,error},plan(valid)]);
  assert.equal(run.attempts,1);assert.equal(run.endpointDispatches,1);assert.equal(run.effects,0);assert.equal(run.result.reason,'PRIVATE_LEAD_UNAVAILABLE');assert.equal(run.result.state.correction,undefined);
  const diagnostic=diagnostics(run.rows)[0]?.diagnostic;assert.equal(diagnostics(run.rows).length,1);assert.equal(diagnostic.stage,'STREAM');assert.equal(diagnostic.keyword,'completion');assert.equal(diagnostic.streamStatus,'INCOMPLETE');assert.equal(diagnostic.finishStatus,after===2?'stop':'UNKNOWN');
 }
});
test('R3 cancellation, HTTP decoding rejection, typed parser and unrelated errors stay distinct',async()=>{
 for(const [p,reason,stage] of [[{...plan(valid),interruptAfter:0,error:'cancelled'},'operation_cancelled',undefined],[{...plan(valid),interruptAfter:0,error:'unrelated'},'transport_unavailable',undefined],[{httpStatus:400},'structured_decoding_http_400',undefined],[{httpStatus:422},'structured_decoding_http_422',undefined],[{wire:'data: {bad\n\n'},'answer_incomplete','STREAM']]){
  const run=await leadRun([p,plan(valid)]);assert.equal(run.attempts,1);assert.equal(run.effects,0);assert.equal(run.responses[0].reason,reason);assert.equal(diagnostics(run.rows)[0]?.diagnostic.stage,stage);
 }
});

test('R4 actual reviewer caller logs once with captured reviewer identities',async()=>{
 for(const [p,stage,keyword] of [[plan({kind:'FINAL',text:''}),'GENERIC_RESULT','minLength'],[plan({kind:'FINAL',text:'',schemaDigest:'d'.repeat(64),semanticSchemaDigest:'e'.repeat(64)}),'GENERIC_RESULT','additionalProperties'],[{injectDiagnostic:true},'JSON_PARSE','syntax'],[{text:'{"INJECTED_PRIVATE_KEY":'},'JSON_PARSE','syntax'],[{...plan({kind:'FINAL',text:'x'}),omitDone:true},'STREAM','completion'],[{...plan({kind:'FINAL',text:'x'}),interruptAfter:0,error:'TimeoutError'},'STREAM','completion']]){
  const run=await reviewerRun(p);assert.ok(run.status.text.includes('REVIEWER_UNAVAILABLE'));assert.equal(run.attempts,2);assert.equal(run.endpointDispatches,p.injectDiagnostic?1:2);
  const rows=diagnostics(run.rows);assert.equal(rows.length,1);const expected=preflightCurrentWorkIntentSchemas().schemas.reviewer.request;
  assert.equal(rows[0].diagnostic.stage,stage);assert.equal(rows[0].diagnostic.keyword,keyword);assert.equal(rows[0].schemaDigest,expected.schemaDigest);assert.equal(rows[0].semanticSchemaDigest,expected.semanticSchemaDigest);
  assert.notEqual(rows[0].schemaDigest,request(run.captures[0]).state.workIntent.schemaDigest);
  const reviewRequest=p.injectDiagnostic?run.requests[1]:request(run.captures[1]);
  assert.deepEqual(reviewRequest.state.workIntent,expected);assert.ok(!JSON.stringify(reviewRequest).includes(pattern));
 }
});
test('R4 ACCEPT REJECT REVISE and separate verdict parser retain existing policy',async()=>{
 for(const [text,outcome,calls] of [[JSON.stringify({verdict:'ACCEPT',findings:[]}),'COMPLETE',2],[JSON.stringify({verdict:'REJECT',findings:[]}),'REVIEW_REJECTED',2],[JSON.stringify({verdict:'REVISE',findings:[]}),'COMPLETE',3],['not verdict JSON','REVIEWER_UNAVAILABLE',2]]){
  const run=await reviewerRun(plan({kind:'FINAL',text}));assert.ok(run.status.text.includes(outcome),run.status.text);assert.equal(run.attempts,calls);assert.equal(diagnostics(run.rows).length,0);
  assert.equal(run.captures.filter(x=>request(x).state.phase==='REVIEW').length,1);assert.ok(!JSON.stringify(run.captures[1]).includes(pattern));
 }
});
