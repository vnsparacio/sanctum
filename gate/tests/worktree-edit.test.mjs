import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {workModeTools} from '../plugin/workspace-tools.mjs';
import {deriveCapabilityManifest} from '../foundation/manifest.mjs';
import {bindWorkIntent,validateWorkIntent,workIntentRequest,workIntentSchema} from '../foundation/work-intent.mjs';
import {CONTRACT_VERSION,digest,validateReasonerResult} from '../foundation/contracts.mjs';
import {createWorkMode,MUTABLE_WORKTREE_COMPLETION_POLICY,WORKSPACE_EVIDENCE_VERSION} from '../plugin/work-mode.mjs';
import {normalizeWorkspacePacket,workCapabilityRefusal} from '../plugin/work-command.mjs';
import {compile,prepare} from '../../reliability/runtime.mjs';
import {syntheticProtection} from './fixtures/task-evidence.mjs';
const names=workModeTools.map(x=>x.name),manifest=deriveCapabilityManifest({schemas:workModeTools,registeredTools:names,declaredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
const specs=manifest.capabilities,scope='a'.repeat(32),options={specs,terminalKinds:['ESCALATION']};
const intent=(capability,args)=>({kind:'TOOL_PROPOSAL',capability,arguments:args});
const edit=intent('worktree_edit',{operation:'replace',path:'a.js',old_text:'old',new_text:'new'}),read=intent('worktree_read',{path:'a.js'});
const allow=(proposal,spec,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:proposal.capability,proposalDigest:digest(proposal),scope,effect:spec.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false});
const egress=({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']});
function run(rows,{invoke,observeRead,egressOverride,maxIterations=8}={}){
 const requests=[],events=[],calls=[];let i=0;
 const work=createWorkMode({manifest,reasoner:{async invoke(request){requests.push(request);return rows[i++]??{kind:'ESCALATION',reason:'DONE'};}},authorize:allow,egress:egressOverride??egress,observeRead,verifyProtectedEvidence:syntheticProtection,completionPolicy:MUTABLE_WORKTREE_COMPLETION_POLICY,workspaceState:async({scope,workspace,turn})=>({schema:WORKSPACE_EVIDENCE_VERSION,scope,workspace,turn,diff:{ok:true,executionState:'COMPLETED',digest:'a'.repeat(64),bytes:1},status:{ok:true,executionState:'COMPLETED',digest:'b'.repeat(64),bytes:1}}),invoke:async({proposal})=>{calls.push(proposal);return invoke?invoke(proposal):{ok:true,executionState:'COMPLETED',data:{text:'old'}};},evaluate:async()=>({passed:true}),onEvent:(kind,value)=>events.push({kind,...value})});
 return work.run({task:'synthetic',scope,capabilities:names.filter(x=>x!=='source_first_research'),maxIterations}).then(result=>({result,requests,events,calls}));
}
test('normal registered and generation surfaces expose bounded edit and patch operations without whole-file fallback',()=>{
 assert.ok(names.includes('worktree_edit'));assert.ok(names.includes('worktree_patch'));for(const name of ['worktree_create','worktree_delete','worktree_replace_file'])assert.ok(!names.includes(name));
 const request=workIntentRequest(specs,{terminalKinds:['ESCALATION']});assert.ok(JSON.stringify(request).includes('worktree_patch'));
 assert.equal(validateWorkIntent(intent('worktree_patch',{patch:'diff'}),options).ok,true);
 assert.equal(manifest.byName.worktree_edit.policy.effect,'MUTATION');assert.deepEqual(manifest.byName.worktree_edit.policy.repairRules,[]);
 assert.equal(manifest.byName.worktree_patch.policy.effect,'MUTATION');assert.deepEqual(manifest.byName.worktree_patch.policy.repairRules,[]);
});
test('generated and host edit contracts require the same four exact argument shapes',()=>{
 const editSpec=manifest.byName.worktree_edit;
 const authoritative=workIntentSchema([editSpec],{terminalKinds:['ESCALATION']});
 const branch=authoritative.oneOf.find(x=>x.properties?.capability?.const==='worktree_edit');
 const shapes=branch.properties.arguments.oneOf;
 assert.deepEqual(shapes.map(x=>x.required),[['operation','path','old_text','new_text'],['operation','path','new_text'],['operation','path'],['operation','path','destination']]);
 assert.ok(shapes.every(x=>x.additionalProperties===false));
 const generation=workIntentRequest([editSpec],{terminalKinds:['ESCALATION']});
 assert.equal(generation.schema.oneOf[0].properties.arguments.oneOf.length,4);
 for(const args of [
  {operation:'replace',path:'README.md',old_text:'old',new_text:'new'},
  {operation:'create',path:'index.js',new_text:'content'},
  {operation:'delete',path:'README.md'},
  {operation:'move',path:'README.md',destination:'docs/README.md'},
 ])assert.equal(validateWorkIntent(intent('worktree_edit',args),options).ok,true);
 for(const args of [
  {operation:'create',path:'index.js',new_text:'content',old_text:'old'},
  {operation:'create',path:'index.js'},
  {operation:'delete',path:'README.md',new_text:''},
  {operation:'move',path:'README.md',destination:'docs/README.md',new_text:'x'},
  {path:'README.md',new_text:'new'},
 ])assert.equal(validateWorkIntent(intent('worktree_edit',args),options).code,'ARGUMENT_SCHEMA');
});
test('missing-source recovery exposes only the create edit shape to generation and validation',()=>{
 const editSpec=manifest.byName.worktree_edit;
 const recovery={specs:[editSpec],terminalKinds:['ESCALATION'],editOperations:['create']};
 const authoritative=workIntentSchema([editSpec],recovery);
 const shapes=authoritative.oneOf[0].properties.arguments.oneOf;
 assert.deepEqual(shapes.map(x=>x.required),[['operation','path','new_text']]);
 assert.equal(workIntentRequest([editSpec],recovery).schema.oneOf[0].properties.arguments.oneOf.length,1);
 assert.equal(validateWorkIntent(intent('worktree_edit',{operation:'create',path:'new.js',new_text:'ready'}),recovery).ok,true);
 for(const args of [{operation:'delete',path:'new.js'},{operation:'move',path:'new.js',destination:'other.js'},{path:'new.js',old_text:'old',new_text:'new'}])assert.equal(validateWorkIntent(intent('worktree_edit',args),recovery).code,'ARGUMENT_SCHEMA');
});
test('malformed edit is corrected before authority and preflight refusal is known not started',async()=>{
 const invalid=intent('worktree_edit',{operation:'create',path:'index.js',new_text:'content',old_text:'old'});
 const valid=intent('worktree_edit',{operation:'create',path:'index.js',new_text:'content'});
 const out=await run([invalid,valid],{invoke:()=>({ok:true,executionState:'COMPLETED',verifier:'VERIFIED'})});
 assert.equal(out.calls.length,1);
 assert.equal(out.calls[0].arguments.operation,'create');
 assert.ok(out.events.some(x=>x.kind==='PROPOSAL'&&x.outcome==='REJECTED'&&x.code==='ARGUMENT_SCHEMA'));
 assert.deepEqual(workCapabilityRefusal('worktree_edit',{reason:'EDIT_SCHEMA_INVALID'}),{ok:false,error:{code:'EDIT_SCHEMA_INVALID'},executionState:'NOT_STARTED',verifier:'REJECTED'});
 assert.equal(workCapabilityRefusal('worktree_edit',{reason:'operation_unavailable'}).executionState,'COMPLETION_UNKNOWN');
});
test('missing source and parent feedback identifies the model-relative action without host paths',async()=>{
 for(const [code,phrase] of [['EDIT_SOURCE_MISSING','operation=create'],['EDIT_PARENT_MISSING','workspace root']]){
  const response=workCapabilityRefusal('worktree_edit',{reason:code});
  assert.equal(response.executionState,'NOT_STARTED');
  assert.equal(response.error.code,code);
  assert.ok(response.error.diagnostic.includes(phrase));
  assert.ok(!response.error.diagnostic.includes('src/app.js'));
 }
 const out=await run([intent('worktree_edit',{operation:'create',path:'src/app.js',new_text:'x'})],{invoke:()=>workCapabilityRefusal('worktree_edit',{reason:'EDIT_PARENT_MISSING'})});
 const event=out.events.find(x=>x.kind==='EDIT');
 assert.deepEqual({operation:event.operation,pathDepth:event.pathDepth,errorCode:event.errorCode},{operation:'create',pathDepth:2,errorCode:'EDIT_PARENT_MISSING'});
 assert.ok(!JSON.stringify(event).includes('src/app.js'));
 assert.ok(out.requests[1].messages[1].content.includes('workspace root'));
 assert.ok(out.requests[1].messages[1].content.includes('src/app.js')); // echoed model-relative action, never a host path
});
test('missing-source recovery narrows the next surface and accepts a valid create',async()=>{
 const missing=intent('worktree_edit',{operation:'delete',path:'new.js'});
 const created=intent('worktree_edit',{operation:'create',path:'new.js',new_text:'export const ready = true;'});
 const out=await run([missing,created],{invoke:p=>p.capability==='worktree_edit'&&p.arguments.operation==='delete'?workCapabilityRefusal('worktree_edit',{reason:'EDIT_SOURCE_MISSING'}):{ok:true,executionState:'COMPLETED',verifier:'VERIFIED'}});
 assert.equal(out.calls.filter(x=>x.capability==='worktree_edit').length,2);
 const beforeCreate=out.requests[1];
 assert.equal(JSON.parse(beforeCreate.messages[1].content).state.missingSource.operation,'delete');
 assert.equal(JSON.parse(beforeCreate.messages[1].content).state.missingSource.path,'new.js');
 assert.deepEqual(JSON.parse(beforeCreate.messages[1].content).state.availableEditOperations,['create']);
 assert.equal(beforeCreate.state.workIntent.schema.oneOf.find(x=>x.properties?.capability?.const==='worktree_edit').properties.arguments.oneOf.length,1);
 assert.ok(beforeCreate.messages[0].content.includes('use operation=create for a new file'));
 assert.equal(out.result.state.missingSource,null);
});
test('a model that ignores the narrowed edit surface cannot repeat a missing-source mutation',async()=>{
 const missing=intent('worktree_edit',{operation:'delete',path:'new.js'});
 const out=await run([missing,missing,missing],{invoke:()=>workCapabilityRefusal('worktree_edit',{reason:'EDIT_SOURCE_MISSING'})});
 assert.equal(out.calls.length,1);
 assert.equal(out.result.reason,'REPEATED_INVALID_PROPOSAL');
 assert.equal(out.events.filter(x=>x.kind==='EDIT').length,1);
});
test('bounded unified diff survives semantic transport and task binding exactly',()=>{
 const patch='--- a/a.js\n+++ b/a.js\n@@ -1 +1 @@\n-old\n+new\n--- /dev/null\n+++ b/new.js\n@@ -0,0 +1 @@\n+added\n';
 const checked=validateWorkIntent(intent('worktree_patch',{patch}),options);assert.equal(checked.ok,true);
 const proposal=bindWorkIntent(checked,{scope,proposalId:'p',requestId:'r',turn:0,reasoner:'PRIVATE_LEAD',specDigests:{worktree_patch:manifest.byName.worktree_patch.digest}});
 const validation=prepare('worktree_patch',proposal.arguments,compile(workModeTools));assert.equal(validation.ok,true);
 assert.deepEqual(normalizeWorkspacePacket('worktree_patch',validation.params),{task_id:scope,patch});
 assert.equal(validateWorkIntent(intent('worktree_patch',{patch:''}),options).ok,false);
 assert.equal(validateWorkIntent(intent('worktree_patch',{patch:'x'.repeat(48001)}),options).ok,false);
});
test('semantic transport, binding, reliability and signed packet preserve exact strings',()=>{
 const args={operation:'replace',path:'a.js',old_text:' \t{ "雪": "\\n" }\r\n\n',new_text:'\n\t  {"quote":"\\\""}\r\n '};
 const wire=JSON.parse(JSON.stringify(intent('worktree_edit',args)));
 const adapter=validateReasonerResult(wire,{supportsWorkIntents:true});assert.equal(adapter.ok,true);
 const checked=validateWorkIntent(adapter.value,options);assert.equal(checked.ok,true);
 const proposal=bindWorkIntent(checked,{scope,proposalId:'p',requestId:'r',turn:0,reasoner:'PRIVATE_LEAD',specDigests:{worktree_edit:manifest.byName.worktree_edit.digest}});
 const validation=prepare('worktree_edit',proposal.arguments,compile(workModeTools));assert.equal(validation.ok,true);assert.deepEqual(validation.rules,[]);
 const packet=normalizeWorkspacePacket('worktree_edit',validation.params);const {operation,...exactArgs}=args;assert.equal(operation,'replace');assert.deepEqual(packet,{task_id:scope,...exactArgs});
 for(const old_text of ['',null,42])assert.equal(validateWorkIntent(intent('worktree_edit',{...args,old_text}),options).ok,false);
 assert.equal(validateWorkIntent(intent('worktree_edit',{...args,new_text:''}),options).ok,true);
 assert.equal(validateWorkIntent(intent('worktree_edit',{...args,edits:[]}),options).ok,false);
});
test('bounded create delete and move intents preserve only repository-relative inputs',()=>{
 for(const args of [
  {operation:'create',path:'src/new.js',new_text:'export const value = 1;\n'},
  {operation:'delete',path:'src/old.js'},
  {operation:'move',path:'src/old.js',destination:'test/old.test.js'},
 ]){
  const checked=validateWorkIntent(intent('worktree_edit',args),options);assert.equal(checked.ok,true);
  const proposal=bindWorkIntent(checked,{scope,proposalId:'p',requestId:'r',turn:0,reasoner:'PRIVATE_LEAD',specDigests:{worktree_edit:manifest.byName.worktree_edit.digest}});
  const validation=prepare('worktree_edit',proposal.arguments,compile(workModeTools));assert.equal(validation.ok,true);
  assert.deepEqual(normalizeWorkspacePacket('worktree_edit',validation.params),{task_id:scope,...args});
 }
 for(const bad of [
  {operation:'create',path:'../new.js',new_text:'x'},
  {operation:'move',path:'/old.js',destination:'new.js'},
  {operation:'move',path:'old.js',destination:'../new.js'},
 ])assert.equal(validateWorkIntent(intent('worktree_edit',bad),options).ok,false);
});
test('semantic mismatches hide editing until successful same-path read, not list or another file',async()=>{
 let edits=0;
 const rows=[edit,intent('worktree_list',{}),intent('worktree_read',{path:'b.js'}),read,edit];
 const out=await run(rows,{observeRead:async()=>true,invoke:p=>p.capability==='worktree_edit'?++edits===1?{ok:false,error:{code:'EDIT_TARGET_NOT_FOUND'},executionState:'NOT_STARTED'}:{ok:true,executionState:'COMPLETED'}:{ok:true,executionState:'COMPLETED',data:{text:'old'}}});
 for(let i=1;i<=3;i++)assert.ok(!JSON.stringify(out.requests[i].state.workIntent).includes('worktree_edit'));
 assert.ok(JSON.stringify(out.requests[4].state.workIntent).includes('worktree_edit'));
 assert.equal(out.events.filter(x=>x.kind==='EDIT_RECOVERY').length,1);assert.equal(edits,2);
});
test('blind retries never execute and terminate through existing correction bound',async()=>{
 const out=await run([edit,edit,edit],{invoke:()=>({ok:false,error:{code:'EDIT_SOURCE_STALE'},executionState:'NOT_STARTED'})});
 assert.equal(out.calls.length,1);assert.equal(out.result.reason,'REPEATED_INVALID_PROPOSAL');
});
test('withheld and omitted read results never create observations or clear recovery',async()=>{
 for(const mode of ['withheld','omitted']){
  let commits=0;
  const out=await run([edit,read],{observeRead:async()=>{commits++;return true;},egressOverride:mode==='withheld'?()=>({}):undefined,invoke:p=>p.capability==='worktree_edit'?{ok:false,error:{code:'EDIT_SOURCE_NOT_OBSERVED'},executionState:'NOT_STARTED'}:{ok:true,executionState:'COMPLETED',data:{text:'x'.repeat(20000)}}});
  assert.equal(commits,0);assert.equal(out.result.state.editRecovery.path,'a.js');
 }
});
test('successful mutation requires tests even when result egress is withheld',async()=>{
 const out=await run([edit],{egressOverride:()=>({})});assert.equal(out.result.state.tests.required,true);assert.equal(out.result.state.workspaceGeneration,1);assert.deepEqual(out.result.state.readRequired,['a.js']);
});
test('file operation completion tracks only paths that can be observed afterward',async()=>{
 for(const [args,required] of [
  [{operation:'create',path:'new.js',new_text:'x'},['new.js']],
  [{operation:'delete',path:'old.js'},[]],
  [{operation:'move',path:'old.js',destination:'new.js'},['new.js']],
 ]){
  const out=await run([intent('worktree_edit',args)],{egressOverride:()=>({})});
  assert.equal(out.result.state.tests.required,true);assert.deepEqual(out.result.state.readRequired,required);
 }
});

test('replacement discriminator is model-only and legacy model shape is refused',async()=>{
 const legacy={path:'a.js',old_text:'old',new_text:'new'};
 assert.equal(validateWorkIntent(intent('worktree_edit',legacy),options).ok,false);
 const out=await run([edit]);
 assert.deepEqual(out.calls[0].arguments,{task_id:scope,...legacy});
 const context=JSON.parse(out.requests[0].messages[1].content);
 assert.match(context.capabilities.find(x=>x.name==='worktree_edit').description,/operation:replace/);
 assert.ok(!context.capabilities.find(x=>x.name==='worktree_edit').description.includes('no operation'));
 assert.deepEqual(JSON.parse(out.requests[1].messages[1].content).state.observations[0].result.action,{operation:'replace',path:'a.js'});
});

test('existing-destination recovery requires disclosed same-path read and permits exact replace',async()=>{
 const create=intent('worktree_edit',{operation:'create',path:'a.js',new_text:'new'});
 const out=await run([create,intent('worktree_list',{}),intent('worktree_read',{path:'b.js'}),read,edit],{observeRead:async()=>true,invoke:p=>p.arguments.operation==='create'?{ok:false,error:{code:'EDIT_DESTINATION_EXISTS'},executionState:'NOT_STARTED'}:{ok:true,executionState:'COMPLETED',data:{text:'old'}}});
 for(const index of [1,2,3])assert.ok(!out.requests[index].state.workIntent.schema.oneOf.some(x=>x.properties.capability?.const==='worktree_edit'));
 assert.ok(out.requests[4].state.workIntent.schema.oneOf.some(x=>x.properties.capability?.const==='worktree_edit'));
 assert.equal(out.calls.filter(x=>x.arguments.operation==='create').length,1);
 assert.deepEqual(out.calls.at(-1).arguments,{task_id:scope,path:'a.js',old_text:'old',new_text:'new'});
 const feedback=JSON.parse(out.requests[1].messages[1].content).state;
 assert.deepEqual(feedback.observations[0].result.action,{operation:'create',path:'a.js'});
 assert.equal(feedback.editRecovery.requiredAction,'worktree_read');
 assert.ok(!JSON.stringify(feedback.observations[0].result).includes('new_text'));
 const blind=await run([create,create,create],{invoke:()=>({ok:false,error:{code:'EDIT_DESTINATION_EXISTS'},executionState:'NOT_STARTED'})});
 assert.equal(blind.calls.length,1);assert.equal(blind.result.reason,'REPEATED_INVALID_PROPOSAL');
});

test('action context is bound by egress and withheld results cannot disclose it or create collision recovery',async()=>{
 const create=intent('worktree_edit',{operation:'create',path:'relative.txt',new_text:'UNRETURNED_CONTENT'});
 let packet;
 const out=await run([create],{invoke:()=>({ok:false,error:{code:'EDIT_DESTINATION_EXISTS'},executionState:'NOT_STARTED'}),egressOverride:({claim,envelope})=>{packet=envelope;assert.equal(claim.packetDigest,digest(envelope));return {};}});
 assert.deepEqual(packet.action,{operation:'create',path:'relative.txt'});
 assert.ok(!JSON.stringify(packet).includes('UNRETURNED_CONTENT'));
 const next=JSON.parse(out.requests[1].messages[1].content).state;
 assert.equal(next.editRecovery,null);
 assert.ok(!JSON.stringify(next.observations).includes('relative.txt'));
});

test('small edit budgets apply before authority while preserving the underlying tool contract',async()=>{
 const original=manifest.byName.worktree_edit.arguments.properties;
 assert.equal(original.old_text.maxLength,4096);assert.equal(original.new_text.maxLength,8192);
 const shape=workIntentSchema([manifest.byName.worktree_edit],options).oneOf[0].properties.arguments.oneOf[0].properties;
 assert.equal(shape.old_text.maxLength,512);assert.equal(shape.new_text.maxLength,2048);
 for(const [field,length] of [['old_text',512],['new_text',2048]]){
  const args={operation:'replace',path:'a.js',old_text:'old',new_text:'new',[field]:'x'.repeat(length)};
  assert.equal(validateWorkIntent(intent('worktree_edit',args),options).ok,true);
  args[field]+='x';assert.equal(validateWorkIntent(intent('worktree_edit',args),options).ok,false);
  const out=await run([intent('worktree_edit',args),{kind:'ESCALATION',reason:'SMALLER_EDIT_REQUIRED'}]);assert.equal(out.calls.length,0);
  assert.equal(JSON.parse(out.requests[0].messages[1].content).state.resultRequirements.worktree_edit[field],length);
 }
 assert.equal(validateWorkIntent(intent('worktree_edit',{operation:'create',path:'new.js',new_text:'x'.repeat(2049)}),options).ok,false);
 const generated=workIntentRequest([manifest.byName.worktree_edit],options).schema.oneOf[0].properties.arguments.oneOf[0].properties;
 assert.equal(generated.old_text.maxLength,undefined); // Pinned decoder cannot enforce escaped string lengths.
 assert.equal(validateWorkIntent(intent('worktree_edit',{operation:'create',path:'new.js',new_text:'😀'.repeat(1024)}),options).ok,true);
 assert.equal(validateWorkIntent(intent('worktree_edit',{operation:'create',path:'new.js',new_text:'😀'.repeat(1025)}),options).ok,false);
});

test('oversized edit gets one field-specific correction and only the corrected edit executes',async()=>{
 for(const [field,length,limit] of [['old_text',1636,512],['old_text',1724,512],['new_text',3000,2048]]){
  const marker='REJECTED_PRIVATE_SOURCE_',bad=structuredClone(edit);bad.arguments[field]=marker.padEnd(length,'x');
  let source='old';
  const out=await run([read,bad,edit,intent('worktree_command',{operation:'test'})],{invoke:p=>{
   if(p.capability==='worktree_read')return {ok:true,executionState:'COMPLETED',verifier:'VERIFIED',data:{text:source}};
   if(p.capability==='worktree_edit'){assert.equal(p.arguments.old_text,source);source=p.arguments.new_text;}
   if(p.capability==='worktree_command')assert.equal(source,'new');
   return {ok:true,executionState:'COMPLETED',verifier:'VERIFIED'};
  }});
  const correction=JSON.parse(out.requests[2].messages[1].content).state.correction;
  assert.equal(correction.field,field);assert.equal(correction.keyword,'maxLength');assert.equal(correction.lengthLimit,limit);
  assert.equal(correction.diagnostic.field,field);assert.equal(correction.diagnostic.stringLength,length);
  assert.equal(correction.recovery.field,field);assert.equal(correction.recovery.maxLength,limit);
  assert.equal(correction.recovery.unit,'UTF-16 code units');assert.match(correction.recovery.guidance,/short exact unique/);
  assert.equal(correction.attempt,1);assert.equal(correction.correctionsRemaining,1);
  assert.ok(!JSON.stringify(out.requests).includes(marker));assert.ok(!JSON.stringify(out.events).includes(marker));
  assert.equal(out.calls.filter(p=>p.capability==='worktree_edit').length,1);assert.equal(source,'new');
  assert.equal(out.result.metrics.modelCalls,4);assert.equal(out.result.status,'COMPLETE');
  const rejected=out.events.find(e=>e.kind==='PROPOSAL'&&e.outcome==='REJECTED');
  assert.equal(rejected.field,field);assert.equal(rejected.keyword,'maxLength');assert.equal(rejected.lengthLimit,limit);
 }
});

test('repeated oversized edits still stop before authority or execution',async()=>{
 const bad=structuredClone(edit);bad.arguments.old_text='x'.repeat(1636);
 const out=await run([bad,bad]);
 assert.equal(out.result.reason,'REPEATED_INVALID_PROPOSAL');assert.equal(out.result.metrics.modelCalls,2);
 assert.equal(out.calls.length,0);assert.equal(out.events.filter(e=>e.kind==='AUTHORITY').length,0);
});
