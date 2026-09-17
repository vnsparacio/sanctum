/*
 * PRIVATE_LEAD is a data-only reasoner adapter.  It translates the accepted
 * characterized profile into a signed loopback request; it deliberately owns
 * neither capability selection nor execution.
 */
import {sanitizeProtocolDiagnostic} from '../foundation/protocol-diagnostics.mjs';
import {createReasonerAdapter} from '../foundation/contracts.mjs';

export const PRIVATE_LEAD_DESTINATION=Object.freeze({kind:'PRIVATE_REASONER',service:'runpod-loopback',model:'PRIVATE_LEAD'});

export function profileSystem(profile){
 if(profile?.status!=='accepted-characterized'||profile?.logical_profile!=='PRIVATE_LEAD'||typeof profile?.prompt?.system!=='string')throw Error('private_lead_profile_invalid');
 return profile.prompt.system;
}

export function createPrivateLeadReasoner({execute,profile,body,onTelemetry=()=>{}}){
 if(typeof execute!=='function'||typeof body!=='function')throw Error('private_lead_adapter_config');
 const system=profileSystem(profile);
 return createReasonerAdapter({id:'PRIVATE_LEAD',kind:'private-loopback',supportsWorkIntents:true,async invoke(request,signal){
   const result=await execute(body('private_lead_propose','PRIVATE_LEAD',{request:{system,request}},'private_lead_workmode'),signal);
   // A syntactically malformed model result is a proposal-schema failure, not
   // loss of the private runtime.  Preserve that distinction so Work Mode can
   // spend its single accepted correction turn.  All other worker failures
   // remain availability failures and stop closed.
   if(result?.status!=='OK'||!result.result){
     if(result?.reason==='private_lead_result_schema'){const error=Error('reasoner_result_shape');if(result.diagnostic)error.diagnostic=sanitizeProtocolDiagnostic(result.diagnostic);throw error;}
     const match=String(result?.reason??'').match(/^structured_decoding_http_(400|422)$/);
     if(match){const error=Error('structured_decoding_unavailable');error.httpStatus=Number(match[1]);error.backendFailure='HTTP_REJECTED';throw error;}
     const error=Error('private_lead_unavailable');if(result?.diagnostic)error.diagnostic=sanitizeProtocolDiagnostic(result.diagnostic);throw error;
   }
   if(result.telemetry)onTelemetry(structuredClone(result.telemetry));
   return result.result;
 }});
}
