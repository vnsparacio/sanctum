/* Host-owned runner. Candidate output is data, never execution proof. */
'use strict';
const fs=require('node:fs');
const crypto=require('node:crypto');
const {run}=require('node:test');
const path=require('node:path');
require('/sanctum-acceptance/protected-test-preload.cjs');
const entries=JSON.parse(process.argv[2]);
const secret=fs.readFileSync(0,'utf8').trim();
if(!/^[0-9a-f]{64}$/.test(secret))process.exit(1);
const key=Buffer.from(secret,'hex');
const write=fs.writeSync.bind(fs);
const stringify=JSON.stringify.bind(JSON);
const bufferFrom=Buffer.from.bind(Buffer);
const bufferText=Function.call.bind(Buffer.prototype.toString);
const signer=crypto.createHmac('sha256',key);
const signerUpdate=signer.update.bind(signer);
const signerDigest=signer.digest.bind(signer);
(async()=>{
 const expected=[];
 for(let i=0;i<entries.length;i++)for(let j=0;j<entries[i].names.length;j++)expected.push(Object.assign(Object.create(null),{file:path.resolve('/workspace',entries[i].path),name:entries[i].names[j],started:0,completed:0,passed:0,skipped:0}));
 let failures=0,skipped=0,observed=0;
 const files=[];for(let i=0;i<entries.length;i++)files.push(path.resolve('/workspace',entries[i].path));
 for await(const event of run({files,isolation:'none',concurrency:1,cwd:'/workspace'})){
  const d=event.data;
  if(event.type==='test:fail')failures++;
  let state=null;for(let i=0;i<expected.length;i++)if(expected[i].file===d.file&&expected[i].name===d.name){state=expected[i];break;}
  if(state){
   if(event.type==='test:start')state.started++;
   if(event.type==='test:complete'){
    state.completed++;observed++;
    if(d.skip||d.todo){state.skipped++;skipped++;}
    else if(d.details?.passed===true)state.passed++;
   }
  }
 }
 let executed=true,passed=true;
 for(let i=0;i<expected.length;i++){const s=expected[i];if(s.started!==1||s.completed!==1||s.skipped!==0)executed=false;if(s.passed!==1)passed=false;}
 passed=executed&&passed&&failures===0&&skipped===0;
 const payload=bufferFrom(stringify({schema:'sanctum-protected-test-run/v1',executed,passed,observed,failures,skipped}));
 signerUpdate(payload);const mac=signerDigest('hex');
 write(2,bufferFrom('\nSANCTUM_PROTECTED_PROOF_V1 '+bufferText(payload,'base64')+' '+mac+'\n'));
 process.exitCode=passed?0:1;
})().catch(()=>{process.exitCode=1;});
