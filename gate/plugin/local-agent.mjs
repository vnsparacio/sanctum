import {createReasonerAdapter} from '../foundation/contracts.mjs';
import {beginLocalToolRun,endLocalToolRun,localSessionKey,localToolFamily} from './local-tool-boundary.mjs';

export function buildLocalRequest(body, config, localModel, maxAnswerTokens) {
  if(body.operation!=='answer_local' || body.approval!=='local_only')throw Error('wrong_operation');
  if(!Number.isInteger(maxAnswerTokens) || maxAnswerTokens<1 || maxAnswerTokens>4096)throw Error('invalid_answer_token_limit');
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
  const main=config.agents?.entries?.main;
  if(main?.thinkingDefault!=='off'
      || main?.params?.chat_template_kwargs?.enable_thinking!==false)throw Error('unreviewed_local_answer_budget');
  const provider=config.models?.providers?.['mlx-local'];
  const providerModel=provider?.models?.find(item=>item?.id===localModel);
  if(provider?.baseUrl!==`http://127.0.0.1:${mlxPort}/v1`
      || providerModel?.contextWindow!==24576
      || providerModel?.maxTokens!==maxAnswerTokens)throw Error('local_provider_changed');
  const gateway=config.gateway;
  if(gateway?.bind!=='loopback' || gateway.port!==port || gateway.auth?.mode!=='token'
      || typeof gateway.auth.token!=='string' || !gateway.auth.token
      || gateway.http?.endpoints?.chatCompletions?.enabled!==true)throw Error('gateway_contract_changed');
  // A gate scope gets its own ordinary-agent session. Tool history stays here on
  // the Mac. Send only the new user message; OpenClaw supplies its agent context.
  const sessionKey=localSessionKey(req.scope,localToolFamily(latest.content));
  return {url:`http://127.0.0.1:${port}/v1/chat/completions`,
    headers:{'Content-Type':'application/json','Authorization':'Bearer '+gateway.auth.token,
      'x-openclaw-agent-id':'main','x-openclaw-model':expected,
      'x-openclaw-session-key':sessionKey},
    payload:{model:'openclaw/main',messages:[{role:'user',content:latest.content}],
      stream:false}};
}

// Leave the worker and WebUI transports enough time to report this bounded
// deadline instead of racing the native request during a long local prefill.
export const LOCAL_AGENT_TIMEOUT_MS=240000;

const WEEKDAYS=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
const LABELED_DATE=new RegExp(`\\b(${WEEKDAYS.join('|')}),?\\s+(${MONTHS.join('|')})\\s+(\\d{1,2}),?\\s+(\\d{4})\\b`,'gi');

// A weekday is a deterministic property of the stated calendar date. Correct
// this narrow self-contradiction without asking a 4B model to recalculate it.
export function normalizeWeekdayLabels(text){
  return text.replace(LABELED_DATE,(match,_weekday,month,day,year)=>{
    const index=MONTHS.findIndex(x=>x.toLowerCase()===month.toLowerCase());
    const instant=new Date(Date.UTC(Number(year),index,Number(day)));
    if(instant.getUTCFullYear()!==Number(year)||instant.getUTCMonth()!==index||instant.getUTCDate()!==Number(day))return match;
    return match.replace(/^\w+/,WEEKDAYS[instant.getUTCDay()]);
  });
}

export function createLocalAgent({getConfig,localModel,maxAnswerTokens,fetchImpl=fetch,timeoutMs=LOCAL_AGENT_TIMEOUT_MS}) {
  return async(body,signal)=>{
    let abort, timer, sessionKey=null;
    const controller=new AbortController();
    try {
      if(signal.aborted)return {status:'UNAVAILABLE'};
      const request=buildLocalRequest(body,getConfig(),localModel,maxAnswerTokens);
      sessionKey=request.headers['x-openclaw-session-key'];
      beginLocalToolRun(sessionKey,request.payload.messages[0].content);
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
      if(!endLocalToolRun(sessionKey)){sessionKey=null;return {status:'UNAVAILABLE',reason:'local_source_unavailable'};}
      sessionKey=null;
      const family=localToolFamily(request.payload.messages[0].content);
      return {status:'OK',text:family&&family!=='evidence'?normalizeWeekdayLabels(text):text};
    }catch{return {status:'UNAVAILABLE'};}
    finally{if(sessionKey)endLocalToolRun(sessionKey);clearTimeout(timer);if(abort)signal.removeEventListener('abort',abort);}
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
