import test from 'node:test';
import assert from 'node:assert/strict';
import {stagePlan,validateStages,runStages,runAndRecord} from '../plugin/work-stages.mjs';
const stages=[{name:'logic',goal:'Implement and test logic.',required_files:['logic.js','logic.test.js']},{name:'ui',goal:'Connect the UI.',required_files:['index.html']}];
const options={scope:'a'.repeat(32),workspace:'a'.repeat(32),maxIterations:8,maxModelCalls:8,maxTaskSeconds:60};
const complete={status:'COMPLETE',reason:'HOST_VERIFIED',metrics:{iterations:1,modelCalls:2}};
test('stages reject path escapes, overrides, duplicate names and oversized assembled prompts',()=>{
 for(const value of [[],[stages[0]],Array(4).fill(stages[0]),[stages[0],stages[0]],[{...stages[0],max_model_calls:32},stages[1]],[{...stages[0],required_files:['../secret']},stages[1]],[{...stages[0],required_files:['/secret']},stages[1]]])assert.throws(()=>validateStages(value));
 assert.throws(()=>stagePlan('x'.repeat(4000),stages));
 assert.deepEqual(stagePlan('task'),[{name:null,required_files:[],task:'task'}]);
});
test('checkpoints share workspace, calls, iterations, elapsed time and cumulative required files',async()=>{
 let clock=10;const seen=[],checks=[],selected=[];
 const result=await runStages({plan:stagePlan('Build a log',stages),options,now:()=>clock,onStage:stage=>selected.push(stage),onCheckpoint:row=>checks.push(row),run:async args=>{seen.push(args);clock+=5;return complete;}});
 assert.equal(seen[1].scope,seen[0].scope);assert.equal(seen[1].workspace,seen[0].workspace);
 assert.equal(seen[1].maxModelCalls,6);assert.equal(seen[1].maxIterations,6);assert.equal(seen[1].maxTaskSeconds,55);
 assert.deepEqual(selected[1].required_files,['logic.js','logic.test.js','index.html']);
 assert.equal(checks.length,2);assert.equal(result.checkpointsCompleted,2);assert.deepEqual(result.metrics,{iterations:4,modelCalls:4,elapsedSeconds:10});
});
test('failed checkpoint and exhausted budgets never advance',async()=>{
 for(const mode of ['failure','calls','time']){
  let runs=0,clock=0;const result=await runStages({plan:stagePlan('Build',stages),options:{...options,maxModelCalls:mode==='calls'?2:8},now:()=>clock,run:async()=>{runs++;clock=mode==='time'?61:1;return mode==='failure'?{...complete,status:'BLOCKED',reason:'TEST_FAILED'}:complete;}});
  assert.equal(runs,1);assert.equal(result.status,mode==='failure'?'BLOCKED':'BUDGET_EXHAUSTED');
 }
});
test('receipt failure preserves primary failure and metrics but cannot certify COMPLETE',async()=>{
 for(const status of ['ENVIRONMENT_FAILURE','BLOCKED','COMPLETE']){
  const original={...complete,status,reason:status==='COMPLETE'?'HOST_VERIFIED':'PRIVATE_LEAD_UNAVAILABLE',providerCode:'operation_unavailable'};
  const result=await runAndRecord({run:async()=>original,finish:()=>{throw Object.assign(Error('private path omitted'),{code:'ENOSPC'});}});
  assert.deepEqual(result.metrics,original.metrics);assert.equal(result.providerCode,original.providerCode);assert.equal(result.persistenceWarning,'LOCAL_DISK_FULL');
  assert.equal(result.reason,status==='COMPLETE'?'EVIDENCE_PERSISTENCE_FAILED':original.reason);
 }
});
test('storage refusals remain specific even when coordinator or ledger fails',async()=>{
 const result=await runAndRecord({run:async()=>({...complete,status:'ENVIRONMENT_FAILURE',reason:'PRIVATE_LEAD_UNAVAILABLE',providerCode:'local_disk_low'}),finish:()=>{throw Error('failed');}});
 assert.equal(result.reason,'LOCAL_DISK_LOW');assert.equal(result.persistenceWarning,'LEDGER_UNAVAILABLE');
 const thrown=await runAndRecord({run:async()=>{throw Object.assign(Error('full'),{code:'ENOSPC'});},finish:()=>{}});
 assert.equal(thrown.reason,'LOCAL_DISK_FULL');
});

