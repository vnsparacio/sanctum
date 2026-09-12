import fs from 'node:fs';
import path from 'node:path';
const codes=new Set(['INVALID_ARGUMENT','AMBIGUOUS_ARGUMENT','CONSEQUENTIAL_REPAIR_BLOCKED','UNKNOWN_SCHEMA','BACKEND_FAILURE','TOOL_VALIDATION_FAILED','TOOL_PLAN_FAILED','VERIFICATION_FAILED','TOOL_INCOMPATIBILITY_REPEATED','COMPLEX_STRUCTURED_TASK','SEMANTIC_QUALITY_REQUIRED','NONE']);
const outcomes=new Set(['VALID','REPAIRED','BLOCKED','SUCCESS','FAILED','VERIFIED','VERIFICATION_READY','VERIFICATION_SKIPPED','VERIFICATION_CHECK','LOCAL_CONTINUES','PRIVACY_BLOCKED','PROVIDER_NOT_CONFIGURED','DRY_RUN_READY','TIER_EXHAUSTED','POLICY_UNAVAILABLE']);
export function logger(file,toolNames,ruleIds){
 const names=new Set(toolNames), rules=new Set(ruleIds);
 return event=>{
  const record={schema:'vinceai-failure/v1',timestamp:new Date().toISOString(),request_class:'tool_call',selected_tool:names.has(event.tool)?event.tool:'unknown',validation_error:codes.has(event.code)?event.code:'NONE',repair_attempted:event.attempts===1,repair_rule_ids:(event.rules??[]).filter(x=>rules.has(x)),repair_success:event.repair_success===true,tool_result_status:['ok','error','not_executed'].includes(event.status)?event.status:'not_executed',escalated:false,target_model:['80b','235b'].includes(event.target)?event.target:null,final_outcome:outcomes.has(event.outcome)?event.outcome:'FAILED'};
  try{
   fs.mkdirSync(path.dirname(file),{recursive:true,mode:0o700});
   // One bounded prior segment. No arguments, exception text, IDs or prompts.
   if(fs.existsSync(file)&&fs.statSync(file).size>1024*1024)fs.renameSync(file,file+'.1');
   fs.appendFileSync(file,JSON.stringify(record)+'\n',{mode:0o600,flag:'a'});
  }catch{/* telemetry is not an authority boundary; never include payload in fallback logs */}
 };
}
