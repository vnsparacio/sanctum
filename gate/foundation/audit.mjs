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
