/* Host completion path for one isolated Qwen Code headless coding run. */
const HEX64=/^[a-f0-9]{64}$/;
const terminal=(status,reason,metrics,providerCode=null)=>({status,reason,metrics,...(providerCode?{providerCode}:{})});

export async function runQwenWorkMode({task,profile,call,baseline,evaluate,reviewer,signal,now=()=>Date.now()/1000}){
 if(profile.engine!=='qwen_code'||profile.stages||profile.reviewer===false||typeof reviewer!=='function')throw Error('qwen_workmode_config');
 const started=now();
 let metrics={modelCalls:0,iterations:0,elapsedSeconds:0};
 let result=terminal('ENVIRONMENT_FAILURE','QWEN_RUN_UNAVAILABLE',metrics);
 try{
  const starting=await baseline({signal});
  task.ledger.event('QWEN_BASELINE',starting);
  if(starting?.ordinaryExecuted!==true||starting?.protectedExecuted!==true)throw Error('qwen_baseline_unavailable');
  if(signal?.aborted)throw Error('qwen_cancelled');
  const response=await call(task,'worktree_qwen_run',{task_id:task.id,profile:task.profile,goal:task.goal},signal);
  const run=response?.result;
  if(response?.status!=='OK'||run?.schema!=='sanctum-qwen-run/v1'||run.taskId!==task.id){
   result=terminal('ENVIRONMENT_FAILURE','QWEN_RUN_UNAVAILABLE',metrics,response?.reason??null);
  }else{
   metrics={modelCalls:run.modelCalls??0,iterations:1,elapsedSeconds:run.elapsedSeconds??now()-started};
   task.telemetry.qwenCostUsd=run.estimatedCostUsd??0;
   task.telemetry.estimatedCostUsd+=task.telemetry.qwenCostUsd;
   task.telemetry.modelCalls+=metrics.modelCalls;
   task.telemetry.inferenceSeconds+=run.inferenceSeconds??0;
   task.ledger.event('QWEN_RUN',{code:run.code,modelCalls:metrics.modelCalls,inferenceSeconds:run.inferenceSeconds??null,estimatedCostUsd:run.estimatedCostUsd??null,containerAbsent:run.containerAbsent===true,patchDigest:run.importReceipt?.patchDigest??null,candidateDigest:run.importReceipt?.candidateDigest??null});
   if(run.ok!==true||run.code!=='OK'||run.containerAbsent!==true){
    const budget=/limit|wall|budget/i.test(run.code??'');
    result=terminal(budget?'BUDGET_EXHAUSTED':'ENVIRONMENT_FAILURE',run.code??'QWEN_RUN_FAILED',metrics);
   }else if(!Array.isArray(run.importReceipt?.paths)||!run.importReceipt.paths.length||run.importReceipt.authorityResult!=='ALLOW'||!HEX64.test(run.importReceipt.candidateDigest??'')){
    result=terminal('ENVIRONMENT_FAILURE','QWEN_IMPORT_IDENTITY',metrics);
   }else if(task.telemetry.estimatedCostUsd>profile.max_cost_usd){
    result=terminal('BUDGET_EXHAUSTED','COST_BUDGET',metrics);
   }else{
    if(signal?.aborted)throw Error('qwen_cancelled');
    const evidence=await evaluate({signal});
    task.ledger.event('QWEN_EVALUATION',{passed:evidence?.passed===true,diffDigest:evidence?.diffDigest??null,checks:(evidence?.checks??[]).map(({operation,ok,code})=>({operation,ok,code}))});
    if(evidence?.passed!==true||evidence?.protectedEvidence?.integrity!=='PASS'){
     result=terminal('BLOCKED','EVALUATOR_REJECTED',metrics);
    }else{
     if(signal?.aborted)throw Error('qwen_cancelled');
     const state={iteration:1,tests:{passed:true,required:false},observations:[]};
     const critique=await reviewer({task:task.goal,state,claim:'COMPLETE',evidence,signal});
     task.ledger.event('QWEN_REVIEWER',{verdict:critique?.verdict??'UNAVAILABLE',findings:(critique?.findings??[]).map(({checkCode,evidenceDigest})=>({checkCode,evidenceDigest}))});
     result=critique?.verdict==='ACCEPT'
      ?terminal('COMPLETE','QWEN_ACCEPTED',metrics)
      :terminal('BLOCKED',critique?.verdict==='REVISE'?'REVIEWER_REVISE':'REVIEWER_REJECT',metrics);
    }
   }
  }
 }catch(error){
  result=terminal(signal?.aborted?'BLOCKED':'ENVIRONMENT_FAILURE',signal?.aborted?'OWNER_CANCELLED':'QWEN_WORKMODE_FAILURE',metrics);
 }finally{
  try{
   const closed=await call(task,'close',{});
   task.ledger.event('QWEN_GPU_CLEANUP',{phase:closed?.gpu?.phase??'UNKNOWN'});
   if(closed?.status!=='OK'||closed?.gpu?.phase!=='OFFLINE')result=terminal('ENVIRONMENT_FAILURE','GPU_CLEANUP_UNCERTAIN',metrics);
  }catch{result=terminal('ENVIRONMENT_FAILURE','GPU_CLEANUP_UNCERTAIN',metrics);}
 }
 if(result.status==='COMPLETE'&&task.telemetry.estimatedCostUsd>profile.max_cost_usd)result=terminal('BUDGET_EXHAUSTED','COST_BUDGET',metrics);
 result.metrics={...metrics,modelCalls:task.telemetry.modelCalls,elapsedSeconds:now()-started};
 return result;
}
