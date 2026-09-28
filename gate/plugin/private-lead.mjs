/*
 * PRIVATE_LEAD is a data-only reasoner adapter.  It translates the accepted
 * characterized profile into a signed loopback request; it deliberately owns
 * neither capability selection nor execution.
 */
import {detachDecisionNote} from '../foundation/decision-note.mjs';
import {sanitizeProtocolDiagnostic} from '../foundation/protocol-diagnostics.mjs';
import {canonical,createReasonerAdapter} from '../foundation/contracts.mjs';

export const PRIVATE_LEAD_DESTINATION=Object.freeze({kind:'PRIVATE_REASONER',service:'runpod-loopback',model:'PRIVATE_LEAD'});
// Only fixed local worker refusal codes may cross into owner-visible receipts.
// Never copy provider responses, exception text, pod identities, or URLs.
const providerRefusals=new Set(['local_disk_low','local_disk_full','local_storage_unavailable','capacity_timeout','gpu_capacity_unavailable','gpu_price_or_identity','gpu_budget_unavailable','canonical_volume_mismatch','runpod_auth_missing','runpod_request_failed','runpod_request_uncertain','runpod_cli_drift','runpod_list_shape','runpod_response_limit','mac_guard_not_ready','ssh_key_missing','ssh_timeout','ssh_failed','tunnel_failed','model_readiness_timeout','allocation_unresolved','untracked_or_duplicate_pod','gpu_runtime_limit','lease_cancelled','operation_cancelled','private_lead_configuration','operation_unavailable']);
export const safeProviderRefusal=value=>providerRefusals.has(value)?value:null;

export function profileSystem(profile){
 if(profile?.status!=='accepted-characterized'||profile?.logical_profile!=='PRIVATE_LEAD'||typeof profile?.prompt?.system!=='string')throw Error('private_lead_profile_invalid');
 return profile.prompt.system;
}

// Match the worker's UTF-8 packet limit, including the profile and schema.
// Only older, already-disclosed observations may be removed. Never trim source
// text in place, essential host state, or the newest observation.
export function privateLeadPacket(system,request,maxContextBytes=32768){
 if(!Number.isSafeInteger(maxContextBytes)||maxContextBytes<=0)throw Error('private_lead_adapter_config');
 const limit=Math.min(maxContextBytes,196608),packet={system,request};
 const fits=()=>Buffer.byteLength(canonical(packet),'utf8')<=limit;
 if(fits())return packet;
 packet.request=structuredClone(request);
 const messages=packet.request?.messages;
 if(!Array.isArray(messages)||messages.length!==2||messages[0]?.role!=='system'||messages[1]?.role!=='user')throw Error('model_context_limit');
 let context;try{context=JSON.parse(messages[1].content);}catch{throw Error('model_context_limit');}
 if(!Array.isArray(context?.state?.observations))throw Error('model_context_limit');
 let removed=0;
 while(context.state.observations.length>1){
  context.state.observations.shift();
  context.state.earlierObservationsOmitted=++removed;
  messages[1].content=canonical(context);
  if(fits())return packet;
 }
 throw Error('model_context_limit');
}

export function privateLeadTelemetry(value){
 const source=value&&typeof value==='object'?value:{};
 const numeric=(key,integer=false)=>typeof source[key]==='number'&&Number.isFinite(source[key])&&source[key]>=0&&source[key]<=Number.MAX_SAFE_INTEGER&&(!integer||Number.isSafeInteger(source[key]))?source[key]:null;
 const out={prompt_tokens:numeric('prompt_tokens',true),completion_tokens:numeric('completion_tokens',true)};
 out.usage_complete=out.prompt_tokens!==null&&out.completion_tokens!==null;
 for(const key of ['elapsed_seconds','ttft_seconds','decode_seconds','decode_tokens_per_second'])out[key]=numeric(key);
 for(const [key,allowed] of Object.entries({result_kind:['FINAL','ESCALATION','TOOL_PROPOSAL'],streamStatus:['COMPLETE','INCOMPLETE','NOT_STREAMED'],finishStatus:['stop','length','tool_calls','content_filter'],parseStatus:['BEFORE_PARSE','PARSED','FAILED'],normalization:['UNCHANGED','NOT_REACHED']}))out[key]=allowed.includes(source[key])?source[key]:'UNKNOWN';
 return out;
}

export function createPrivateLeadReasoner({execute,profile,body,maxContextBytes=32768,onTelemetry=()=>{},onDecision=()=>{}}){
 if(typeof execute!=='function'||typeof body!=='function')throw Error('private_lead_adapter_config');
 const system=profileSystem(profile);
 return createReasonerAdapter({id:'PRIVATE_LEAD',kind:'private-loopback',supportsWorkIntents:true,async invoke(request,signal){
   const packet=privateLeadPacket(system,request,maxContextBytes);
   const report=value=>onTelemetry({...privateLeadTelemetry(value),iteration:request.state.iteration,role:request.state.phase==='REVIEW'?'REVIEWER':'IMPLEMENTER'});
   let result;try{result=await execute(body('private_lead_propose','PRIVATE_LEAD',{request:packet},'private_lead_workmode'),signal);}catch(error){report(null);throw error;}
   // Account once before parsing or refusing; unavailable usage stays explicitly unknown.
   report(result?.telemetry);
   // A syntactically malformed model result is a proposal-schema failure, not
   // loss of the private runtime.  Preserve that distinction so Work Mode can
   // spend its single accepted correction turn. Packet limits exhaust the
   // context budget; provider availability failures still stop closed.
   if(result?.status!=='OK'||!result.result){
     if(result?.reason==='private_lead_proposal_limit')throw Error('model_context_limit');
     if(result?.reason==='private_lead_result_schema'){const error=Error('reasoner_result_shape');if(result.diagnostic)error.diagnostic=sanitizeProtocolDiagnostic(result.diagnostic);throw error;}
     const match=String(result?.reason??'').match(/^structured_decoding_http_(400|422)$/);
     if(match){const error=Error('structured_decoding_unavailable');error.httpStatus=Number(match[1]);error.backendFailure='HTTP_REJECTED';throw error;}
     const error=Error('private_lead_unavailable');error.providerCode=safeProviderRefusal(result?.reason);if(result?.diagnostic)error.diagnostic=sanitizeProtocolDiagnostic(result.diagnostic);throw error;
   }
   // Notes cannot enter the tool/action adapter or affect its validation.
   const enabled=request.state?.workIntent?.schema?.oneOf?.some(branch=>branch.properties?.decision_note);
   if(enabled){const detached=detachDecisionNote(result.result);try{onDecision({iteration:request.state.iteration,role:request.state.phase==='REVIEW'?'REVIEWER':'IMPLEMENTER',status:detached.status,note:detached.note});}catch{}return detached.value;}
   return result.result;
 }});
}
