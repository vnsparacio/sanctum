/*
 * PRIVATE_LEAD is a data-only reasoner adapter.  It translates the accepted
 * characterized profile into a signed loopback request; it deliberately owns
 * neither capability selection nor execution.
 */
import {createReasonerAdapter} from '../foundation/contracts.mjs';

export const PRIVATE_LEAD_DESTINATION=Object.freeze({kind:'PRIVATE_REASONER',service:'runpod-loopback',model:'PRIVATE_LEAD'});

export function profileSystem(profile){
 if(profile?.status!=='accepted-characterized'||profile?.logical_profile!=='PRIVATE_LEAD'||typeof profile?.prompt?.system!=='string')throw Error('private_lead_profile_invalid');
 return profile.prompt.system;
}

export function createPrivateLeadReasoner({execute,profile,body}){
 if(typeof execute!=='function'||typeof body!=='function')throw Error('private_lead_adapter_config');
 const system=profileSystem(profile);
 return createReasonerAdapter({id:'PRIVATE_LEAD',kind:'private-loopback',supportsToolProposals:true,async invoke(request,signal){
   const result=await execute(body('private_lead_propose','PRIVATE_LEAD',{request:{system,request}},'private_lead_workmode'),signal);
   if(result?.status!=='OK'||!result.result)throw Error('private_lead_unavailable');
   return result.result;
 }});
}
