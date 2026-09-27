#!/usr/bin/env node
/* Local-only report from bounded private receipts. No server or external assets. */
import {openSync,closeSync,readSync,writeFileSync,lstatSync,fstatSync,realpathSync,renameSync,unlinkSync,constants} from 'node:fs';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomBytes,createHash} from 'node:crypto';
import {canonical} from '../gate/foundation/contracts.mjs';
import {NOTE_FIELDS} from '../gate/foundation/decision-note.mjs';
const escape=value=>String(value??'—').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
function readPrivate(path,limit,optional=false){
 let fd;
 try{fd=openSync(path,constants.O_RDONLY|constants.O_NOFOLLOW);}catch(error){if(optional&&error.code==='ENOENT')return '';throw Error('timeline_input_unavailable');}
 try{
  const stat=fstatSync(fd);
  if(!stat.isFile()||stat.uid!==process.getuid()||(stat.mode&0o077)||stat.size>limit)throw Error('timeline_input_unsafe');
  const buffer=Buffer.alloc(limit+1);let count=0,n;
  while(count<buffer.length&&(n=readSync(fd,buffer,count,buffer.length-count,null))>0)count+=n;
  if(count>limit)throw Error('timeline_input_limit');return buffer.subarray(0,count).toString('utf8');
 }finally{closeSync(fd);}
}
function parseRows(raw,maximum){const rows=raw.trim()?raw.trimEnd().split('\n'):[];if(rows.length>maximum)throw Error('timeline_row_limit');return rows.map(row=>JSON.parse(row));}
export function renderTimeline(events,notes){
 if(!events.length||events.length>4096||notes.length>128)throw Error('timeline_row_limit');
 const task=events[0].taskId;if(!/^[a-f0-9]{32}$/.test(task))throw Error('timeline_identity');
 let previous='0'.repeat(64);
 for(let index=0;index<events.length;index++){
  const {eventDigest,...row}=events[index];
  if(row.schema!=='sanctum-work-ledger/v1'||row.taskId!==task||row.sequence!==index||row.previousDigest!==previous||createHash('sha256').update(canonical(row)).digest('hex')!==eventDigest)throw Error('timeline_receipt_integrity');
  previous=eventDigest;
 }
 for(let index=0;index<notes.length;index++){const row=notes[index];if(row.schema!=='sanctum-work-trace/v1'||row.taskId!==task||row.sequence!==index||row.untrustedModelExplanation!==true)throw Error('timeline_trace_identity');}
 const table=events.map(row=>`<tr><td>${row.sequence}</td><td>${escape(row.checkpoint)}</td><td>${escape(row.iteration)}</td><td>${escape(row.kind)}</td><td>${escape([row.role,row.capability,row.operation,row.selectedResultKind,row.outcome,row.status,row.reason,row.errorCode,row.verdict,row.validationCode,row.eligibilityReason].filter(Boolean).join(' · '))}</td><td>${escape(row.prompt_tokens??'—')} / ${escape(row.completion_tokens??'—')}</td><td>${escape(row.elapsed_seconds??row.elapsedSeconds??'—')}</td></tr>`).join('');
 const explanations=notes.map(row=>`<article><h3>Checkpoint ${escape(row.checkpoint)} · turn ${escape(row.iteration)} · ${escape(row.role)}</h3>${row.type==='DECISION'?`<p>Note status: ${escape(row.status)}</p><dl>${NOTE_FIELDS.map(key=>`<dt>${escape(key)}</dt><dd>${escape(row.note?.[key])}</dd>`).join('')}</dl>`:`<p>Reviewer verdict: ${escape(row.verdict)}</p><ul>${(Array.isArray(row.findings)?row.findings:[]).slice(0,16).map(finding=>`<li>${['severity','locator','checkCode','summary'].map(key=>escape(String(finding?.[key]??'').slice(0,240))).join(' · ')}</li>`).join('')}</ul>`}</article>`).join('');
 return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Work Mode timeline</title><style>body{font:16px system-ui;margin:2rem;color:#17202b;background:#f6f8fa}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:.5rem;text-align:left;border-bottom:1px solid #ccd3dc;vertical-align:top}article{padding:1rem;background:white;border:1px solid #ccd3dc;margin:1rem 0}dd{white-space:pre-wrap;overflow-wrap:anywhere;margin-bottom:.6rem}dt{font-weight:bold}.scroll{overflow:auto}</style><h1>Work Mode timeline</h1><p>Task ${escape(task)}</p><p>Receipt chain verified for ${events.length} records. This proves internal consistency, not authenticity against rewriting or task correctness. ${events.some(row=>row.kind==='STOP')?'A stop record is present.':'No stop record: this may be a partial run.'}</p><h2>Model-written explanations</h2><p>Untrusted summaries, not hidden reasoning or evidence of correctness. Explanations are separate from the receipt chain and never authorize actions. Missing notes are not reconstructed. Turn numbers restart at each checkpoint.</p>${explanations||'<p>No explanation records are available.</p>'}<h2>Host event sequence</h2><div class="scroll"><table><thead><tr><th>Event</th><th>Checkpoint</th><th>Turn</th><th>Kind</th><th>Outcome / detail</th><th>Input / output tokens</th><th>Seconds</th></tr></thead><tbody>${table}</tbody></table></div></html>`;
}
export function writeTimeline(directory){
 const root=resolve(directory),stat=lstatSync(root);
 if(realpathSync(root)!==root||stat.isSymbolicLink()||!stat.isDirectory()||stat.uid!==process.getuid()||(stat.mode&0o077))throw Error('timeline_directory_unsafe');
 const events=parseRows(readPrivate(join(root,'events.jsonl'),8*1024*1024),4096);
 const notes=parseRows(readPrivate(join(root,'decision-trace.jsonl'),256*1024,true),128);
 const html=renderTimeline(events,notes),output=join(root,'timeline.html'),temporary=output+'.'+randomBytes(8).toString('hex')+'.tmp';
 const fd=openSync(temporary,constants.O_CREAT|constants.O_EXCL|constants.O_WRONLY|constants.O_NOFOLLOW,0o600);
 try{writeFileSync(fd,html);renameSync(temporary,output);}finally{closeSync(fd);try{unlinkSync(temporary);}catch(error){if(error.code!=='ENOENT')throw error;}}
 return output;
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===resolve(process.argv[1])){
 try{if(process.argv.length!==4||process.argv[2]!=='--task-dir')throw Error('usage');console.log(writeTimeline(process.argv[3]));}
 catch{console.error('Timeline unavailable: use --task-dir with an owner-private task directory containing valid, bounded receipts. No report was written.');process.exitCode=1;}
}
