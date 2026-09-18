import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {workModeTools} from '../plugin/workspace-tools.mjs';
import {deriveCapabilityManifest} from '../foundation/manifest.mjs';
import {bindWorkIntent,validateWorkIntent,workIntentRequest} from '../foundation/work-intent.mjs';
import {CONTRACT_VERSION,digest,validateReasonerResult} from '../foundation/contracts.mjs';
import {createWorkMode,MUTABLE_WORKTREE_COMPLETION_POLICY,WORKSPACE_EVIDENCE_VERSION} from '../plugin/work-mode.mjs';
import {normalizeWorkspacePacket} from '../plugin/work-command.mjs';
import {compile,prepare} from '../../reliability/runtime.mjs';
import {syntheticProtection} from './fixtures/task-evidence.mjs';
const names=workModeTools.map(x=>x.name),manifest=deriveCapabilityManifest({schemas:workModeTools,registeredTools:names,declaredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
const specs=manifest.capabilities,scope='a'.repeat(32),options={specs,terminalKinds:['ESCALATION']};
const intent=(capability,args)=>({kind:'TOOL_PROPOSAL',capability,arguments:args});
const edit=intent('worktree_edit',{path:'a.js',old_text:'old',new_text:'new'}),read=intent('worktree_read',{path:'a.js'});
const allow=(proposal,spec,scope)=>({schema:CONTRACT_VERSION,outcome:'ALLOW',capability:proposal.capability,proposalDigest:digest(proposal),scope,effect:spec.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false});
const egress=({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']});
function run(rows,{invoke,observeRead,egressOverride}={}){
 const requests=[],events=[],calls=[];let i=0;
 const work=createWorkMode({manifest,reasoner:{async invoke(request){requests.push(request);return rows[i++]??{kind:'ESCALATION',reason:'DONE'};}},authorize:allow,egress:egressOverride??egress,observeRead,verifyProtectedEvidence:syntheticProtection,completionPolicy:MUTABLE_WORKTREE_COMPLETION_POLICY,workspaceState:async({scope,workspace,turn})=>({schema:WORKSPACE_EVIDENCE_VERSION,scope,workspace,turn,diff:{ok:true,executionState:'COMPLETED',digest:'a'.repeat(64),bytes:1},status:{ok:true,executionState:'COMPLETED',digest:'b'.repeat(64),bytes:1}}),invoke:async({proposal})=>{calls.push(proposal);return invoke?invoke(proposal):{ok:true,executionState:'COMPLETED',data:{text:'old'}};},evaluate:async()=>({passed:true}),onEvent:(kind,value)=>events.push({kind,...value})});
 return work.run({task:'synthetic',scope,capabilities:names.filter(x=>x!=='source_first_research')}).then(result=>({result,requests,events,calls}));
}
test('normal registered and generation surfaces require no raw patches or whole-file fallback',()=>{
 assert.ok(names.includes('worktree_edit'));for(const name of ['worktree_patch','worktree_create','worktree_delete','worktree_replace_file'])assert.ok(!names.includes(name));
 const request=workIntentRequest(specs,{terminalKinds:['ESCALATION']});assert.ok(!JSON.stringify(request).includes('worktree_patch'));
 assert.equal(validateWorkIntent(intent('worktree_patch',{patch:'diff'}),options).ok,false);
 assert.equal(manifest.byName.worktree_edit.policy.effect,'MUTATION');assert.deepEqual(manifest.byName.worktree_edit.policy.repairRules,[]);
});
test('semantic transport, binding, reliability and signed packet preserve exact strings',()=>{
 const args={path:'a.js',old_text:' \t{ "雪": "\\n" }\r\n\n',new_text:'\n\t  {"quote":"\\\""}\r\n '};
 const wire=JSON.parse(JSON.stringify(intent('worktree_edit',args)));
 const adapter=validateReasonerResult(wire,{supportsWorkIntents:true});assert.equal(adapter.ok,true);
 const checked=validateWorkIntent(adapter.value,options);assert.equal(checked.ok,true);
 const proposal=bindWorkIntent(checked,{scope,proposalId:'p',requestId:'r',turn:0,reasoner:'PRIVATE_LEAD',specDigests:{worktree_edit:manifest.byName.worktree_edit.digest}});
 const validation=prepare('worktree_edit',proposal.arguments,compile(workModeTools));assert.equal(validation.ok,true);assert.deepEqual(validation.rules,[]);
 const packet=normalizeWorkspacePacket('worktree_edit',validation.params);assert.deepEqual(packet,{task_id:scope,...args});
 for(const old_text of ['',null,42])assert.equal(validateWorkIntent(intent('worktree_edit',{...args,old_text}),options).ok,false);
 assert.equal(validateWorkIntent(intent('worktree_edit',{...args,new_text:''}),options).ok,true);
 assert.equal(validateWorkIntent(intent('worktree_edit',{...args,edits:[]}),options).ok,false);
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
