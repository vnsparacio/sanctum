/*
 * Shared, model-independent capability contracts. Validation proves shape and
 * scope only. A decision becomes authoritative solely when trusted Mac code
 * supplies it to an existing enforcement point.
 */
import {createHash} from 'node:crypto';

export const CONTRACT_VERSION='sanctum-capability/v1';
export const AUTHORITY_OUTCOMES=Object.freeze(['ALLOW','ALLOW_ONCE','ASK','DENY']);
export const VERIFIER_OUTCOMES=Object.freeze(['VERIFIED','REJECTED','UNKNOWN']);
export const EXECUTION_STATES=Object.freeze(['NOT_STARTED','COMPLETED','COMPLETION_UNKNOWN']);
export const DATA_CLASSES=Object.freeze(['PUBLIC','PERSONAL','RESTRICTED']);
export const EGRESS_PURPOSES=Object.freeze(['RISK_CLASSIFICATION','ANSWER_GENERATION','PUBLIC_SEARCH','PUBLIC_FETCH','REMOTE_RESULT_RETURN']);

export const isRecord=value=>!!value&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype;
export const canonical=value=>{
  const visit=x=>{
    if(x===null||typeof x==='string'||typeof x==='boolean')return x;
    if(typeof x==='number'){if(!Number.isFinite(x))throw Error('nonfinite');return x;}
    if(Array.isArray(x))return x.map(visit);
    if(!isRecord(x))throw Error('invalid_record');
    return Object.fromEntries(Object.keys(x).sort().map(k=>[k,visit(x[k])]));
  };
  return JSON.stringify(visit(value));
};
export const digest=value=>createHash('sha256').update(canonical(value)).digest('hex');
export const deepFreeze=value=>{
  if(Array.isArray(value)){for(const item of value)deepFreeze(item);return Object.freeze(value);}
  if(isRecord(value)){for(const item of Object.values(value))deepFreeze(item);return Object.freeze(value);}
  return value;
};
const exact=(value,keys)=>isRecord(value)&&Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
const text=(value,max=256)=>typeof value==='string'&&value.length>0&&value.length<=max&&!value.includes('\0');
const identifier=value=>typeof value==='string'&&/^[A-Za-z][A-Za-z0-9_.:-]{0,79}$/.test(value);
const destinationId=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$/.test(value);
const code=value=>typeof value==='string'&&/^[A-Z][A-Z0-9_:-]{0,79}$/.test(value);
const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const enumValue=(value,values)=>values.includes(value);
const dataClasses=value=>Array.isArray(value)&&value.length>0&&value.length<=3&&new Set(value).size===value.length&&value.every(x=>enumValue(x,DATA_CLASSES));
const clone=value=>deepFreeze(structuredClone(value));
const proposalShape=value=>{
  const keys=['schema','proposalId','requestId','revision','reasoner','capability','capabilityDigest','arguments'];
  return exact(value,keys)&&value.schema===CONTRACT_VERSION&&text(value.proposalId)&&text(value.requestId)&&Number.isSafeInteger(value.revision)&&value.revision>=0&&identifier(value.reasoner)&&identifier(value.capability)&&hex(value.capabilityDigest)&&isRecord(value.arguments);
};

export function validateToolProposal(value,manifest,validateArguments=()=>true){
  if(!proposalShape(value))return {ok:false,code:'PROPOSAL_SHAPE'};
  const spec=manifest?.byName&&Object.hasOwn(manifest.byName,value.capability)?manifest.byName[value.capability]:undefined;
  if(!spec)return {ok:false,code:'UNKNOWN_CAPABILITY'};
  if(spec.digest!==value.capabilityDigest)return {ok:false,code:'CAPABILITY_DRIFT'};
  if(spec.runtime?.exposed!==true)return {ok:false,code:'CAPABILITY_NOT_EXPOSED'};
  if(validateArguments(value.arguments)!==true)return {ok:false,code:'ARGUMENT_SCHEMA'};
  return {ok:true,value:clone(value),spec};
}

