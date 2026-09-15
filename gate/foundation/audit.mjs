import {AUTHORITY_OUTCOMES,DATA_CLASSES,EXECUTION_STATES,VERIFIER_OUTCOMES,deepFreeze,digest,isRecord} from './contracts.mjs';

const phases=new Set(['PROPOSAL','AUTHORITY','EGRESS','EXECUTION','RESULT','VERIFICATION']);
const outcomes=new Set([...AUTHORITY_OUTCOMES,...EXECUTION_STATES,...VERIFIER_OUTCOMES,'SUCCESS','FAILED']);
const destinations=new Set(['LOCAL','EXTERNAL_SERVICE','REASONER','PRIVATE_REASONER','NONE']);
const durations=new Set(['UNKNOWN','LT_10MS','LT_100MS','LT_1S','LT_10S','GTE_10S']);
const code=value=>typeof value==='string'&&/^[A-Z][A-Z0-9_:-]{0,79}$/.test(value);
const capabilityName=value=>typeof value==='string'&&/^[a-z][a-z0-9_:-]{0,79}$/.test(value);
export function auditEvent({phase,capability,correlation,reasonCodes=[],outcome='UNKNOWN',dataClass='PERSONAL',destinationClass='LOCAL',durationBucket='UNKNOWN'}={}){
  if(!phases.has(phase)||!capabilityName(capability)||typeof correlation!=='string'||!correlation||correlation.length>4096||!Array.isArray(reasonCodes)||!reasonCodes.every(code)||!outcomes.has(outcome)||!DATA_CLASSES.includes(dataClass)||!destinations.has(destinationClass)||!durations.has(durationBucket))throw Error('audit_event_shape');
  const event={schema:'sanctum-audit/v1',phase,capability,correlation:digest(correlation),reasonCodes:[...reasonCodes],outcome,dataClass,destinationClass,durationBucket};
  return deepFreeze(event);
}
export function validateAuditEvent(value){
  const exact=Object.keys(value??{}).sort().join(',')==='capability,correlation,dataClass,destinationClass,durationBucket,outcome,phase,reasonCodes,schema';
  return exact&&isRecord(value)&&value.schema==='sanctum-audit/v1'&&phases.has(value.phase)&&capabilityName(value.capability)&&/^[a-f0-9]{64}$/.test(value.correlation)&&Array.isArray(value.reasonCodes)&&value.reasonCodes.every(code)&&outcomes.has(value.outcome)&&DATA_CLASSES.includes(value.dataClass)&&destinations.has(value.destinationClass)&&durations.has(value.durationBucket);
}

export function sourceEvent({correlation,sourceNeed,reasonCodes=[],queryClass,retrieval='NOT_ATTEMPTED',candidateBucket='ZERO',fetchedBucket='ZERO',evidenceBucket='ZERO',grounding='NOT_APPLICABLE',outcome='UNKNOWN'}={}){
 const values={sourceNeed:new Set(['NONE','WEB_HELPFUL','WEB_REQUIRED']),queryClass:new Set(['NONE','PUBLIC_GENERALIZED','EXACT_APPROVED','DENIED']),retrieval:new Set(['NOT_ATTEMPTED','ATTEMPTED','SUCCEEDED','FAILED']),candidateBucket:new Set(['ZERO','ONE','TWO_TO_THREE','FOUR_TO_SIX']),fetchedBucket:new Set(['ZERO','ONE','TWO_TO_THREE']),evidenceBucket:new Set(['ZERO','LT_1K','LT_6K','LT_12K','GTE_12K']),grounding:new Set(['GROUNDED','PARTIAL','INSUFFICIENT','NOT_APPLICABLE'])};
 if(typeof correlation!=='string'||!values.sourceNeed.has(sourceNeed)||!values.queryClass.has(queryClass)||!values.retrieval.has(retrieval)||!values.candidateBucket.has(candidateBucket)||!values.fetchedBucket.has(fetchedBucket)||!values.evidenceBucket.has(evidenceBucket)||!values.grounding.has(grounding)||!outcomes.has(outcome)||!Array.isArray(reasonCodes)||!reasonCodes.every(code))throw Error('source_event_shape');
 return deepFreeze({schema:'sanctum-source-audit/v1',correlation:digest(correlation),sourceNeed,reasonCodes:[...reasonCodes],queryClass,retrieval,candidateBucket,fetchedBucket,evidenceBucket,grounding,outcome});
}
