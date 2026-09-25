/* Per-turn Mac gate tool boundary for explicit local personal-source requests. */
import {createHash} from 'node:crypto';

const ALLOWED=Object.freeze({
  gmail:Object.freeze(['gmail_search','gmail_read']),
  messages:Object.freeze(['messages_chats','messages_history','messages_contact_history','messages_search']),
  calendar:Object.freeze(['calendar_calendars','calendar_events','calendar_search','calendar_event']),
  evidence:Object.freeze([]),
  mixed:Object.freeze([]),
});
const ACTIVE=new Map();
const SESSION=/^agent:main:mac-gate-local-(gmail|messages|calendar|evidence|mixed)-[a-f0-9]{64}$/;
const personal=/\b(?:my|mine|me|latest|recent|last|newest|unread|received|sent|find|search|read|check|show)\b/i;

export function localToolFamily(prompt){
  if(typeof prompt!=='string')return null;
  if(prompt.includes('SOURCE-FIRST EVIDENCE'))return 'evidence';
  if(!personal.test(prompt)||/^\s*how\s+(?:do|can|should)\s+i\b/i.test(prompt))return null;
  const found=[];
  const email=/\b(?:e-?mails?|gmail|inbox)\b/i.test(prompt);
  if(email)found.push('gmail');
  if(/\b(?:iMessages?|texts|text\s+messages?|sms)\b/i.test(prompt)||(!email&&/\b(?:my|latest|recent|last|newest)\s+text\b/i.test(prompt)))found.push('messages');
  if(/\b(?:calendar|appointments?|meetings?)\b/i.test(prompt)||(!email&&found.length===0&&/\b(?:events?)\b/i.test(prompt)))found.push('calendar');
  return found.length>1?'mixed':found[0]??null;
}

export function localSessionKey(scope,family){
  const digest=createHash('sha256').update(scope).digest('hex');
  return `agent:main:mac-gate-local-${family??'general'}-${digest}`;
}

export function localToolSurface(_event,ctx){
  const family=SESSION.exec(ctx?.sessionKey??'')?.[1];
  return family?{toolsAllow:[...ALLOWED[family]]}:undefined;
}

export function localToolGuard(event,ctx){
  const family=SESSION.exec(ctx?.sessionKey??'')?.[1];
  if(!family)return;
  if(!ALLOWED[family].includes(event?.toolName))return {block:true,blockReason:'Mac gate local source boundary'};
  const state=ACTIVE.get(ctx.sessionKey);
  if(family==='calendar'&&state?.unconstrainedNext&&['calendar_events','calendar_search'].includes(event.toolName)){
    // A model-selected "today" window includes events that have already ended.
    // For an unconstrained next-event request, the Mac owns the lower bound.
    const {to:_ignored,...params}=event.params??{};
    return {params:{...params,from:new Date().toISOString(),days:90}};
  }
}

export function beginLocalToolRun(sessionKey,prompt=''){
  const family=SESSION.exec(sessionKey)?.[1];
  if(family&&family!=='evidence')ACTIVE.set(sessionKey,{family,successful:0,
    unconstrainedNext:family==='calendar'&&/\b(?:next|upcoming|soonest)\b/i.test(prompt)
      &&!/\b(?:today|tomorrow|yesterday|this\s+week|next\s+week|this\s+month|next\s+month|after|before|monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|april|may|june|july|august|september|october|november|december|\d{4}-\d{2}-\d{2})\b/i.test(prompt)});
}

export function observeLocalTool(event,ctx){
  const state=ACTIVE.get(ctx?.sessionKey);
  if(!state||!ALLOWED[state.family].includes(event?.toolName))return;
  if(!event.error&&event.result?.isError!==true)state.successful++;
}

export function endLocalToolRun(sessionKey){
  const state=ACTIVE.get(sessionKey);
  ACTIVE.delete(sessionKey);
  return !state||state.successful>0;
}