export function validateAuthorityDecision(value,now=Date.now()/1000){
  const keys=['schema','outcome','capability','proposalDigest','scope','effect','source','reasonCodes','expires','oneUse'];
  if(!exact(value,keys)||value.schema!==CONTRACT_VERSION||!enumValue(value.outcome,AUTHORITY_OUTCOMES)||!identifier(value.capability)||!hex(value.proposalDigest)||!text(value.scope)||!enumValue(value.effect,['READ','MUTATION','CONTROL'])||!enumValue(value.source,['MAC_POLICY','MAC_GATE','NATIVE_APPROVAL'])||!Array.isArray(value.reasonCodes)||!value.reasonCodes.every(code)||typeof value.oneUse!=='boolean'||!(value.expires===null||(typeof value.expires==='number'&&Number.isFinite(value.expires))))return {ok:false,code:'AUTHORITY_SHAPE'};
  if(value.outcome==='ALLOW_ONCE'&&(!value.oneUse||value.expires===null||value.expires<=now))return {ok:false,code:'AUTHORITY_EXPIRED'};
  if(value.outcome==='ASK'&&(!value.oneUse||value.expires===null||value.expires<=now))return {ok:false,code:'AUTHORITY_PENDING_INVALID'};
  if(['ALLOW','DENY'].includes(value.outcome)&&(value.oneUse||value.expires!==null))return {ok:false,code:'AUTHORITY_SCOPE'};
  return {ok:true,value:clone(value)};
}

export function validateEgressDecision(value,now=Date.now()/1000){
  const keys=['schema','outcome','capability','capabilityDigest','requestDigest','packetDigest','scope','revision','dataClasses','destination','purpose','expires','oneUse','approvalState','reasonCodes'];
  if(!exact(value,keys)||value.schema!==CONTRACT_VERSION||!enumValue(value.outcome,AUTHORITY_OUTCOMES)||!identifier(value.capability)||!hex(value.capabilityDigest)||!hex(value.requestDigest)||!hex(value.packetDigest)||!text(value.scope)||!Number.isSafeInteger(value.revision)||value.revision<0||!dataClasses(value.dataClasses)||!exact(value.destination,['kind','service','model'])||![value.destination.kind,value.destination.service,value.destination.model].every(destinationId)||!enumValue(value.purpose,EGRESS_PURPOSES)||!(value.expires===null||(typeof value.expires==='number'&&Number.isFinite(value.expires)))||typeof value.oneUse!=='boolean'||!enumValue(value.approvalState,['NONE','PENDING','CONSUMED'])||!Array.isArray(value.reasonCodes)||!value.reasonCodes.every(code))return {ok:false,code:'EGRESS_SHAPE'};
  if(value.outcome==='ALLOW_ONCE'&&(!value.oneUse||value.approvalState!=='CONSUMED'||value.expires===null||value.expires<=now))return {ok:false,code:'EGRESS_EXPIRED_OR_UNCONSUMED'};
  if(value.outcome==='ASK'&&(!value.oneUse||value.approvalState!=='PENDING'||value.expires===null||value.expires<=now))return {ok:false,code:'EGRESS_PENDING_INVALID'};
  if(['ALLOW','DENY'].includes(value.outcome)&&(value.oneUse||value.approvalState!=='NONE'||value.expires!==null))return {ok:false,code:'EGRESS_SCOPE'};
  return {ok:true,value:clone(value)};
}

export function egressMatches(decision,claim,now=Date.now()/1000){
  const checked=validateEgressDecision(decision,now);if(!checked.ok)return checked;
  const keys=['requestDigest','packetDigest','scope','revision','capability','capabilityDigest','dataClasses','purpose','destination'];
  if(!exact(claim,keys)||!dataClasses(claim.dataClasses)||!exact(claim.destination,['kind','service','model']))return {ok:false,code:'EGRESS_CLAIM_SHAPE'};
  const d=checked.value;
  if(!['ALLOW','ALLOW_ONCE'].includes(d.outcome))return {ok:false,code:'EGRESS_NOT_ALLOWED'};
  for(const key of ['requestDigest','packetDigest','scope','revision','capability','capabilityDigest','purpose'])if(d[key]!==claim[key])return {ok:false,code:'EGRESS_SCOPE_MISMATCH'};
  if(canonical(d.dataClasses)!==canonical(claim.dataClasses))return {ok:false,code:'EGRESS_DATA_CLASS_MISMATCH'};
  if(canonical(d.destination)!==canonical(claim.destination))return {ok:false,code:'EGRESS_DESTINATION_MISMATCH'};
  return {ok:true,value:d};
}