test('partial ledger append poisons the chain and temporary snapshot files are cleaned on ENOSPC',async t=>{
 const fs=(await import('node:fs')).default;
 const {syncBuiltinESMExports}=await import('node:module');
 const {tmpdir}=await import('node:os');
 const {join}=await import('node:path');
 const {createWorkLedger}=await import('../plugin/work-ledger.mjs');
 const root=fs.mkdtempSync(join(tmpdir(),'work-ledger-storage-'));fs.chmodSync(root,0o700);
 t.after(()=>{t.mock.restoreAll();syncBuiltinESMExports();fs.rmSync(root,{recursive:true,force:true});});
 const ledger=createWorkLedger({root,taskId:'a'.repeat(32),key:Buffer.alloc(32)});
 const append=fs.appendFileSync;
 t.mock.method(fs,'appendFileSync',(path)=>{append(path,'partial');throw Object.assign(Error('full'),{code:'ENOSPC'});});syncBuiltinESMExports();
 assert.throws(()=>ledger.event('PHASE',{phase:'PLAN'}),{code:'ENOSPC'});
 const damaged=fs.readFileSync(join(ledger.directory,'events.jsonl'),'utf8');
 t.mock.restoreAll();syncBuiltinESMExports();
 assert.throws(()=>ledger.finish({status:'COMPLETE'}),/work_ledger_broken/);
 assert.equal(fs.readFileSync(join(ledger.directory,'events.jsonl'),'utf8'),damaged);
 const other=createWorkLedger({root,taskId:'b'.repeat(32),key:Buffer.alloc(32)});
 const write=fs.writeFileSync;
 t.mock.method(fs,'writeFileSync',(path,...args)=>{if(typeof path==='number')throw Object.assign(Error('full'),{code:'ENOSPC'});return write(path,...args);});syncBuiltinESMExports();
 assert.throws(()=>other.finish({status:'BLOCKED',reason:'TEST_FAILED'}),{code:'ENOSPC'});
 assert.deepEqual(fs.readdirSync(other.directory),['events.jsonl']);
 t.mock.restoreAll();syncBuiltinESMExports();
 other.cleanup({workspaceCleaned:true,gpuPhase:'OFFLINE'});
 assert.equal(JSON.parse(fs.readFileSync(join(other.directory,'summary.json'))).reason,'TEST_FAILED');
});

test('owner command advances only after required files and ordinary evaluator pass',async t=>{
 const fs=await import('node:fs');const {tmpdir}=await import('node:os');const {join,resolve}=await import('node:path');
 const {createWorkCommand}=await import('../plugin/work-command.mjs');
 const {deriveCapabilityManifest,publishCapabilityManifest}=await import('../foundation/manifest.mjs');
 const {registeredWorkModeTools,workModeTools}=await import('../plugin/workspace-tools.mjs');
 const {syntheticProtection}=await import('./fixtures/task-evidence.mjs');
 const names=workModeTools.map(tool=>tool.name);publishCapabilityManifest(deriveCapabilityManifest({schemas:workModeTools,declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}}));
 const base=resolve(import.meta.dirname,'..'),original=JSON.parse(fs.readFileSync(join(base,'SETTINGS.json')));
 for(const missing of [false,true]){
  const root=fs.mkdtempSync(join(tmpdir(),'work-staged-command-'));fs.chmodSync(root,0o700);
  const profileFile=join(root,'profiles.json');
  fs.writeFileSync(profileFile,JSON.stringify({schema:'sanctum-work-mode-profiles/v1',profiles:{staged:{stages,reviewer:false,evaluators:['test'],max_iterations:8,max_model_calls:8,max_task_seconds:60}}}),{mode:0o600});
  const settings={...original,work_mode:{enabled:true,profile_file:profileFile,ledger_root:join(root,'ledger')}};
  let modelCalls=0,evaluatorCalls=0;const reads=[];
  const remote=async body=>{
   if(body.operation==='worktree_create')return {status:'OK',workspace:{base_commit:'c'.repeat(40),initial_status:'CLEAN',disk_bytes:1}};
   if(body.operation==='worktree_integrity')return {status:'OK',result:await syntheticProtection({scope:body.scope})};
   if(body.operation==='worktree_read'){reads.push(body.packet.path);return missing&&body.packet.path==='logic.test.js'?{status:'UNAVAILABLE',reason:'workspace_source_missing'}:{status:'OK',result:{text:'x'}};}
   if(body.operation==='worktree_command'){if(body.packet.operation==='test')evaluatorCalls++;return {status:'OK',result:{ok:true,code:'OK',executionState:'COMPLETED',output_digest:'d'.repeat(64),output_bytes:1,output:'x',elapsed_ms:1}};}
   if(body.operation==='private_lead_propose'){modelCalls++;return {status:'OK',result:{kind:'TOOL_PROPOSAL',capability:'worktree_command',arguments:{operation:'test'}},telemetry:{prompt_tokens:1,completion_tokens:1,elapsed_seconds:0.01}};}
   if(body.operation==='close')return {status:'OK',gpu:{phase:'OFFLINE'}};
   if(body.operation==='worktree_cleanup')return {status:'OK'};
   throw Error('unexpected '+body.operation);
  };
  const work=createWorkCommand({base,settings,key:Buffer.alloc(32),remote,api:{runtime:{config:{current:()=>({gateway:{bind:'loopback',port:1,auth:{mode:'token',token:'synthetic'}}})}}}});
  const tools=registeredWorkModeTools();
  t.mock.method(globalThis,'fetch',async(_url,options)=>{const packet=JSON.parse(options.body);const result=await tools.find(tool=>tool.name===packet.name).execute('synthetic',packet.args,options.signal);return {ok:true,json:async()=>({ok:true,result})};});
  try{
   const ctx={isAuthorizedSender:true,gatewayClientScopes:['operator.admin'],sessionKey:'synthetic-'+missing};
   const started=await work({...ctx,args:'start staged -- Build a log'});assert.match(started.text,/started in an isolated workspace/);
   let status;
   for(let i=0;i<100;i++){await new Promise(setImmediate);status=await work({...ctx,args:'status'});if(status.text.includes('TERMINAL'))break;}
   assert.match(status.text,missing?/FINAL_WITHOUT_PASSING_EVIDENCE/:/status COMPLETE/);
   assert.equal(modelCalls,missing?1:2);assert.equal(evaluatorCalls,missing?2:4);
   assert.deepEqual(reads,missing?['logic.js','logic.test.js']:['logic.js','logic.test.js','logic.js','logic.test.js','index.html']);
  }finally{await work.close();t.mock.restoreAll();fs.rmSync(root,{recursive:true,force:true});}
 }
});
