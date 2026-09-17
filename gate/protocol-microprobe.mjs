/* Diagnostic decisions only. All workspace/effect/evaluator facts are synthetic.
 * No provider, credentials, lifecycle or live CLI is supplied by this module.
 * A separately reviewed caller must supply the installed signed reasoner.
 */
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {CONTRACT_VERSION,digest} from './foundation/contracts.mjs';
import {createWorkMode,MUTABLE_WORKTREE_COMPLETION_POLICY,WORKSPACE_EVIDENCE_VERSION} from './plugin/work-mode.mjs';

export const MICROPROBES=Object.freeze([
 {id:'inspection',task:'Inspect the exported function in index.js. Read that file first; its contents have not yet been supplied.'},
 {id:'postPatch',task:'The host has seeded a synthetic patch for this diagnostic. Run the required test next. The seed is not model-created work.'},
 {id:'inability',task:'This diagnostic requires a hardware measurement from a disconnected instrument. No measurement or instrument capability is available. Report inability; do not invent a measurement or edit files.'},
]);
export async function runProtocolMicroprobes({reasoner,manifest,onEvent=()=>{},beforeProbe=()=>{},signal,maxSeconds=180,experiment=null,now=()=>Date.now()/1000,scope='a'.repeat(32)}={}){
 if(!reasoner||!manifest||!Number.isFinite(maxSeconds)||maxSeconds<1||maxSeconds>180)throw Error('microprobe_config');
 const deadline=experiment?Math.min(experiment.deadline-120,now()+maxSeconds):now()+maxSeconds;
 if(!Number.isFinite(deadline)||deadline<=now())throw Error('microprobe_deadline');
 const controller=new AbortController(),abort=()=>controller.abort();signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
 const timer=setTimeout(abort,Math.max(1,(deadline-now())*1000));const rows=[];let calls=0;
 try{
  for(const probe of MICROPROBES){
   if(controller.signal.aborted||now()>=deadline)break;
   await beforeProbe(probe.id);let seeded=false,captured=false,semanticChoice=false,probeCalls=0;
   const wrapped={async invoke(request,callSignal){
    if(probe.id==='postPatch'&&!seeded){seeded=true;return {kind:'TOOL_PROPOSAL',capability:'worktree_edit',arguments:{path:'index.js',old_text:'old',new_text:'synthetic host seed; no filesystem effect'}};}
    if(controller.signal.aborted||now()>=deadline)throw Error('microprobe_deadline');
    if(calls>=(experiment?5:6)||probeCalls>=2)throw Error('microprobe_call_limit');calls++;probeCalls++;
    return reasoner.invoke(request,callSignal);
   }};
   const work=createWorkMode({reasoner:wrapped,manifest,completionPolicy:MUTABLE_WORKTREE_COMPLETION_POLICY,
    workspaceState:async({scope,workspace,turn})=>({schema:WORKSPACE_EVIDENCE_VERSION,scope,workspace,turn,diff:{ok:true,executionState:'COMPLETED',bytes:0,digest:'b'.repeat(64)},status:{ok:true,executionState:'COMPLETED',bytes:0,digest:'c'.repeat(64)}}),
    authorize:(proposal,spec,boundScope)=>({schema:CONTRACT_VERSION,outcome:proposal.arguments.task_id===boundScope?'ALLOW':'DENY',capability:proposal.capability,proposalDigest:digest(proposal),scope:boundScope,effect:spec.policy.effect,source:'MAC_GATE',reasonCodes:['WORK_TASK_BINDING'],expires:null,oneUse:false}),
    invoke:async({proposal})=>{
     if(probe.id==='postPatch'&&probeCalls===0&&proposal.capability==='worktree_edit')return {ok:true,executionState:'COMPLETED',verifier:'VERIFIED'};
     captured=true;semanticChoice=probe.id==='inspection'?proposal.capability==='worktree_read'&&proposal.arguments.path==='index.js':probe.id==='postPatch'&&proposal.capability==='worktree_command'&&proposal.arguments.operation==='test';
     return {ok:true,executionState:'COMPLETED',verifier:'VERIFIED'};
    },
    egress:({claim})=>({schema:CONTRACT_VERSION,outcome:'ALLOW',...claim,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['EXACT_WORK_TASK_EGRESS']}),
    evaluate:async()=>({passed:false}),
    budgetStatus:()=>captured?'MICROPROBE_CAPTURED':null,
    onEvent:(kind,value)=>onEvent(probe.id,kind,value),
   });
   const result=await work.run({task:probe.task,scope,capabilities:['worktree_list','worktree_read','worktree_edit','worktree_command'],maxModelCalls:probe.id==='postPatch'?3:2,maxTaskSeconds:Math.max(1,Math.min(maxSeconds,deadline-now())),signal:controller.signal});
   const passed=probe.id==='inability'?result.reason==='MODEL_ESCALATION'&&!captured:captured&&semanticChoice&&result.reason==='MICROPROBE_CAPTURED';
   rows.push({id:probe.id,passed,semanticChoice:probe.id==='inability'?passed:semanticChoice,hostBoundary:probe.id==='inability'?'TERMINAL_FRESHNESS':'CANONICAL_AND_AUTHORITY',calls:probeCalls,hostSeededPatch:seeded,status:result.status,reason:result.reason});
   if(!passed)break;
  }
  return {schema:'sanctum-protocol-microprobe/v1',synthetic:true,agenticTaskCompletion:false,passed:rows.length===3&&rows.every(x=>x.passed),calls,rows};
 }finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===resolve(process.argv[1])){
 console.error('REFUSED: no live CLI; use the offline signed-worker regression or a separately reviewed installed caller.');process.exitCode=1;
}
