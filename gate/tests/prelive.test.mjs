import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';
import {createHash,randomBytes} from 'node:crypto';
import Ajv from 'ajv';
import {readinessArtifact,SURFACES,hostSemanticReadiness} from '../runtime-readiness.mjs';
import {projectVllmGenerationSchema,validateVllmGenerationSchema} from '../foundation/vllm-structured-output.mjs';
import {digest} from '../foundation/contracts.mjs';
import {runProtocolMicroprobes,MICROPROBES} from '../protocol-microprobe.mjs';
import {executorDeadlineSeconds} from '../plugin/core.mjs';
import {verifyAuthorization} from '../diagnostic-experiment.mjs';
import {signedHarness,manifest,root} from './fixtures/targeted-harness.mjs';
const sha=x=>createHash('sha256').update(x).digest('hex');

test('six exact surfaces enumerate every valid branch through AJV without compiler claims',()=>{
 const artifact=readinessArtifact(),ajv=new Ajv({strict:false});
 assert.deepEqual(Object.keys(artifact.surfaces),SURFACES);
 for(const row of Object.values(artifact.surfaces))for(const schema of [row.request.schema,row.semanticSchema]){
  const validate=ajv.compile(schema);for(const value of row.representatives)assert.equal(validate(value),true,JSON.stringify(validate.errors));
 }
 assert.equal(artifact.exactCompiler,'NOT_RUN');assert.equal(artifact.tokenMeasurement,'NOT_RUN');assert.equal(artifact.liveEndpoint,'NOT_RUN');
});
test('production request preparation preserves actual character boundary correction and reviewer',()=>{
 const a=readinessArtifact();assert.equal(a.messages.ordinaryInitial.request.state.phase,'PLAN');assert.equal(a.messages.ordinaryInitial.request.state.decisionState,'WORK_REQUIRED');assert.equal(a.messages.postPatchContinue.request.state.decisionState,'TEST_REQUIRED');assert.equal(a.messages.nearCharacterLimit.request.messages[1].content.length,64000);
 assert.ok(a.messages.activeCorrection.request.messages[1].content.includes('REASONER_RESULT_SCHEMA'));
 assert.deepEqual(a.messages.postPatchContinue.request.state.workIntent,a.surfaces.ordinaryIneligible.request);
 assert.deepEqual(a.messages.reviewer.request.state.workIntent,a.surfaces.reviewer.request);
 assert.deepEqual(a,readinessArtifact());
});
test('generation projection removes only incompatible constraints while host length and path rules reject',()=>{
 const artifact=readinessArtifact();
 for(const row of Object.values(artifact.surfaces)){
  const before=structuredClone(row.semanticSchema),projection=projectVllmGenerationSchema(row.semanticSchema);
  assert.deepEqual(row.semanticSchema,before);assert.deepEqual(projection.schema,row.request.schema);
  assert.ok(projection.omitted.every(x=>['pattern','minLength','maxLength'].includes(x.keyword)));
  const host=row.hostSemanticValidation;
  assert.equal(host.status,'PASS');assert.equal(host.semanticSchemaDigest,digest(row.semanticSchema));
  assert.equal(host.representativesDigest,digest(row.representatives));assert.equal(host.positiveBranches,row.branches);
  assert.ok(host.negativeControls.length>row.branches);assert.ok(host.negativeControls.every(c=>c.rejected));
  if(JSON.stringify(row.semanticSchema).includes('"maxLength"'))assert.ok(host.negativeControls.some(c=>c.keyword==='maxLength'));
  assert.deepEqual(hostSemanticReadiness(row.semanticSchema,row.representatives),host);
  const invalid=structuredClone(row.representatives);invalid[0].unexpected_field=true;
  assert.throws(()=>hostSemanticReadiness(row.semanticSchema,invalid),/semantic_invalid/);
 }
 const ordinary=artifact.surfaces.ordinaryEligible;
 for(const keyword of ['minLength','maxLength','pattern'])assert.ok(ordinary.hostSemanticValidation.negativeControls.some(c=>c.keyword===keyword));
 assert.equal(validateVllmGenerationSchema({type:'string',minLength:1}).ok,false);
 assert.equal(validateVllmGenerationSchema({type:'string',maxLength:10}).ok,false);
 const projected=projectVllmGenerationSchema({type:'array',minItems:1,maxItems:2,items:{type:'string',minLength:1,maxLength:10}}).schema;
 assert.deepEqual(projected,{type:'array',minItems:1,maxItems:2,items:{type:'string'}});
});
test('executor derives remaining worker lifetime from absolute experiment deadline',()=>{
 const now=Date.now()/1000,body={operation:'private_lead_propose',packet:{experiment:{deadline:now+170}}};
 const value=executorDeadlineSeconds(body,{});assert.ok(value>49&&value<=50);
 body.packet.experiment.deadline=now;assert.equal(executorDeadlineSeconds(body,{}),0);
 assert.equal(executorDeadlineSeconds({operation:'private_lead_propose',packet:{}},{private_lead:{readiness_seconds:30},request_deadline_seconds:120}),150);
});
test('diagnostic proposals share five-call ceiling and fixed order with existing correction allowance',async()=>{
 let calls=0;const order=[];
 const reasoner={async invoke(){calls++;return calls%2===1?{kind:'ESCALATION',reason:'bad reason'}:calls===2?{kind:'TOOL_PROPOSAL',capability:'worktree_read',arguments:{path:'index.js'}}:calls===4?{kind:'TOOL_PROPOSAL',capability:'worktree_command',arguments:{operation:'test'}}:{kind:'ESCALATION',reason:'SYNTHETIC'};}};
 const result=await runProtocolMicroprobes({reasoner,manifest,experiment:{deadline:Date.now()/1000+900},beforeProbe:id=>order.push(id)});
 assert.equal(calls,5);assert.equal(result.passed,false);assert.deepEqual(order,MICROPROBES.map(x=>x.id));assert.equal(result.rows[2].passed,false);
});
test('deadline and first failure prevent later probes or new inference',async()=>{
 let calls=0;const reasoner={async invoke(){calls++;return {kind:'TOOL_PROPOSAL',capability:'worktree_list',arguments:{}};}};
 const result=await runProtocolMicroprobes({reasoner,manifest,experiment:{deadline:Date.now()/1000+900}});
 assert.equal(calls,1);assert.equal(result.rows.length,1);assert.equal(result.passed,false);
 await assert.rejects(runProtocolMicroprobes({reasoner,manifest,experiment:{deadline:Date.now()/1000}}),/deadline/);assert.equal(calls,1);
});
test('allocation authorization requires all free gates identity and proposed ceiling',()=>{
 const identity={source_id:'a'.repeat(64),install_id:'b'.repeat(64)};
 const authorization={...identity,schema:'sanctum-diagnostic-authorization/v1',ownerAuthorized:true,allocationLimit:1,seconds:900,computeCeilingUsd:0.75,hourlyUsd:3,expires:1001,gates:Object.fromEntries(['independentReview','installedBytes','doctor','authenticatedWorkHelp','schemaPreflight','exactCompiler','tokenMeasurement','janitor','zeroOwnership','pricingAndCharges'].map(x=>[x,true]))};
 assert.equal(verifyAuthorization(authorization,identity,1000),authorization);
 for(const key of Object.keys(authorization.gates))assert.throws(()=>verifyAuthorization({...authorization,gates:{...authorization.gates,[key]:false}},identity,1000));
 for(const delta of [{ownerAuthorized:false},{hourlyUsd:3.01},{allocationLimit:2},{seconds:901},{source_id:'c'.repeat(64)}])assert.throws(()=>verifyAuthorization({...authorization,...delta},identity,1000));
});
test('signed actual worker persists global reservations across processes and rejects stale identities',async()=>{
 const h=signedHarness([]);
 try{
  writeFileSync(join(h.dir,'receipt.json'),JSON.stringify({work_mode_source_manifest_sha256:'b'.repeat(64)}));
  const binding={experiment_id:'a'.repeat(32),source_id:'b'.repeat(64),install_id:sha(readFileSync(join(h.pkg,'FREEZE.json'))),deadline:Date.now()/1000+900};
  const init=`import sys,json,os,time\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nfrom experiment import ExperimentLedger,process_identity\nroot,b,pid=json.loads(sys.argv[2]);ledger=ExperimentLedger(root);ledger.create(b,owner_pid=pid,owner_process=process_identity(pid))\nwith ledger.transaction() as c:\n r=ledger._bound(c,b);r.update(ready=True,allocation='OWNED',allocation_id='synthetic-pod',supervisor_pid=pid,supervisor_process=process_identity(pid),supervisor_heartbeat=time.time());ledger._write(c,r)\n`;
  execFileSync(h.settings.python,['-B','-c',init,join(h.pkg,'src'),JSON.stringify([join(h.settings.state_directory,'private-lead'),binding,process.pid])]);
  writeFileSync(join(h.dir,'transport/worker.py'),`import runpy\nrunpy.run_path(${JSON.stringify(join(root,'gate/tests/fixtures/prelive_worker.py'))},init_globals={'PACKAGE_ROOT':${JSON.stringify(h.pkg)},'FIXTURE_ROOT':${JSON.stringify(h.dir)}},run_name='__main__')\n`);
  const request=readinessArtifact().messages.ordinaryInitial;
  const body=experiment=>({operation:'private_lead_propose',tier:'PRIVATE_LEAD',packet:{request,experiment},state:{scope:'a'.repeat(32),privacy_floor:'PERSONAL',high_stakes:false},scope:'a'.repeat(32),approval:'private_lead_workmode',strong:false,nonce:randomBytes(32).toString('hex'),expires:Date.now()/1000+60,spec_sha256:sha(readFileSync(join(h.pkg,'SETTINGS.json')))});
  for(let i=0;i<5;i++)assert.equal((await h.execute(body(binding))).status,'OK');
  assert.equal((await h.execute(body(binding))).status,'UNAVAILABLE');
  assert.equal((await h.execute(body({...binding,experiment_id:'d'.repeat(32)}))).status,'UNAVAILABLE');
  const rows=readFileSync(join(h.dir,'dispatch-counts.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
  assert.deepEqual(rows.map(x=>x.reserved),[1,2,3,4,5]);assert.deepEqual(rows.map(x=>x.dispatched),[1,2,3,4,5]);
  assert.ok(rows.every(x=>x.deadline===binding.deadline&&x.timeout<=120));
 }finally{h.close();}
});
test('runbook enforces ordered free gates fixed probes first failure and confirmed cleanup',()=>{
 const path=join(root,'docs/history/v1.1/project-3/PROJECT-3-QWEN-PRELIVE-READINESS.md');assert.ok(existsSync(path));
 const text=readFileSync(path,'utf8');
 const start=text.indexOf('<!-- RUNBOOK START -->'),end=text.indexOf('<!-- RUNBOOK END -->');assert.ok(start>=0&&end>start);
 const book=text.slice(start,end);assert.ok(book.includes('NOT AUTHORIZED TO EXECUTE BY THIS WORK PACKAGE'));
 const keys=['01 VERIFY_SOURCE','02 VERIFY_BRANCH','03 GATEWAY_STOPPED','04 BOTH_RELEASES_SAFE','05 ZERO_OWNERSHIP','06 SUPERVISOR_READY','07 AMEND','08 INSTALLED_BYTES','09 DOCTOR','10 AUTHENTICATED_GATEWAY','11 WORK_HELP','12 SCHEMA_PREFLIGHT','13 NEW_LEDGER','14 PRICE_AND_CEILING','15 OWNER_AUTHORIZE','16 SINGLE_SMOKE','17 SMOKE_FAILURE_STOP','18 FIXED_PROBES','19 SHARED_BUDGET','20 STOP_FIRST_FAILURE','21 DELETE','22 CONFIRM_ABSENCE','23 ZERO_LEASES','24 PRESERVE_STORAGE','25 UNCERTAIN_SUPERVISION','26 RECEIPT'];
 let previous=-1;for(const key of keys){const index=book.indexOf(key);assert.ok(index>previous,key);previous=index;}
 assert.ok(book.includes('inspection → postPatch → inability'));assert.ok(book.includes('six'));assert.ok(book.includes('16-token'));assert.ok(!book.includes('qualify_work_mode.py'));
});
