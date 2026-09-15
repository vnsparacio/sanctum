/*
 * Shared, model-independent capability contracts. These records describe Mac
 * policy decisions; they are not a way for a model to manufacture authority.
 */
import {createHash} from 'node:crypto';

export const CONTRACT_VERSION='sanctum-capability/v1';
export const AUTHORITY_OUTCOMES=Object.freeze(['ALLOW','ALLOW_ONCE','ASK','DENY']);
export const VERIFIER_OUTCOMES=Object.freeze(['VERIFIED','REJECTED','UNKNOWN']);
export const EXECUTION_STATES=Object.freeze(['NOT_STARTED','COMPLETED','COMPLETION_UNKNOWN']);
export const DATA_CLASSES=Object.freeze(['PUBLIC','PERSONAL','RESTRICTED']);
export const EGRESS_PURPOSES=Object.freeze(['RISK_CLASSIFICATION','ANSWER_GENERATION','PUBLIC_SEARCH','PUBLIC_FETCH','REMOTE_RESULT_RETURN']);

export const canonical=value=>{
  const visit=x=>{
    if(x===null||typeof x==='string'||typeof x==='boolean')return x;
    if(typeof x==='number'){if(!Number.isFinite(x))throw Error('nonfinite');return x;}
    if(Array.isArray(x))return x.map(visit);
    if(!x||typeof x!=='object'||Object.getPrototypeOf(x)!==Object.prototype)throw Error('invalid_record');
    return Object.fromEntries(Object.keys(x).sort().map(k=>[k,visit(x[k])]));
  };
  return JSON.stringify(visit(value));
};
export const digest=value=>createHash('sha256').update(canonical(value)).digest('hex');
export const isRecord=value=>!!value&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype;
const exact=(value,keys)=>isRecord(value)&&Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
const text=(value,max=256)=>typeof value==='string'&&value.length>0&&value.length<=max;
const enumValue=(value,values)=>values.includes(value);
const dataClasses=value=>Array.isArray(value)&&value.length>0&&value.length<=3&&new Set(value).size===value.length&&value.every(x=>enumValue(x,DATA_CLASSES));

export function validateToolProposal(value,manifest,validateArguments=()=>true){
  const keys=['schema','proposalId','requestId','revision','reasoner','capability','capabilityDigest','arguments'];
  if(!exact(value,keys)||value.schema!==CONTRACT_VERSION||!text(value.proposalId)||!text(value.requestId)||!Number.isSafeInteger(value.revision)||value.revision<0||!text(value.reasoner)||!text(value.capability)||!text(value.capabilityDigest,64)||!isRecord(value.arguments))return {ok:false,code:'PROPOSAL_SHAPE'};
  const spec=manifest?.byName?.get(value.capability);
  if(!spec)return {ok:false,code:'UNKNOWN_CAPABILITY'};
  if(spec.digest!==value.capabilityDigest)return {ok:false,code:'CAPABILITY_DRIFT'};
  if(spec.runtime?.exposed!==true)return {ok:false,code:'CAPABILITY_NOT_EXPOSED'};
  if(validateArguments(value.arguments)!==true)return {ok:false,code:'ARGUMENT_SCHEMA'};
  return {ok:true,value:Object.freeze(structuredClone(value)),spec};
}

export function validateAuthorityDecision(value,now=Date.now()/1000){
  const keys=['schema','outcome','capability','proposalDigest','scope','effect','source','reasonCodes','expires','oneUse'];
  if(!exact(value,keys)||value.schema!==CONTRACT_VERSION||!enumValue(value.outcome,AUTHORITY_OUTCOMES)||!text(value.capability)||!text(value.proposalDigest,64)||!text(value.scope)||!enumValue(value.effect,['READ','MUTATION','CONTROL'])||!text(value.source)||!Array.isArray(value.reasonCodes)||!value.reasonCodes.every(x=>text(x,80))||typeof value.oneUse!=='boolean'||!(value.expires===null||(typeof value.expires==='number'&&Number.isFinite(value.expires))))return {ok:false,code:'AUTHORITY_SHAPE'};
  if(value.outcome==='ALLOW_ONCE'&&(!value.oneUse||value.expires===null||value.expires<=now))return {ok:false,code:'AUTHORITY_EXPIRED'};
  if(value.outcome!=='ALLOW_ONCE'&&value.oneUse)return {ok:false,code:'AUTHORITY_SCOPE'};
  return {ok:true,value:Object.freeze(structuredClone(value))};
}

