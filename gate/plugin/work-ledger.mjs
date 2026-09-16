/* Owner-only, payload-free, hash-chained Work Mode receipts. */
import {appendFileSync,chmodSync,existsSync,lstatSync,mkdirSync,openSync,closeSync,readFileSync,renameSync,writeFileSync} from 'node:fs';
import {createHash,createHmac} from 'node:crypto';
import {join,resolve} from 'node:path';
import {canonical,digest} from '../foundation/contracts.mjs';

const allowed=new Set(['TASK_CREATED','WORKSPACE_CREATED','PHASE','MODEL_CALL','PROPOSAL','AUTHORITY','EXECUTION','EGRESS','EVALUATOR','REVIEW_EGRESS','REVIEWER','STOP','CLEANUP']);
const safeId=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
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
 if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).slice(0,64).filter(([key])=>!/(?:^goal$|prompt|content|output|text|body|secret|token|path)/i.test(key)).map(([key,item])=>[key,clean(item)]));
 return null;
}
export function createWorkLedger({root,taskId,key,metadata={},now=()=>Date.now()/1000}){
 if(!safeId(taskId)||!Buffer.isBuffer(key)||key.length<32)throw Error('work_ledger_config');
 const directory=privateDir(join(root,taskId)),events=join(directory,'events.jsonl'),summary=join(directory,'summary.json');
 if(existsSync(events)||existsSync(summary))throw Error('work_ledger_exists');
 const fd=openSync(events,'wx',0o600);closeSync(fd);let previousDigest='0'.repeat(64),sequence=0;
 const goalHmac=createHmac('sha256',key).update(String(metadata.goal??'')).digest('hex');
 function event(kind,fields={}){
   if(!allowed.has(kind))throw Error('work_ledger_event');
   const base={schema:'sanctum-work-ledger/v1',taskId,sequence:sequence++,time:now(),kind,previousDigest,...clean(fields)};
   const eventDigest=createHash('sha256').update(canonical(base)).digest('hex'),row={...base,eventDigest};
   appendFileSync(events,canonical(row)+'\n',{encoding:'utf8',mode:0o600});previousDigest=eventDigest;return eventDigest;
 }
 event('TASK_CREATED',{goalHmac,profile:metadata.profile,reasonerRelease:metadata.reasonerRelease,manifestDigest:metadata.manifestDigest});
 let final={};
 function snapshot(value={}){final={...final,...clean(value)};const rows=readFileSync(events,'utf8').trim().split('\n').filter(Boolean);atomic(summary,canonical({schema:'sanctum-work-summary/v1',taskId,goalHmac,events:rows.length,finalDigest:previousDigest,...final})+'\n');return {events:rows.length,finalDigest:previousDigest};}
 return Object.freeze({directory,event,modelCall:value=>event('MODEL_CALL',value),finish(value){event('STOP',value);return snapshot(value);},cleanup(value){event('CLEANUP',value);return snapshot({cleanup:value});}});
}
