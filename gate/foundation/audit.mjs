import {CONTRACT_VERSION,digest,isRecord} from './contracts.mjs';

const phases=new Set(['PROPOSAL','AUTHORITY','EGRESS','EXECUTION','RESULT','VERIFICATION']);
const safe=value=>typeof value==='string'&&/^[A-Za-z0-9_:-]{1,80}$/.test(value);
export function auditEvent({phase,capability,correlation,reasonCodes=[],outcome='UNKNOWN',dataClass='PERSONAL',destinationClass='LOCAL',durationBucket='UNKNOWN'}={}){
  if(!phases.has(phase)||typeof capability!=='string'||!capability||typeof correlation!=='string'||!correlation||!Array.isArray(reasonCodes)||!reasonCodes.every(safe)||!safe(outcome)||!safe(dataClass)||!safe(destinationClass)||!safe(durationBucket))throw Error('audit_event_shape');
  const event={schema:'sanctum-audit/v1',phase,capability,correlation:digest(correlation),reasonCodes:[...reasonCodes],outcome,dataClass,destinationClass,durationBucket};
  return Object.freeze(event);
}
export function validateAuditEvent(value){
  if(!isRecord(value)||value.schema!=='sanctum-audit/v1'||!phases.has(value.phase)||typeof value.capability!=='string'||!/^[a-f0-9]{64}$/.test(value.correlation)||!Array.isArray(value.reasonCodes)||!value.reasonCodes.every(safe))return false;
  // Exact keys plus hashed correlation prevent arbitrary payload fields. Safe
  // reason codes may legitimately contain words such as "argument".
  return Object.keys(value).sort().join(',')==='capability,correlation,dataClass,destinationClass,durationBucket,outcome,phase,reasonCodes,schema';
}
