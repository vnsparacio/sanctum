import fs from 'node:fs';
import path from 'node:path';
import {auditEvent} from '../gate/foundation/audit.mjs';
const codes=new Set(['INVALID_ARGUMENT','AMBIGUOUS_ARGUMENT','CONSEQUENTIAL_REPAIR_BLOCKED','UNKNOWN_SCHEMA','UNKNOWN_CAPABILITY','CAPABILITY_NOT_EXPOSED','CAPABILITY_DRIFT','PROPOSAL_SHAPE','ARGUMENT_SCHEMA','BACKEND_FAILURE','TOOL_VALIDATION_FAILED','TOOL_PLAN_FAILED','VERIFICATION_FAILED','TOOL_INCOMPATIBILITY_REPEATED','COMPLEX_STRUCTURED_TASK','SEMANTIC_QUALITY_REQUIRED','NONE']);
const outcomes=new Set(['VALID','REPAIRED','BLOCKED','SUCCESS','FAILED','VERIFIED','VERIFICATION_READY','VERIFICATION_SKIPPED','VERIFICATION_CHECK','LOCAL_CONTINUES','PRIVACY_BLOCKED','PROVIDER_NOT_CONFIGURED','DRY_RUN_READY','TIER_EXHAUSTED','POLICY_UNAVAILABLE']);
export function logger(file,toolNames,ruleIds){
 const names=new Set(toolNames), rules=new Set(ruleIds);
 return event=>{
  const selected=names.has(event.tool)?event.tool:'unknown';
  const outcome=outcomes.has(event.outcome)?event.outcome:'FAILED';
  const phase=['PROPOSAL','AUTHORITY','EGRESS','EXECUTION','RESULT','VERIFICATION'].includes(event.phase)?event.phase:'EXECUTION';
  const auditOutcome=['SUCCESS','FAILED','VERIFIED'].includes(outcome)?outcome:'UNKNOWN';
  const record={schema:'vinceai-failure/v1',timestamp:new Date().toISOString(),request_class:'tool_call',selected_tool:selected,validation_error:codes.has(event.code)?event.code:'NONE',repair_attempted:event.attempts===1,repair_rule_ids:(event.rules??[]).filter(x=>rules.has(x)),repair_success:event.repair_success===true,tool_result_status:['ok','error','not_executed'].includes(event.status)?event.status:'not_executed',escalated:false,target_model:['80b','235b'].includes(event.target)?event.target:null,final_outcome:outcome,capability_event:auditEvent({phase,capability:selected,correlation:String(event.runId??selected),reasonCodes:(event.rules??[]).filter(x=>rules.has(x)).map(x=>x.toUpperCase()),outcome:auditOutcome,dataClass:'PERSONAL',destinationClass:'LOCAL',durationBucket:'UNKNOWN'})};
  try{
   fs.mkdirSync(path.dirname(file),{recursive:true,mode:0o700});
   // One bounded prior segment. No arguments, exception text, IDs or prompts.
   if(fs.existsSync(file)&&fs.statSync(file).size>1024*1024)fs.renameSync(file,file+'.1');
   fs.appendFileSync(file,JSON.stringify(record)+'\n',{mode:0o600,flag:'a'});
  }catch{/* telemetry is not an authority boundary; never include payload in fallback logs */}
 };
}
