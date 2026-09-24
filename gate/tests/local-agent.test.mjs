import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import { buildLocalRequest,createLocalAgent,createLocalReasonerAdapter,LOCAL_AGENT_TIMEOUT_MS } from '../plugin/local-agent.mjs';
import {beginLocalToolRun,endLocalToolRun,localToolFamily,localToolGuard,localToolSurface,observeLocalTool} from '../plugin/local-tool-boundary.mjs';
const model='local4b';
const answerTokens=JSON.parse(readFileSync(new URL('../SETTINGS.json',import.meta.url),'utf8')).max_answer_tokens;
const config={agents:{ownership:'explicit',defaults:{model:{primary:'mlx-local/'+model},systemAgent:{agentId:'main'}},entries:{main:{thinkingDefault:'off',params:{chat_template_kwargs:{enable_thinking:false}}},'workmode-broker':{}}},models:{providers:{'mlx-local':{baseUrl:'http://127.0.0.1:8080/v1',models:[{id:model,contextWindow:24576,maxTokens:4096}]}}},gateway:{bind:'loopback',port:18789,auth:{mode:'token',token:'synthetic-only'},http:{endpoints:{chatCompletions:{enabled:true}}}}};
const body={operation:'answer_local',approval:'local_only',request:{scope:'a'.repeat(32),revision:2,messages:[{role:'assistant',content:'synthetic previous answer'},{role:'user',content:'Answer a synthetic local question.'}]},state:{scope:'a'.repeat(32),revision:2,privacy_floor:'PERSONAL',high_stakes:false}};
const response=text=>new Response(JSON.stringify({choices:[{finish_reason:'stop',message:{role:'assistant',content:text}}]}));
test('handoff pins local model and supplies no new tools or system permissions',()=>{
 const r=buildLocalRequest(body,config,model,answerTokens);
 assert.equal(r.url,'http://127.0.0.1:18789/v1/chat/completions');assert.equal(r.headers['x-openclaw-model'],'mlx-local/'+model);
 assert.equal(r.headers['x-openclaw-agent-id'],'main');assert.equal(r.payload.model,'openclaw/main');
 assert.deepEqual(r.payload.messages,[body.request.messages.at(-1)]);assert.equal(r.payload.tools,undefined);assert.equal(r.payload.messages.some(x=>x.role==='system'),false);
 assert.equal(r.payload.max_completion_tokens,undefined);
});
test('scope isolates local sessions and revisions retain task context',()=>{
 const a=buildLocalRequest(body,config,model,answerTokens).headers['x-openclaw-session-key'];
 const next=structuredClone(body);next.request.revision=3;next.state.revision=3;
 assert.equal(buildLocalRequest(next,config,model,answerTokens).headers['x-openclaw-session-key'],a);
 next.request.scope=next.state.scope='b'.repeat(32);assert.notEqual(buildLocalRequest(next,config,model,answerTokens).headers['x-openclaw-session-key'],a);
});
test('explicit personal source requests narrow both submitted and executable tools',()=>{
 const expected=[['What is my most recent email?','gmail','gmail_search','messages_search'],['Show my latest text','messages','messages_search','gmail_search'],['Check my calendar today','calendar','calendar_events','gmail_search']];
 for(const [prompt,family,allowed,denied] of expected){
  assert.equal(localToolFamily(prompt),family);
  const sample=structuredClone(body);sample.request.messages.at(-1).content=prompt;
  const sessionKey=buildLocalRequest(sample,config,model,answerTokens).headers['x-openclaw-session-key'];
  assert.match(sessionKey,new RegExp(`mac-gate-local-${family}-`));
  assert.ok(localToolSurface(null,{sessionKey}).toolsAllow.includes(allowed));
  assert.equal(localToolGuard({toolName:allowed},{sessionKey}),undefined);
  assert.equal(localToolGuard({toolName:denied},{sessionKey}).block,true);
 }
 assert.equal(localToolFamily('How do I use Gmail?'),null);
 assert.equal(localToolFamily('What is my latest email and text message?'),'mixed');
 assert.equal(localToolFamily('Read the text of my latest email'),'gmail');
 const evidence=structuredClone(body);evidence.request.messages.at(-1).content+='\nSOURCE-FIRST EVIDENCE';
 const key=buildLocalRequest(evidence,config,model,answerTokens).headers['x-openclaw-session-key'];
 assert.deepEqual(localToolSurface(null,{sessionKey:key}),{toolsAllow:[]});
 assert.equal(localToolGuard({toolName:'web_search'},{sessionKey:key}).block,true);
});
test('personal-source answer is suppressed unless its requested tool succeeds',async()=>{
 const mail=structuredClone(body);mail.request.messages.at(-1).content='What is my most recent email?';
 const failed=createLocalAgent({getConfig:()=>config,localModel:model,maxAnswerTokens:answerTokens,fetchImpl:async(_url,{headers})=>{
  observeLocalTool({toolName:'gmail_search',error:'synthetic broker failure'},{sessionKey:headers['x-openclaw-session-key']});
  return response('A misleading answer about a text message.');
 }});
 assert.deepEqual(await failed(mail,new AbortController().signal),{status:'UNAVAILABLE',reason:'local_source_unavailable'});
 const succeeded=createLocalAgent({getConfig:()=>config,localModel:model,maxAnswerTokens:answerTokens,fetchImpl:async(_url,{headers})=>{
  observeLocalTool({toolName:'gmail_search',result:{isError:false}},{sessionKey:headers['x-openclaw-session-key']});
  return response('Synthetic email result.');
 }});
 assert.deepEqual(await succeeded(mail,new AbortController().signal),{status:'OK',text:'Synthetic email result.'});
 const key=buildLocalRequest(mail,config,model,answerTokens).headers['x-openclaw-session-key'];
 beginLocalToolRun(key);assert.equal(endLocalToolRun(key),false);
});
test('non-normal or stale state cannot dispatch',()=>{
 for(const patch of [{high_stakes:true},{privacy_floor:'RESTRICTED'},{revision:1},{scope:'b'.repeat(32)}]){
  assert.throws(()=>buildLocalRequest({...body,state:{...body.state,...patch}},config,model,answerTokens));
 }
 for(const operation of ['classify','answer_frontier'])assert.throws(()=>buildLocalRequest({...body,operation},config,model,answerTokens));
});
test('remote default or fallback or provider drift refuses handoff',()=>{
 for(const change of [c=>{c.agents.defaults.model.primary='openrouter/remote';},c=>{c.agents.defaults.model.fallbacks=['openrouter/remote'];},c=>{c.models.providers['mlx-local'].baseUrl='https://example.invalid/v1';},c=>{c.models.providers['mlx-local'].models[0].contextWindow=16384;},c=>{c.models.providers['mlx-local'].models[0].maxTokens=1;},c=>{c.models.providers['mlx-local'].models=[];},c=>{c.agents.list=[{id:'main',model:'remote'}];}]){
  const c=structuredClone(config);change(c);assert.throws(()=>buildLocalRequest(body,c,model,answerTokens));
 }
});
test('local answer requires the reviewed non-thinking MLX budget',()=>{
 for(const change of [c=>{c.agents.entries.main.thinkingDefault='medium';},c=>{c.agents.entries.main.params.chat_template_kwargs.enable_thinking=true;},c=>{delete c.agents.entries.main.params.chat_template_kwargs;}]){
  const c=structuredClone(config);change(c);assert.throws(()=>buildLocalRequest(body,c,model,answerTokens),/unreviewed_local_answer_budget/);
 }
});
test('changed gateway authentication or public listener refuses handoff',()=>{
 for(const change of [c=>{c.gateway.bind='lan';},c=>{c.gateway.auth.mode='none';},c=>{c.gateway.http.endpoints.chatCompletions.enabled=false;}]){
  const c=structuredClone(config);change(c);assert.throws(()=>buildLocalRequest(body,c,model,answerTokens));
 }
});
test('local answer token limit is pinned per provider turn and omitted from the outer agent request',()=>{
 for(const limit of [undefined,0,1.5,4097])assert.throws(()=>buildLocalRequest(body,config,model,limit),/invalid_answer_token_limit/);
 const changed=structuredClone(config);changed.models.providers['mlx-local'].models[0].maxTokens=1;
 assert.equal(buildLocalRequest(body,changed,model,1).payload.max_completion_tokens,undefined);
});
test('successful local agent answer uses one local request only',async()=>{
 const calls=[];const run=createLocalAgent({getConfig:()=>config,localModel:model,maxAnswerTokens:answerTokens,fetchImpl:async(...args)=>{calls.push(args);return response('Synthetic result');}});
 assert.deepEqual(await run(body,new AbortController().signal),{status:'OK',text:'Synthetic result'});assert.equal(calls.length,1);assert.equal(calls[0][1].redirect,'manual');
 assert.equal(JSON.parse(calls[0][1].body).max_completion_tokens,undefined);
});
test('model-independent adapter preserves the existing local execution boundary',async()=>{
 let calls=0;const adapter=createLocalReasonerAdapter({getConfig:()=>config,localModel:model,maxAnswerTokens:answerTokens,fetchImpl:async()=>{calls++;return response('Adapter result');}});
 const request={schema:'sanctum-capability/v1',requestId:'request-1',scope:body.request.scope,revision:body.request.revision,messages:[body.request.messages.at(-1)],manifestDigest:'a'.repeat(64),state:body.state};
 assert.deepEqual(await adapter.invoke(request,new AbortController().signal),{kind:'FINAL',text:'Adapter result'});assert.equal(calls,1);
});
test('failures and redirects have no retry or remote fallback',async()=>{
 for(const status of [302,500]){
  let calls=0;const run=createLocalAgent({getConfig:()=>config,localModel:model,maxAnswerTokens:answerTokens,fetchImpl:async()=>{calls++;return new Response('',{status});}});
  assert.equal((await run(body,new AbortController().signal)).status,'UNAVAILABLE');assert.equal(calls,1);
 }
});
test('aborted request does not start agent',async()=>{
 const abort=new AbortController();abort.abort();let calls=0;const run=createLocalAgent({getConfig:()=>config,localModel:model,maxAnswerTokens:answerTokens,fetchImpl:async()=>{calls++;return response('bad');}});
 assert.equal((await run(body,abort.signal)).status,'UNAVAILABLE');assert.equal(calls,0);
});
test('deadline cancels native request without retry',async()=>{
 let aborted=false;const run=createLocalAgent({getConfig:()=>config,localModel:model,maxAnswerTokens:answerTokens,timeoutMs:10,fetchImpl:(_url,{signal})=>new Promise((_,reject)=>signal.addEventListener('abort',()=>{aborted=true;reject(Error());}))});
 assert.equal((await run(body,new AbortController().signal)).status,'UNAVAILABLE');assert.equal(aborted,true);
});
test('default local deadline leaves bounded headroom for slow Mac prefill',()=>{
 assert.equal(LOCAL_AGENT_TIMEOUT_MS,240000);
});
test('UTF-8 split across chunks survives intact',async()=>{
 const data=Buffer.from(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'Grüße'}}]}));const i=data.indexOf(Buffer.from('ü'))+1;
 const run=createLocalAgent({getConfig:()=>config,localModel:model,maxAnswerTokens:answerTokens,fetchImpl:async()=>new Response(new ReadableStream({start(c){c.enqueue(data.subarray(0,i));c.enqueue(data.subarray(i));c.close();}}))});
 assert.equal((await run(body,new AbortController().signal)).text,'Grüße');
});
