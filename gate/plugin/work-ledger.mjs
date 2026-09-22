/* Owner-only, payload-free, hash-chained Work Mode receipts. */
import {appendFileSync,chmodSync,existsSync,lstatSync,mkdirSync,openSync,closeSync,readFileSync,renameSync,writeFileSync} from 'node:fs';
import {createHash,createHmac} from 'node:crypto';
import {join,resolve} from 'node:path';
import {sanitizeProtocolDiagnostic} from '../foundation/protocol-diagnostics.mjs';
import {canonical,digest} from '../foundation/contracts.mjs';

const allowed=new Set(['EDIT','EDIT_RECOVERY','EDIT_RETRY_BLOCKED','PROTECTED_EVIDENCE','PROTOCOL_DIAGNOSTIC','TASK_CREATED','WORKSPACE_CREATED','PHASE','SEMANTIC_SURFACE','MODEL_CALL','PROPOSAL','AUTHORITY','EXECUTION','EGRESS','EVALUATOR','REVIEW_EGRESS','REVIEWER','STOP','CLEANUP']);
const safeId=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
const safeLabel=value=>typeof value==='string'&&/^[A-Z][A-Z0-9_.:-]{0,79}$/.test(value);
const safeDigest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const oneOf=(value,allowed)=>allowed.includes(value);
function privateDir(path){
 const parent=resolve(path);mkdirSync(parent,{recursive:true,mode:0o700});
 if(lstatSync(parent).isSymbolicLink()||(lstatSync(parent).mode&0o077))throw Error('unsafe_work_ledger');
 return parent;
}
function atomic(path,value){const tmp=path+'.tmp';writeFileSync(tmp,value,{mode:0o600,flag:'wx'});chmodSync(tmp,0o600);renameSync(tmp,path);}
function clean(value){
 if(value===null||typeof value==='boolean'||typeof value==='number')return value;
 if(typeof value==='string')return value.length<=160&&/^[A-Za-z0-9_.:@/+ -]*$/.test(value)?value:digest({value});
 if(Array.isArray(value))return value.slice(0,32).map(clean);
 if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).slice(0,64).filter(([key])=>!/(?:^goal$|prompt|content|^output$|outputText|text|body|secret|token|path|diagnostic)/i.test(key)).map(([key,item])=>[key,clean(item)]));
 return null;
}
export function sanitizeSemanticSurface(value){
 if(!value||typeof value!=='object'||Array.isArray(value))throw Error('work_ledger_surface');
 const strings=['phase','stage','decisionState','eligibilityReason','completionPolicy','latestTestState','evaluatorState','evaluationTrigger','selectedResultKind','validationCode','reviewDisposition'];
 if(strings.some(key=>!safeLabel(value[key])))throw Error('work_ledger_surface');
 if(!oneOf(value.stage,['REQUEST','RESULT'])||!oneOf(value.phase,['PLAN'])||!oneOf(value.decisionState,['WORK_REQUIRED','TEST_REQUIRED','COMPLETION_ELIGIBLE'])||!oneOf(value.completionPolicy,['MUTABLE_WORKTREE_V1']))throw Error('work_ledger_surface');
 if(!oneOf(value.eligibilityReason,['HOST_STOP_ACTIVE','EXECUTION_UNCERTAIN','WORKSPACE_EVIDENCE_UNAVAILABLE','POST_PATCH_TEST_REQUIRED','NO_COMPLETABLE_DIFF','NO_WORKTREE_CHANGES','ELIGIBLE_FOR_FRESH_EVALUATION']))throw Error('work_ledger_surface');
 if(!oneOf(value.latestTestState,['NOT_RUN','PASS','FAIL','STALE'])||!oneOf(value.evaluatorState,['NOT_RUN','RUNNING','PASS','FAIL','STALE'])||!oneOf(value.evaluationTrigger,['NONE','FINAL','HOST_TEST_PASSED']))throw Error('work_ledger_surface');
 if(!oneOf(value.selectedResultKind,['PENDING','REJECTED','UNKNOWN','TOOL_PROPOSAL','FINAL','ESCALATION'])||!oneOf(value.reviewDisposition,['NOT_CONFIGURED','NOT_RUN','ACCEPT','REVISE','REJECT']))throw Error('work_ledger_surface');
 if(typeof value.completionEligible!=='boolean'||typeof value.postPatchTestOutstanding!=='boolean'||!Number.isSafeInteger(value.iteration)||value.iteration<0||!Number.isSafeInteger(value.modelCalls)||value.modelCalls<0||!Number.isSafeInteger(value.workspaceGeneration)||value.workspaceGeneration<0)throw Error('work_ledger_surface');
 if(!safeDigest(value.schemaDigest)||!safeDigest(value.semanticSchemaDigest)||!safeDigest(value.snapshotDigest)||typeof value.schemaVersion!=='string'||value.schemaVersion!=='sanctum-work-intent/v1')throw Error('work_ledger_surface');
 if(!Array.isArray(value.terminalKinds)||value.terminalKinds.some(x=>!oneOf(x,['FINAL','ESCALATION']))||new Set(value.terminalKinds).size!==value.terminalKinds.length)throw Error('work_ledger_surface');
 if(!Array.isArray(value.visibleCapabilities)||value.visibleCapabilities.some(x=>typeof x!=='string'||!/^[a-z][a-z0-9_]{0,63}$/.test(x)))throw Error('work_ledger_surface');
 return Object.fromEntries(['phase','iteration','modelCalls','stage','decisionState','completionEligible','eligibilityReason','completionPolicy','schemaVersion','schemaDigest','semanticSchemaDigest','terminalKinds','visibleCapabilities','workspaceGeneration','snapshotDigest','postPatchTestOutstanding','latestTestState','evaluatorState','evaluationTrigger','selectedResultKind','validationCode','reviewDisposition'].map(key=>[key,structuredClone(value[key])]));
}
export function sanitizeProtectedEvidence(value){
 if(!value||typeof value!=='object'||Array.isArray(value)||!oneOf(value.stage,['TASK_CREATED','BEFORE_EVALUATION','AFTER_EVALUATION','BEFORE_COMPLETE','EVALUATION'])||!oneOf(value.integrity,['PASS','FAIL']))throw Error('work_ledger_protection');
 const out={stage:value.stage,integrity:value.integrity};
 for(const key of ['snapshotDigest','contractDigest','candidateDigest']){
  if(key==='contractDigest'&&value.stage==='EVALUATION'&&value[key]===undefined)continue;
  if(key==='candidateDigest'&&value.integrity==='FAIL'&&value[key]===null){out[key]=null;continue;}
  if(!safeDigest(value[key]))throw Error('work_ledger_protection');out[key]=value[key];
 }
 for(const key of ['acceptanceRequired',...(value.stage==='EVALUATION'?['originalExecuted','originalPassed','candidateExecuted','candidatePassed']:[])]){
  if(typeof value[key]!=='boolean')throw Error('work_ledger_protection');out[key]=value[key];
 }
 return out;
}
export function createWorkLedger({root,taskId,key,metadata={},now=()=>Date.now()/1000}){
 if(!safeId(taskId)||!Buffer.isBuffer(key)||key.length<32)throw Error('work_ledger_config');
 const directory=privateDir(join(root,taskId)),events=join(directory,'events.jsonl'),summary=join(directory,'summary.json');
 if(existsSync(events)||existsSync(summary))throw Error('work_ledger_exists');
 const fd=openSync(events,'wx',0o600);closeSync(fd);let previousDigest='0'.repeat(64),sequence=0;
 const goalHmac=createHmac('sha256',key).update(String(metadata.goal??'')).digest('hex');
 function event(kind,fields={}){
   if(!allowed.has(kind))throw Error('work_ledger_event');
   const sanitized=kind==='PROTECTED_EVIDENCE'?sanitizeProtectedEvidence(fields):kind==='PROTOCOL_DIAGNOSTIC'?{diagnostic:sanitizeProtocolDiagnostic(fields.diagnostic),schemaDigest:safeDigest(fields.schemaDigest)?fields.schemaDigest:null,semanticSchemaDigest:safeDigest(fields.semanticSchemaDigest)?fields.semanticSchemaDigest:null}:kind==='SEMANTIC_SURFACE'?sanitizeSemanticSurface(fields):clean(fields);
   const base={schema:'sanctum-work-ledger/v1',taskId,sequence:sequence++,time:now(),kind,previousDigest,...sanitized};
   const eventDigest=createHash('sha256').update(canonical(base)).digest('hex'),row={...base,eventDigest};
   appendFileSync(events,canonical(row)+'\n',{encoding:'utf8',mode:0o600});previousDigest=eventDigest;return eventDigest;
 }
 event('TASK_CREATED',{goalHmac,profile:metadata.profile,reasonerRelease:metadata.reasonerRelease,manifestDigest:metadata.manifestDigest});
 let final={};
 function snapshot(value={}){final={...final,...clean(value)};const rows=readFileSync(events,'utf8').trim().split('\n').filter(Boolean);atomic(summary,canonical({schema:'sanctum-work-summary/v1',taskId,goalHmac,events:rows.length,finalDigest:previousDigest,...final})+'\n');return {events:rows.length,finalDigest:previousDigest};}
 return Object.freeze({directory,event,modelCall:value=>event('MODEL_CALL',value),finish(value){event('STOP',value);return snapshot(value);},cleanup(value){event('CLEANUP',value);return snapshot({cleanup:value});}});
}
