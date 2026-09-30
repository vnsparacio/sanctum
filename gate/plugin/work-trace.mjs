/* Owner-only explanatory content. Failure here never authorizes or blocks work. */
import {openSync,writeSync,closeSync,lstatSync,constants} from 'node:fs';
import {join} from 'node:path';
import {redactContentText} from '../content-telemetry/redaction.mjs';
import {NOTE_FIELDS,validDecisionNote} from '../foundation/decision-note.mjs';
export const TRACE_MAX_BYTES=256*1024;
export const TRACE_MAX_RECORDS=128;
const text=value=>typeof value==='string'?redactContentText(value.slice(0,4096)).replace(/-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----[\s\S]*/g,'[REDACTED:PRIVATE_KEY]').replace(/[\u0000-\u001f\u007f-\u009f]/g,' ').slice(0,240):'';
export function readableFindings(value){
 return Array.isArray(value)?value.slice(0,16).map(row=>({severity:text(row?.severity),locator:text(row?.locator),checkCode:text(row?.checkCode),summary:text(row?.summary)})):[];
}
export function createWorkTrace({directory,taskId,now=()=>Date.now()/1000}){
 let fd=null,bytes=0,records=0,state='ACTIVE';
 try{
  const stat=lstatSync(directory);
  if(!/^[a-f0-9]{32}$/.test(taskId)||stat.isSymbolicLink()||!stat.isDirectory()||stat.uid!==process.getuid()||(stat.mode&0o077))throw Error('unsafe_trace');
  fd=openSync(join(directory,'decision-trace.jsonl'),constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o600);
 }catch{state='UNAVAILABLE';}
 function close(){if(fd!==null){try{closeSync(fd);}catch{}fd=null;}if(state==='ACTIVE')state='CLOSED';}
 function append({checkpoint=1,iteration=0,role='IMPLEMENTER',type,note,status,verdict,findings}){
  if(state!=='ACTIVE'||fd===null)return;
  try{
   if(!Number.isSafeInteger(checkpoint)||checkpoint<1||checkpoint>3||!Number.isSafeInteger(iteration)||iteration<0||iteration>32||!['IMPLEMENTER','REVIEWER'].includes(role))throw Error('trace_identity');
   let content;
   if(type==='DECISION')content={status:status==='RECORDED'&&validDecisionNote(note)?'RECORDED':status==='MISSING'?'MISSING':'INVALID',note:validDecisionNote(note)?Object.fromEntries(NOTE_FIELDS.map(key=>[key,text(note[key])])):null};
   else if(type==='REVIEW'&&['ACCEPT','REVISE','REJECT'].includes(verdict))content={verdict,findings:readableFindings(findings)};
   else throw Error('trace_shape');
   const row={schema:'sanctum-work-trace/v1',taskId,sequence:records,time:now(),checkpoint,iteration,role,type,untrustedModelExplanation:true,...content};
   const buffer=Buffer.from(JSON.stringify(row)+'\n');
   if(records>=TRACE_MAX_RECORDS||bytes+buffer.length>TRACE_MAX_BYTES){state='LIMIT_REACHED';close();return;}
   let offset=0;while(offset<buffer.length){const count=writeSync(fd,buffer,offset,buffer.length-offset);if(count<=0)throw Error('trace_write');offset+=count;}
   records++;bytes+=buffer.length;
  }catch{state='UNAVAILABLE';close();}
 }
 return Object.freeze({append,close,status:()=>({state,records,bytes})});
}
