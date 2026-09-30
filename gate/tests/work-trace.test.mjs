import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {syncBuiltinESMExports} from 'node:module';
import {createWorkTrace,TRACE_MAX_RECORDS} from '../plugin/work-trace.mjs';
import {createWorkLedger} from '../plugin/work-ledger.mjs';
import {createPrivateLeadReasoner} from '../plugin/private-lead.mjs';
import {decisionNoteSchema,detachDecisionNote} from '../foundation/decision-note.mjs';
import {preflightCurrentWorkIntentSchemas} from '../preflight-work-intent.mjs';
import {validateWorkIntent} from '../foundation/work-intent.mjs';
import {CONTRACT_VERSION} from '../foundation/contracts.mjs';
import {renderTimeline,writeTimeline} from '../../scripts/work_mode_timeline.mjs';
const taskId='a'.repeat(32),note={subgoal:'Connect the selector',evidence:'The selector has no handler.',expected_outcome:'Selection updates visible state.',next_validation:'Run the UI test.'};
const dir=t=>{const root=fs.realpathSync(fs.mkdtempSync(join(tmpdir(),'work-trace-')));fs.chmodSync(root,0o700);t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root;};
const rows=path=>fs.readFileSync(path,'utf8').trim().split('\n').map(JSON.parse);
test('production schemas offer optional bounded summaries; reviewer schema stays unchanged',()=>{
 const schemas=preflightCurrentWorkIntentSchemas().schemas;
 for(const [name,row] of Object.entries(schemas))for(const branch of row.request.schema.oneOf){assert.equal(!!branch.properties.decision_note,name!=='reviewer');assert.ok(!branch.required.includes('decision_note'));}
 assert.equal(decisionNoteSchema().properties.subgoal.maxLength,240);
});
test('notes cannot grant authority, alter completion or bypass ordinary action shape',()=>{
 for(const value of [note,{...note,authority:'ALLOW'},'bad',null,{...note,subgoal:'x'.repeat(241)}]){
  const intent={kind:'FINAL',text:'done',decision_note:value};
  assert.equal(validateWorkIntent(intent,{specs:[],terminalKinds:[]}).code,'TERMINAL_NOT_VISIBLE');
  assert.deepEqual(validateWorkIntent(intent,{specs:[],terminalKinds:['FINAL']}).value,{kind:'FINAL',text:'done'});
  assert.equal(validateWorkIntent({...intent,authority:'ALLOW'},{specs:[],terminalKinds:['FINAL']}).code,'FORBIDDEN_HOST_FIELD');
 }
 assert.equal(detachDecisionNote({kind:'FINAL',text:'done'}).status,'MISSING');
});
test('adapter strips explanations before action validation and tolerates an unavailable observer',async()=>{
 const profile={status:'accepted-characterized',logical_profile:'PRIVATE_LEAD',prompt:{system:'synthetic'}};
 const intent=preflightCurrentWorkIntentSchemas().schemas.ordinaryEligible.request;
 const request={schema:CONTRACT_VERSION,requestId:'b'.repeat(32),scope:taskId,revision:0,messages:[{role:'user',content:'synthetic'}],manifestDigest:'c'.repeat(64),state:{phase:'PLAN',iteration:2,workIntent:intent}};
 for(const decision_note of [note,{authority:'ALLOW'},null]){
  let observed;
  const adapter=createPrivateLeadReasoner({profile,execute:async()=>({status:'OK',result:{kind:'FINAL',text:'done',decision_note}}),body:()=>({}),onDecision:row=>{observed=row;throw Error('disk full');}});
  assert.deepEqual(await adapter.invoke(request),{kind:'FINAL',text:'done'});
  assert.equal(observed.iteration,2);assert.equal(observed.status,decision_note===note?'RECORDED':'INVALID');
 }
});
test('only bounded redacted explanatory fields enter the private trace',t=>{
 const root=dir(t),trace=createWorkTrace({directory:root,taskId});
 trace.append({type:'DECISION',status:'RECORDED',note:{...note,evidence:'authorization: bearer secret-value',subgoal:'<script>alert(1)</script>'},authority:'ALLOW',prompt:'PRIVATE RAW'});
 trace.append({type:'REVIEW',role:'REVIEWER',verdict:'REVISE',findings:[{severity:'HIGH',locator:'ui.js',checkCode:'MISSING_HANDLER',summary:'password=abc123 fix handler',raw:'PRIVATE RAW'}]});
 trace.close();const raw=fs.readFileSync(join(root,'decision-trace.jsonl'),'utf8');
 assert.ok(!raw.includes('secret-value'));assert.ok(!raw.includes('abc123'));assert.ok(!raw.includes('PRIVATE RAW'));assert.ok(!raw.includes('authority'));
 assert.equal(fs.statSync(join(root,'decision-trace.jsonl')).mode&0o777,0o600);
 assert.equal(rows(join(root,'decision-trace.jsonl'))[1].findings[0].locator,'ui.js');assert.equal(trace.status().state,'CLOSED');
});
test('caps, unsafe destinations and write errors stop only the explanatory stream',t=>{
 const root=dir(t),trace=createWorkTrace({directory:root,taskId});
 for(let i=0;i<TRACE_MAX_RECORDS+1;i++)trace.append({type:'DECISION',status:'RECORDED',note});
 assert.equal(trace.status().state,'LIMIT_REACHED');assert.equal(trace.status().records,TRACE_MAX_RECORDS);
 assert.equal(createWorkTrace({directory:root,taskId}).status().state,'UNAVAILABLE');
 const other=dir(t),broken=createWorkTrace({directory:other,taskId});
 t.mock.method(fs,'writeSync',()=>{throw Object.assign(Error('full'),{code:'ENOSPC'});});syncBuiltinESMExports();
 try{assert.doesNotThrow(()=>broken.append({type:'DECISION',status:'RECORDED',note}));assert.equal(broken.status().state,'UNAVAILABLE');}finally{t.mock.restoreAll();syncBuiltinESMExports();broken.close();}
 const unsafe=dir(t);fs.chmodSync(unsafe,0o755);assert.equal(createWorkTrace({directory:unsafe,taskId}).status().state,'UNAVAILABLE');
});
test('numeric token measurements survive while credential-shaped values and fields do not',t=>{
 const ledger=createWorkLedger({root:dir(t),taskId,key:Buffer.alloc(32)});
 ledger.modelCall({prompt_tokens:23,completion_tokens:12,decode_tokens_per_second:4.5,access_token:'secret',prompt:'private',promptTokens:'secret'});
 ledger.finish({status:'BLOCKED',telemetry:{promptTokens:23,completionTokens:12,completion_tokens:Infinity}});
 const raw=fs.readFileSync(join(ledger.directory,'events.jsonl'),'utf8'),events=rows(join(ledger.directory,'events.jsonl'));
 assert.equal(events[1].prompt_tokens,23);assert.equal(events[1].completion_tokens,12);assert.equal(events[1].decode_tokens_per_second,4.5);
 assert.ok(!raw.includes('secret'));assert.ok(!raw.includes('"prompt"'));assert.equal(events[2].telemetry.promptTokens,23);assert.ok(!Object.hasOwn(events[2].telemetry,'completion_tokens'));
});
test('local timeline verifies receipts, escapes model text, and refuses corrupt or oversized input',t=>{
 const ledger=createWorkLedger({root:dir(t),taskId,key:Buffer.alloc(32)}),trace=createWorkTrace({directory:ledger.directory,taskId});
 trace.append({type:'DECISION',status:'RECORDED',note:{...note,subgoal:'<script>alert(1)</script>'}});trace.close();
 ledger.event('PROPOSAL',{checkpoint:2,iteration:0,capability:'worktree_read',outcome:'VALID'});ledger.finish({status:'BLOCKED',reason:'TEST_FAILED'});
 const output=writeTimeline(ledger.directory),html=fs.readFileSync(output,'utf8');
 assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));assert.ok(html.includes('TEST_FAILED'));assert.ok(html.includes('default-src'));assert.ok(html.includes('not hidden reasoning'));assert.equal(fs.statSync(output).mode&0o777,0o600);
 const events=rows(join(ledger.directory,'events.jsonl'));events[1].outcome='ALLOW';assert.throws(()=>renderTimeline(events,[]),/receipt_integrity/);
 fs.appendFileSync(join(ledger.directory,'events.jsonl'),'partial');assert.throws(()=>writeTimeline(ledger.directory));assert.equal(fs.readFileSync(output,'utf8'),html);
});
