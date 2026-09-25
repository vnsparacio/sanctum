import {test} from 'node:test';
import assert from 'node:assert/strict';
import plugin from '../index.mjs';
import {currentCapabilityManifest} from '../../gate/foundation/manifest.mjs';
const hooks=new Map(),tools=[];let middleware;
plugin.register({on:(name,fn)=>hooks.set(name,fn),registerTool:t=>tools.push(t),registerAgentToolResultMiddleware:fn=>{middleware=fn;}});
test('runtime publishes one manifest and gate-local agents cannot bypass source coordination',async()=>{
 assert.equal(currentCapabilityManifest().byName.web_search.runtime.exposed,true);
 const blocked=await hooks.get('before_tool_call')({toolName:'web_search',params:{query:'synthetic'},toolCallId:'source-bypass'},{runId:'source-run',sessionKey:'agent:main:mac-gate-local-synthetic'});
 assert.equal(blocked.block,true);assert.match(blocked.blockReason,/SOURCE_COORDINATOR_REQUIRED/);
});
test('Parallel search accepts only the reviewed provider-native argument shape',async()=>{
 const hook=hooks.get('before_tool_call');
 const ctx={runId:'parallel-shape-run',sessionKey:'agent:workmode-broker:synthetic'};
 const canonical={objective:'Compare two public scholarly subjects',search_queries:['subject one subject two comparison','subject one subject two history'],count:6};
 const accepted=await hook({toolName:'web_search',params:canonical,toolCallId:'parallel-canonical'},ctx);
 assert.equal(accepted?.block,undefined);
 for(const [id,params] of [
  ['obsolete',{query:'subject one subject two',count:6}],
  ['mixed',{...canonical,query:'subject one subject two'}],
  ['missing-objective',{search_queries:canonical.search_queries,count:6}],
  ['empty-queries',{...canonical,search_queries:[]}],
  ['invalid-count',{...canonical,count:41}],
 ]){
  const decision=await hook({toolName:'web_search',params,toolCallId:`parallel-${id}`},ctx);
  assert.equal(decision?.block,true,id);
  assert.match(decision.blockReason,/INVALID_ARGUMENT/,id);
 }
});
test('installed hook repairs before execution and records explicit clamp on returned result',async()=>{
 const ctx={runId:'synthetic-run',toolCallId:'synthetic-call'};
 const decision=await hooks.get('before_tool_call')({toolName:'messages_search',params:{query:'from:Alex Example',limit:'100'},toolCallId:ctx.toolCallId},ctx);
 assert.deepEqual(decision.params,{query:'from:Alex Example',limit:12});
 const out=await middleware({toolName:'messages_search',toolCallId:ctx.toolCallId,result:{details:{ok:true,records:[{text:'fixture'}]}}},ctx);
 assert.equal(out.result.details.truncated,true);assert.equal(out.result.details.repair.attempts,1);
});
test('invalid proposal yields safe blocked result and privacy-blocked escalation',async()=>{
 const decision=await hooks.get('before_tool_call')({toolName:'messages_history',params:{},toolCallId:'failure-test'},{runId:'failure-run'});
 assert.equal(decision.block,true);const body=JSON.parse(decision.blockReason);assert.equal(body.escalation.remote_call_permitted,false);assert.equal(body.escalation.final_outcome,'PRIVACY_BLOCKED');
});
test('pure utility executes through fixed Python transport, not a model shell',async()=>{
 const t=tools.find(x=>x.name==='calc');const r=await t.execute('calc',{expression:'17.5% of 840'});assert.equal(r.details.data.value,'147');
 const err=await t.execute('calc',{expression:"__import__('os').system('id')"});assert.equal(err.details.ok,false);
});

test('real OpenClaw preparation boundary removes aliases before hook merge and final validation',async()=>{
 const {o:prepareBoundary,n:finalizeBoundary}=await import('../../node_modules/openclaw/dist/agent-tools.before-tool-call-DSAdl1_z.js');
 const t=tools.find(t=>t.name==='unit_convert');
 const ctx={runId:'boundary-run',toolCallId:'boundary-call'};
 const raw={value:'1',from:'miles',to:'kilometers'};
 const prepared=await prepareBoundary({tool:t,params:raw,toolCallId:ctx.toolCallId,ctx});
 assert.deepEqual(prepared,{value:1,from_unit:'mi',to_unit:'km'});
 const decision=await hooks.get('before_tool_call')({toolName:t.name,params:prepared,toolCallId:ctx.toolCallId},ctx);
 const merged={...prepared,...decision.params};
 const final=finalizeBoundary({tool:t,preparedParams:prepared,hookParams:prepared,adjustedParams:merged,finalizerMode:'wrapped'});
 assert.deepEqual(final,{value:1,from_unit:'mi',to_unit:'km'});
 const result=await t.execute(ctx.toolCallId,final);assert.equal(result.details.data.value,'1.609344');
 const out=await middleware({toolName:t.name,toolCallId:ctx.toolCallId,result},ctx);
 assert.equal(out.result.details.repair.attempts,1);assert.ok(out.result.details.repair.rules.includes('unit_parameter_alias'));
});

test('operator gateway merge reuses only the exact validated utility proposal',async()=>{
 const t=tools.find(t=>t.name==='unit_convert');
 const raw={value:'1',from:'miles',to:'kilometers'};
 const id='gateway-alias';
 const decision=await hooks.get('before_tool_call')({toolName:t.name,params:raw,toolCallId:id},{});
 const result=await t.execute(id,{...raw,...decision.params});
 assert.equal(result.details.data.value,'1.609344');
 const changedId='gateway-changed';
 const changed=await hooks.get('before_tool_call')({toolName:t.name,params:raw,toolCallId:changedId},{});
 const rejected=await t.execute(changedId,{...raw,...changed.params,to_unit:'GB'});
 assert.equal(rejected.details.ok,false);
 assert.equal(rejected.details.error.code,'AMBIGUOUS_ARGUMENT');
});
