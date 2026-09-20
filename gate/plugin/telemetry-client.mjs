/* Best-effort bridge to the existing private Core telemetry writer. */
import {spawnSync} from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import {currentTraceContext} from './observability.mjs';

const safeId=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$/.test(value)?value:null;
const safeTrace=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value)?value:null;
const safeSpan=value=>typeof value==='string'&&/^[a-f0-9]{16}$/.test(value)?value:null;
const command=env=>env.SANCTUM_TELEMETRY_COMMAND??path.join(os.homedir(),'.sanctum/telemetry/bin/sanctum-telemetry');
const root=env=>env.SANCTUM_TELEMETRY_ROOT??path.join(os.homedir(),'.sanctum/telemetry');

export function createOperationalEmitter({env=process.env,spawn=spawnSync,contextProvider=currentTraceContext}={}){
 return function emitOperational({eventType,component,outcome,payload={},runId=null,taskId=null,sessionId=null,workspaceId=null,model=null,modelRole=null,provider=null,durationMs=null,inputTokens=null,outputTokens=null}={}){
  if(env.SANCTUM_TELEMETRY_DISABLE==='1')return false;
  try{
   const active=contextProvider(),traceId=safeTrace(active?.traceId),spanId=safeSpan(active?.spanId);
   const args=['--root',root(env),'emit','--event-type',eventType,'--component',component,'--outcome',outcome,'--payload-json',JSON.stringify(payload)];
   for(const [flag,value] of [['--run-id',runId],['--task-id',taskId],['--session-id',sessionId],['--workspace-id',workspaceId],['--model',model],['--model-role',modelRole],['--provider',provider]])if(safeId(value))args.push(flag,value);
   if(traceId)args.push('--trace-id',traceId);if(spanId)args.push('--span-id',spanId);
   for(const [flag,value] of [['--duration-ms',durationMs],['--input-tokens',inputTokens],['--output-tokens',outputTokens]])if(Number.isSafeInteger(value)&&value>=0)args.push(flag,String(value));
   const childEnv={HOME:os.homedir(),PATH:env.PATH??'/usr/bin:/bin',SANCTUM_TELEMETRY_INTERNAL:'1'};
   const result=spawn(command(env),args,{stdio:'ignore',timeout:1000,env:childEnv});
   return result.status===0;
  }catch{return false;}
 };
}

export const emitOperational=createOperationalEmitter();
