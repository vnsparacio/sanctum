import {randomBytes} from 'node:crypto';

const TRACE=/^[a-f0-9]{32}$/;
const nonnegative=value=>Number.isSafeInteger(value)&&value>=0?value:null;
const eventId=()=>randomBytes(16).toString('hex');

function modelIdentity(settings,tier,operation){
 const role=operation==='classify'?'classification':'answer';
 if(operation==='answer_local')return {role,model:settings.local_model,revision:null,provider:'mlx-local'};
 const configured=settings.models?.[tier];
 if(configured)return {role,model:configured.id,revision:configured.canonical??null,provider:configured.provider};
 return {role:'gateway',model:'sanctum-gateway',revision:null,provider:'local'};
}

export function createContentInteractionRecorder({spool,settings,now=()=>Date.now(),monotonic=()=>performance.now(),randomId=eventId}={}){
 const enabled=spool?.enabled===true&&typeof spool.append==='function';

 function start({query,runId,sessionId}){
  if(!enabled)return null;
  return {interactionId:randomId(),query,started:monotonic(),correlation:{run_id:runId,session_id:sessionId},model:modelIdentity(settings,null,null),inputTokens:0,outputTokens:0,hasInputTokens:false,hasOutputTokens:false,terminal:null,recorded:false};
 }

 function trace(interaction,value){
  if(interaction&&!interaction.recorded&&TRACE.test(value??''))interaction.correlation.trace_id=value;
 }

 function model(interaction,{tier,operation,telemetry={}}={}){
  if(!interaction||interaction.recorded)return;
  interaction.model=modelIdentity(settings,tier,operation);
  const input=nonnegative(telemetry.prompt_tokens),output=nonnegative(telemetry.completion_tokens);
  if(input!==null){interaction.inputTokens+=input;interaction.hasInputTokens=true;}
  if(output!==null){interaction.outputTokens+=output;interaction.hasOutputTokens=true;}
 }

 function complete(interaction,{outcome,failure}){
  if(!interaction||interaction.recorded||interaction.terminal)return;
  interaction.terminal={outcome,failure};
 }

 function write(interaction,deliveredResponse){
  if(!interaction||interaction.recorded||!interaction.terminal)return false;
  interaction.recorded=true;
  const usage={latency_ms:Math.max(0,Math.round(monotonic()-interaction.started))};
  if(interaction.hasInputTokens)usage.input_tokens=interaction.inputTokens;
  if(interaction.hasOutputTokens)usage.output_tokens=interaction.outputTokens;
  const record={
   schema_version:'sanctum.ai-interaction/v1',event_id:randomId(),interaction_id:interaction.interactionId,
   timestamp:new Date(now()).toISOString(),correlation:interaction.correlation,user_query:interaction.query,
   delivered_response:typeof deliveredResponse==='string'?deliveredResponse:null,
   outcome:interaction.terminal.outcome,failure:interaction.terminal.failure,model:interaction.model,usage,
  };
  try{return spool.append(record)===true;}catch{return false;}
 }

 function abandon(interaction,{outcome='unknown',failure={stage:'TIMEOUT_CANCELLATION',category:'CANCELLATION',code:'OWNER_CANCELLED'}}={}){
  complete(interaction,{outcome,failure});return write(interaction,null);
 }

 return Object.freeze({enabled,start,trace,model,complete,deliver:write,abandon});
}
