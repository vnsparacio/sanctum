import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createWorkCommand} from '../plugin/work-command.mjs';
import {deriveCapabilityManifest,publishCapabilityManifest} from '../foundation/manifest.mjs';
import {workModeTools} from '../plugin/workspace-tools.mjs';
import {syntheticProtection} from './fixtures/task-evidence.mjs';

test('owner-selected Qwen profile uses headless worker, then Sanctum evaluates and reviews',async()=>{
 const names=workModeTools.map(tool=>tool.name);
 publishCapabilityManifest(deriveCapabilityManifest({schemas:workModeTools,declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}}));
 const base=resolve(import.meta.dirname,'..'),original=JSON.parse(fs.readFileSync(join(base,'SETTINGS.json')));
 const root=fs.mkdtempSync(join(tmpdir(),'qwen-work-command-'));fs.chmodSync(root,0o700);
 const profileFile=join(root,'profiles.json');
 fs.writeFileSync(profileFile,JSON.stringify({schema:'sanctum-work-mode-profiles/v1',profiles:{qwen:{engine:'qwen_code',qwen_runner_image_id:'sha256:'+'a'.repeat(64),reviewer:true,evaluators:['test'],max_cost_usd:10,max_gpu_seconds:2700,qwen_model_calls:48,qwen_tool_calls:40,qwen_wall_seconds:1200,qwen_outer_seconds:2400,qwen_retries:0}}}),{mode:0o600});
 const settings={...original,work_mode:{enabled:true,profile_file:profileFile,ledger_root:join(root,'ledger')}};
 const calls=[];
 const remote=async body=>{
  calls.push(body.operation);
  if(body.operation==='worktree_create')return {status:'OK',workspace:{base_commit:'c'.repeat(40),initial_status:'CLEAN',disk_bytes:1}};
  if(body.operation==='worktree_integrity')return {status:'OK',result:await syntheticProtection({scope:body.scope})};
  if(body.operation==='worktree_qwen_run')return {status:'OK',result:{schema:'sanctum-qwen-run/v1',taskId:body.scope,ok:true,code:'OK',containerAbsent:true,modelCalls:37,inferenceSeconds:120,estimatedCostUsd:0.4,elapsedSeconds:500,importReceipt:{paths:['index.js'],authorityResult:'ALLOW',candidateDigest:'a'.repeat(64),patchDigest:'b'.repeat(64)}}};
  if(body.operation==='worktree_command')return {status:'OK',result:{ok:true,code:'OK',executionState:'COMPLETED',output_digest:'d'.repeat(64),output_bytes:1,output:'change',elapsed_ms:1}};
  if(body.operation==='private_lead_propose')return {status:'OK',result:{kind:'FINAL',text:JSON.stringify({verdict:'ACCEPT',findings:[]})},telemetry:{prompt_tokens:1,completion_tokens:1,elapsed_seconds:0.01}};
  if(body.operation==='close')return {status:'OK',gpu:{phase:'OFFLINE'}};
  if(body.operation==='worktree_cleanup')return {status:'OK'};
  throw Error('unexpected '+body.operation);
 };
 const work=createWorkCommand({base,settings,key:Buffer.alloc(32),remote,api:{runtime:{config:{current:()=>({gateway:{bind:'loopback',port:1,auth:{mode:'token',token:'synthetic'}}})}}}});
 try{
  const ctx={isAuthorizedSender:true,gatewayClientScopes:['operator.admin'],sessionKey:'synthetic-qwen'};
  const started=await work({...ctx,args:'start qwen -- Fix MoodLog'});assert.match(started.text,/started in an isolated workspace/);
  let status;
  for(let i=0;i<100;i++){await new Promise(setImmediate);status=await work({...ctx,args:'status'});if(status.text.includes('TERMINAL'))break;}
  assert.match(status.text,/status COMPLETE/);
  assert.equal(calls.filter(x=>x==='worktree_qwen_run').length,1);
  assert.equal(calls.filter(x=>x==='private_lead_propose').length,1);
  assert.equal(calls.includes('worktree_acceptance'),false);
  const task=fs.readdirSync(settings.work_mode.ledger_root)[0];
  const summary=JSON.parse(fs.readFileSync(join(settings.work_mode.ledger_root,task,'summary.json')));
  assert.equal(summary.status,'COMPLETE');assert.equal(summary.reason,'QWEN_ACCEPTED');
  assert.equal(summary.telemetry.modelCalls,38);
 }finally{await work.close();fs.rmSync(root,{recursive:true,force:true});}
});
