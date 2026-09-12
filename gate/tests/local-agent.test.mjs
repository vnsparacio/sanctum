import test from 'node:test';
import assert from 'node:assert/strict';
import { buildLocalRequest,createLocalAgent } from '../plugin/local-agent.mjs';
const model='local4b';
const config={agents:{defaults:{model:{primary:'mlx-local/'+model}}},models:{providers:{'mlx-local':{baseUrl:'http://127.0.0.1:8080/v1'}}},gateway:{bind:'loopback',port:18789,auth:{mode:'token',token:'synthetic-only'},http:{endpoints:{chatCompletions:{enabled:true}}}}};
const body={operation:'answer_local',approval:'local_only',request:{scope:'a'.repeat(32),revision:2,messages:[{role:'assistant',content:'synthetic previous answer'},{role:'user',content:'Search Gmail for a synthetic query.'}]},state:{scope:'a'.repeat(32),revision:2,privacy_floor:'PERSONAL',high_stakes:false}};
const response=text=>new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{role:'assistant',content:text}}]}));
test('handoff pins local model and supplies no new tools or system permissions',()=>{
 const r=buildLocalRequest(body,config,model);
 assert.equal(r.url,'http://127.0.0.1:18789/v1/chat/completions');assert.equal(r.headers['x-openclaw-model'],'mlx-local/'+model);
 assert.deepEqual(r.payload.messages,[body.request.messages.at(-1)]);assert.equal(r.payload.tools,undefined);assert.equal(r.payload.messages.some(x=>x.role==='system'),false);
});
test('scope isolates local sessions and revisions retain task context',()=>{
 const a=buildLocalRequest(body,config,model).headers['x-openclaw-session-key'];
 const next=structuredClone(body);next.request.revision=3;next.state.revision=3;
 assert.equal(buildLocalRequest(next,config,model).headers['x-openclaw-session-key'],a);
 next.request.scope=next.state.scope='b'.repeat(32);assert.notEqual(buildLocalRequest(next,config,model).headers['x-openclaw-session-key'],a);
});
test('non-normal or stale state cannot dispatch',()=>{
 for(const patch of [{high_stakes:true},{privacy_floor:'RESTRICTED'},{revision:1},{scope:'b'.repeat(32)}]){
  assert.throws(()=>buildLocalRequest({...body,state:{...body.state,...patch}},config,model));
 }
 for(const operation of ['classify','answer_frontier'])assert.throws(()=>buildLocalRequest({...body,operation},config,model));
});
test('remote default or fallback or provider drift refuses handoff',()=>{
 for(const change of [c=>{c.agents.defaults.model.primary='openrouter/remote';},c=>{c.agents.defaults.model.fallbacks=['openrouter/remote'];},c=>{c.models.providers['mlx-local'].baseUrl='https://example.invalid/v1';},c=>{c.agents.list=[{id:'main',model:'remote'}];}]){
  const c=structuredClone(config);change(c);assert.throws(()=>buildLocalRequest(body,c,model));
 }
});
test('changed gateway authentication or public listener refuses handoff',()=>{
 for(const change of [c=>{c.gateway.bind='lan';},c=>{c.gateway.auth.mode='none';},c=>{c.gateway.http.endpoints.chatCompletions.enabled=false;}]){
  const c=structuredClone(config);change(c);assert.throws(()=>buildLocalRequest(body,c,model));
 }
});
test('successful local agent answer uses one local request only',async()=>{
 const calls=[];const run=createLocalAgent({getConfig:()=>config,localModel:model,fetchImpl:async(...args)=>{calls.push(args);return response('Synthetic result');}});
 assert.deepEqual(await run(body,new AbortController().signal),{status:'OK',text:'Synthetic result'});assert.equal(calls.length,1);assert.equal(calls[0][1].redirect,'manual');
});
test('failures and redirects have no retry or remote fallback',async()=>{
 for(const status of [302,500]){
  let calls=0;const run=createLocalAgent({getConfig:()=>config,localModel:model,fetchImpl:async()=>{calls++;return new Response('',{status});}});
  assert.equal((await run(body,new AbortController().signal)).status,'UNAVAILABLE');assert.equal(calls,1);
 }
});
test('aborted request does not start agent',async()=>{
 const abort=new AbortController();abort.abort();let calls=0;const run=createLocalAgent({getConfig:()=>config,localModel:model,fetchImpl:async()=>{calls++;return response('bad');}});
 assert.equal((await run(body,abort.signal)).status,'UNAVAILABLE');assert.equal(calls,0);
});
test('deadline cancels native request without retry',async()=>{
 let aborted=false;const run=createLocalAgent({getConfig:()=>config,localModel:model,timeoutMs:10,fetchImpl:(_url,{signal})=>new Promise((_,reject)=>signal.addEventListener('abort',()=>{aborted=true;reject(Error());}))});
 assert.equal((await run(body,new AbortController().signal)).status,'UNAVAILABLE');assert.equal(aborted,true);
});
test('UTF-8 split across chunks survives intact',async()=>{
 const data=Buffer.from(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'Grüße'}}]}));const i=data.indexOf(Buffer.from('ü'))+1;
 const run=createLocalAgent({getConfig:()=>config,localModel:model,fetchImpl:async()=>new Response(new ReadableStream({start(c){c.enqueue(data.subarray(0,i));c.enqueue(data.subarray(i));c.close();}}))});
 assert.equal((await run(body,new AbortController().signal)).text,'Grüße');
});