export function validateEgressDecision(value,now=Date.now()/1000){
  const keys=['schema','outcome','capability','capabilityDigest','requestDigest','packetDigest','scope','revision','dataClasses','destination','purpose','expires','oneUse','approvalState','reasonCodes'];
  if(!exact(value,keys)||value.schema!==CONTRACT_VERSION||!enumValue(value.outcome,AUTHORITY_OUTCOMES)||!text(value.capability)||!text(value.capabilityDigest,64)||!text(value.requestDigest,64)||!text(value.packetDigest,64)||!text(value.scope)||!Number.isSafeInteger(value.revision)||value.revision<0||!dataClasses(value.dataClasses)||!isRecord(value.destination)||!exact(value.destination,['kind','service','model'])||!text(value.destination.kind)||!text(value.destination.service)||!text(value.destination.model)||!enumValue(value.purpose,EGRESS_PURPOSES)||!(value.expires===null||(typeof value.expires==='number'&&Number.isFinite(value.expires)))||typeof value.oneUse!=='boolean'||!enumValue(value.approvalState,['NONE','PENDING','CONSUMED'])||!Array.isArray(value.reasonCodes)||!value.reasonCodes.every(x=>text(x,80)))return {ok:false,code:'EGRESS_SHAPE'};
  if(value.outcome==='ALLOW_ONCE'&&(!value.oneUse||value.approvalState!=='CONSUMED'||value.expires===null||value.expires<=now))return {ok:false,code:'EGRESS_EXPIRED_OR_UNCONSUMED'};
  if(value.outcome==='ALLOW'&&(value.oneUse||value.approvalState!=='NONE'))return {ok:false,code:'EGRESS_SCOPE'};
  if(['ASK','DENY'].includes(value.outcome)&&value.approvalState==='CONSUMED')return {ok:false,code:'EGRESS_SCOPE'};
  return {ok:true,value:Object.freeze(structuredClone(value))};
}

export function egressMatches(decision,claim,now=Date.now()/1000){
  const checked=validateEgressDecision(decision,now);if(!checked.ok)return checked;
  if(!isRecord(claim)||!['requestDigest','packetDigest','scope','revision','capability','purpose','destination'].every(k=>Object.hasOwn(claim,k)))return {ok:false,code:'EGRESS_CLAIM_SHAPE'};
  const d=checked.value;
  if(!['ALLOW','ALLOW_ONCE'].includes(d.outcome))return {ok:false,code:'EGRESS_NOT_ALLOWED'};
  for(const key of ['requestDigest','packetDigest','scope','revision','capability','purpose'])if(d[key]!==claim[key])return {ok:false,code:'EGRESS_SCOPE_MISMATCH'};
  if(canonical(d.destination)!==canonical(claim.destination))return {ok:false,code:'EGRESS_DESTINATION_MISMATCH'};
  return {ok:true,value:d};
}

export function createToolResultEnvelope({capability,capabilityDigest,executionState,result,provenance='LOCAL',dataClass='PERSONAL',untrusted=false,truncated=false,repairRules=[],verifier='UNKNOWN',rollback='NONE'}){
  if(!text(capability)||!text(capabilityDigest,64)||!enumValue(executionState,EXECUTION_STATES)||!text(provenance)||!enumValue(dataClass,DATA_CLASSES)||typeof untrusted!=='boolean'||typeof truncated!=='boolean'||!Array.isArray(repairRules)||!repairRules.every(x=>text(x,80))||!enumValue(verifier,VERIFIER_OUTCOMES)||!enumValue(rollback,['NONE','CREATE_ONLY','UNDO_CAPABILITY','LIFECYCLE_RECONCILIATION']))throw Error('result_envelope_shape');
  const ok=result?.ok===true;
  return Object.freeze({schema:CONTRACT_VERSION,capability,capabilityDigest,executionState,ok,provenance,dataClass,untrusted,truncated,repairRules:[...repairRules],verifier,rollback,...(ok?{data:result.data}:{error:{code:text(result?.error?.code,80)?result.error.code:'BACKEND_FAILURE'}})});
}

export function createReasonerAdapter({id,kind,invoke,supportsToolProposals=false}){
  if(!text(id)||!text(kind)||typeof invoke!=='function'||typeof supportsToolProposals!=='boolean')throw Error('reasoner_adapter_shape');
  return Object.freeze({id,kind,supportsToolProposals,async invoke(request,signal){
    if(!isRecord(request)||request.schema!==CONTRACT_VERSION||!text(request.requestId)||!text(request.scope)||!Array.isArray(request.messages)||!text(request.manifestDigest,64))throw Error('reasoner_request_shape');
    const value=await invoke(Object.freeze(structuredClone(request)),signal);
    if(!isRecord(value)||!['FINAL','ESCALATION','TOOL_PROPOSAL'].includes(value.kind))throw Error('reasoner_result_shape');
    if(value.kind==='TOOL_PROPOSAL'&&!supportsToolProposals)throw Error('reasoner_tool_proposal_unsupported');
    return Object.freeze(structuredClone(value));
  }});
}
