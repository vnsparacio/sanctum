import { createHash } from 'node:crypto';
import {createReasonerAdapter} from '../foundation/contracts.mjs';

export function buildLocalRequest(body, config, localModel) {
  if(body.operation!=='answer_local' || body.approval!=='local_only')throw Error('wrong_operation');
  const req=body.request, state=body.state;
  const port=Number(process.env.VINCEAI_GATEWAY_PORT ?? 18789);
  const mlxPort=Number(process.env.VINCEAI_MLX_PORT ?? 8080);
  if (![port,mlxPort].every(p=>Number.isInteger(p)&&p>=1024&&p<=65535)) throw Error('invalid_port');
  if(!req || !/^[a-f0-9]{32}$/.test(req.scope) || state?.scope!==req.scope
     || state.high_stakes!==false || state.privacy_floor!=='PERSONAL'
     || state.revision!==req.revision)throw Error('invalid_local_state');
  const latest=req.messages?.at(-1);
  if(latest?.role!=='user' || typeof latest.content!=='string' || !latest.content.trim())throw Error('missing_user_request');
  const expected='mlx-local/'+localModel;
  const model=config.agents?.defaults?.model;
  const primary=typeof model==='string'?model:model?.primary;
  if(primary!==expected || (model?.fallbacks?.length??0)!==0 || (config.agents?.list?.length??0)!==0)throw Error('unreviewed_agent_model');
  const provider=config.models?.providers?.['mlx-local'];
  if(provider?.baseUrl!==`http://127.0.0.1:${mlxPort}/v1`)throw Error('local_provider_changed');
  const gateway=config.gateway;
  if(gateway?.bind!=='loopback' || gateway.port!==port || gateway.auth?.mode!=='token'
      || typeof gateway.auth.token!=='string' || !gateway.auth.token
      || gateway.http?.endpoints?.chatCompletions?.enabled!==true)throw Error('gateway_contract_changed');
  // A gate scope gets its own ordinary-agent session. Tool history stays here on
  // the Mac. Send only the new user message; OpenClaw supplies its agent context.
  const sessionKey='agent:main:mac-gate-local-'+createHash('sha256').update(req.scope).digest('hex');
  return {url:`http://127.0.0.1:${port}/v1/chat/completions`,
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+gateway.auth.token,
      'x-openclaw-agent-id':'main','x-openclaw-model':expected,
      'x-openclaw-session-key':sessionKey},
    payload:{model:'openclaw/main',messages:[{role:'user',content:latest.content}],
      stream:false,max_completion_tokens:1024}};
}

export function createLocalAgent({getConfig,localModel,fetchImpl=fetch,timeoutMs=120000}) {
  return async(body,signal)=>{
    let abort, timer;
    const controller=new AbortController();
    try {
      if(signal.aborted)return {status:'UNAVAILABLE'};
      const request=buildLocalRequest(body,getConfig(),localModel);
      abort=()=>controller.abort();signal.addEventListener('abort',abort,{once:true});
      timer=setTimeout(abort,timeoutMs);
      const response=await fetchImpl(request.url,{method:'POST',headers:request.headers,
        body:JSON.stringify(request.payload),redirect:'manual',signal:controller.signal});
      if(!response.ok || !response.body)throw Error('agent_unavailable');
      const chunks=[];let size=0;
      for await(const part of response.body){size+=part.length;if(size>100000){controller.abort();throw Error('response_limit');}chunks.push(Buffer.from(part));}
      const data=JSON.parse(Buffer.concat(chunks).toString('utf8')), choices=data.choices;
      if(data.error || !Array.isArray(choices) || choices.length!==1
        || choices[0].finish_reason!=='stop' || choices[0].message?.tool_calls)throw Error('unfinished_agent_turn');
      const text=choices[0].message?.content;
      if(typeof text!=='string' || !text.trim() || Buffer.byteLength(text)>32768 || controller.signal.aborted)throw Error('invalid_answer');
      return {status:'OK',text};
    }catch{return {status:'UNAVAILABLE'};}
    finally{clearTimeout(timer);if(abort)signal.removeEventListener('abort',abort);}
  };
}

// This is intentionally a final-answer adapter only. The existing OpenClaw
// agent loop still owns local tools and their Mac-side hooks; this wrapper does
// not grant a second tool path or alter the request sent by createLocalAgent.
export function createLocalReasonerAdapter(options){
 const agent=createLocalAgent(options);
 return createReasonerAdapter({id:'LOCAL_4B',kind:'OPENCLAW_LOCAL_AGENT',supportsToolProposals:false,invoke:async(request,signal)=>{
   const latest=request.messages?.at(-1);
   const body={operation:'answer_local',approval:'local_only',request:{scope:request.scope,revision:request.revision,messages:[latest],operation_revision:''},state:request.state};
   const result=await agent(body,signal);
   return result.status==='OK'?{kind:'FINAL',text:result.text}:{kind:'ESCALATION',reason:'REASONER_UNAVAILABLE'};
 }});
}
