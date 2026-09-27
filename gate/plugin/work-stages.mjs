/* Owner-authored checkpoints; one workspace and one aggregate task budget. */
export function validateStages(stages){
 if(stages===undefined)return undefined;
 if(!Array.isArray(stages)||stages.length<2||stages.length>3)throw Error('work_stages_invalid');
 const names=new Set();
 for(const stage of stages){
  if(!stage||Object.keys(stage).sort().join(',')!=='goal,name,required_files'||typeof stage.name!=='string'||!/^[a-z][a-z0-9_-]{0,31}$/.test(stage.name)||names.has(stage.name)||typeof stage.goal!=='string'||!stage.goal.trim()||stage.goal.length>1000||!Array.isArray(stage.required_files)||!stage.required_files.length||stage.required_files.length>8)throw Error('work_stages_invalid');
  names.add(stage.name);
  for(const path of stage.required_files)if(typeof path!=='string'||path.length>160||!path.split('/').every(part=>/^[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(part)))throw Error('work_stages_invalid');
  if(new Set(stage.required_files).size!==stage.required_files.length)throw Error('work_stages_invalid');
 }
 return structuredClone(stages);
}
export function stagePlan(goal,stages){
 const checked=validateStages(stages);
 const plan=checked?.map((stage,index)=>({...stage,task:`Overall owner goal: ${goal}\nCheckpoint ${index+1}/${checked.length}: ${stage.name}\n${stage.goal}\nRequired files: ${stage.required_files.join(', ')}\nComplete only this checkpoint. Preserve earlier passing work. All configured tests and protected acceptance checks must pass.`}))??[{name:null,required_files:[],task:goal}];
 if(plan.some(stage=>stage.task.length>4000))throw Error('work_stage_goal_too_large');
 return plan;
}
export async function runStages({plan,run,options,onStage=()=>{},onCheckpoint=()=>{},now=()=>Date.now()/1000}){
 const started=now();let calls=0,iterations=0,result;
 const metrics=()=>({modelCalls:calls,iterations,elapsedSeconds:now()-started});
 for(let index=0;index<plan.length;index++){
  const remaining={maxIterations:options.maxIterations-iterations,maxModelCalls:options.maxModelCalls-calls,maxTaskSeconds:options.maxTaskSeconds-(now()-started)};
  if(remaining.maxIterations<1||remaining.maxModelCalls<1||remaining.maxTaskSeconds<1)return {status:'BUDGET_EXHAUSTED',reason:remaining.maxTaskSeconds<1?'TASK_TIME_BUDGET':remaining.maxModelCalls<1?'MODEL_CALL_BUDGET':'ITERATION_BUDGET',metrics:metrics(),checkpointsCompleted:index};
  onStage({...plan[index],required_files:[...new Set(plan.slice(0,index+1).flatMap(stage=>stage.required_files))]},index);
  result=await run({...options,...remaining,task:plan[index].task});
  calls+=result.metrics?.modelCalls??0;
  // Successful runs stop before incrementing the final iteration; charge that call too.
  iterations+=Math.max(result.metrics?.iterations??0,result.metrics?.modelCalls??0);
  result={...result,metrics:metrics(),checkpointsCompleted:result.status==='COMPLETE'?index+1:index};
  if(plan.length>1)try{onCheckpoint({checkpoint:index+1,name:plan[index].name,status:result.status,reason:result.reason,metrics:result.metrics});}catch{return result.status==='COMPLETE'?{...result,status:'ENVIRONMENT_FAILURE',reason:'EVIDENCE_PERSISTENCE_FAILED',originalStatus:result.status,originalReason:result.reason,persistenceWarning:'LEDGER_UNAVAILABLE'}:{...result,persistenceWarning:'LEDGER_UNAVAILABLE'};}
  if(result.status!=='COMPLETE')return result;
 }
 return result;
}
const storageCodes=new Set(['local_disk_low','local_disk_full','local_storage_unavailable']);
export const storageCode=value=>storageCodes.has(value)?value.toUpperCase():['ENOSPC','EDQUOT'].includes(value)?'LOCAL_DISK_FULL':null;
export async function runAndRecord({run,finish,storageFailure=()=>null}){
 let result;
 try{result=await run();}catch(error){result={status:'ENVIRONMENT_FAILURE',reason:storageCode(error?.code)??'WORK_MODE_FAILURE'};}
 const local=storageFailure()??storageCode(result.providerCode);
 if(local)result={...result,status:'ENVIRONMENT_FAILURE',reason:local};
 try{finish(result);}catch(error){
  const warning=storageCode(error?.code)??'LEDGER_UNAVAILABLE';
  result=result.status==='COMPLETE'?{...result,status:'ENVIRONMENT_FAILURE',reason:'EVIDENCE_PERSISTENCE_FAILED',originalStatus:result.status,originalReason:result.reason,persistenceWarning:warning}:{...result,persistenceWarning:warning};
 }
 return result;
}