export function createToolResultEnvelope({capability,capabilityDigest,executionState,result,provenance='LOCAL',dataClass='PERSONAL',untrusted=false,truncated=false,repairRules=[],verifier='UNKNOWN',rollback='NONE'}){
  if(!identifier(capability)||!hex(capabilityDigest)||!enumValue(executionState,EXECUTION_STATES)||!identifier(provenance)||!enumValue(dataClass,DATA_CLASSES)||typeof untrusted!=='boolean'||typeof truncated!=='boolean'||!Array.isArray(repairRules)||!repairRules.every(x=>typeof x==='string'&&/^[a-z][a-z0-9_:-]{0,79}$/.test(x))||!enumValue(verifier,VERIFIER_OUTCOMES)||!enumValue(rollback,['NONE','CREATE_ONLY','UNDO_CAPABILITY','LIFECYCLE_RECONCILIATION']))throw Error('result_envelope_shape');
  const ok=result?.ok===true;
  const payload=ok?{data:Object.hasOwn(result,'data')?result.data:null}:{error:{code:code(result?.error?.code)?result.error.code:'BACKEND_FAILURE'}};
  if(canonical(payload).length>65536)throw Error('result_envelope_limit');
  return clone({schema:CONTRACT_VERSION,capability,capabilityDigest,executionState,ok,provenance,dataClass,untrusted,truncated,repairRules:[...repairRules],verifier,rollback,...payload});
}

export function validateReasonerRequest(value){
  const keys=['schema','requestId','scope','revision','messages','manifestDigest','state'];
  if(!exact(value,keys)||value.schema!==CONTRACT_VERSION||!text(value.requestId)||!text(value.scope)||!Number.isSafeInteger(value.revision)||value.revision<0||!hex(value.manifestDigest)||!isRecord(value.state)||!Array.isArray(value.messages)||!value.messages.length||value.messages.length>64)return {ok:false,code:'REASONER_REQUEST_SHAPE'};
  if(!value.messages.every(x=>exact(x,['role','content'])&&enumValue(x.role,['system','user','assistant'])&&text(x.content,65536)))return {ok:false,code:'REASONER_REQUEST_SHAPE'};
  if(canonical({messages:value.messages,state:value.state}).length>262144)return {ok:false,code:'REASONER_REQUEST_LIMIT'};
  return {ok:true,value:clone(value)};
}

export function validateReasonerResult(value,{supportsToolProposals=false}={}){
  if(!isRecord(value))return {ok:false,code:'REASONER_RESULT_SHAPE'};
  if(value.kind==='FINAL')return exact(value,['kind','text'])&&text(value.text,32768)?{ok:true,value:clone(value)}:{ok:false,code:'REASONER_RESULT_SHAPE'};
  if(value.kind==='ESCALATION')return exact(value,['kind','reason'])&&code(value.reason)?{ok:true,value:clone(value)}:{ok:false,code:'REASONER_RESULT_SHAPE'};
  if(value.kind==='TOOL_PROPOSAL')return supportsToolProposals&&exact(value,['kind','proposal'])&&proposalShape(value.proposal)?{ok:true,value:clone(value)}:{ok:false,code:supportsToolProposals?'REASONER_RESULT_SHAPE':'REASONER_TOOL_PROPOSAL_UNSUPPORTED'};
  return {ok:false,code:'REASONER_RESULT_SHAPE'};
}

export function createReasonerAdapter({id,kind,invoke,supportsToolProposals=false}){
  if(!text(id)||!text(kind)||typeof invoke!=='function'||typeof supportsToolProposals!=='boolean')throw Error('reasoner_adapter_shape');
  return Object.freeze({id,kind,supportsToolProposals,async invoke(request,signal){
    const checked=validateReasonerRequest(request);if(!checked.ok)throw Error(checked.code.toLowerCase());
    const result=validateReasonerResult(await invoke(checked.value,signal),{supportsToolProposals});
    if(!result.ok)throw Error(result.code.toLowerCase());
    return result.value;
  }});
}
