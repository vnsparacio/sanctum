import { readFileSync,lstatSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { createGate,createExecutor } from './core.mjs';
import { createLocalAgent } from './local-agent.mjs';
import { createSourceRetrieval } from './source-retrieval.mjs';
import { createWorkCommand } from './work-command.mjs';
import {boundedShutdown,gatewayObservability} from './observability.mjs';
import { currentCapabilityManifest } from '../foundation/manifest.mjs';
import {CONTENT_TELEMETRY_DEFAULTS} from '../content-telemetry/contract.mjs';
import {createContentTelemetrySpool} from '../content-telemetry/spool.mjs';
export default {
  id:'hybrid-ai-prompt-gate',name:'Mac privacy-first hybrid gate',
  register(api){
    const base=resolve(fileURLToPath(new URL('.',import.meta.url)),'..');
    for(const [name,expected] of Object.entries(JSON.parse(readFileSync(resolve(base,'FREEZE.json'),'utf8')))){
      const path=resolve(base,name);if(!path.startsWith(base+'/')||lstatSync(path).isSymbolicLink()||createHash('sha256').update(readFileSync(path)).digest('hex')!==expected)throw Error('Mac gate integrity check failed');
    }
    const raw=readFileSync(resolve(base,'SETTINGS.json'),'utf8'),settings=JSON.parse(raw);
    settings.settingsFileHash=createHash('sha256').update(raw).digest('hex');
    const observability=gatewayObservability({gitCommit:process.env.SANCTUM_GIT_COMMIT});
    const path=resolve(settings.state_directory,'authority.key');if(lstatSync(path).isSymbolicLink()||(lstatSync(path).mode&0o077))throw Error('Invalid authority key');
    const key=readFileSync(path),remote=createExecutor(base,settings,key);
    const local=createLocalAgent({getConfig:()=>api.runtime.config.current(),localModel:settings.local_model});
    const contentTelemetry=createContentTelemetrySpool({config:settings.content_telemetry??CONTENT_TELEMETRY_DEFAULTS,root:resolve(settings.state_directory,'..','telemetry','content')});
    contentTelemetry.recover();
    const invokeWeb=async(name,args,proposal)=>{
      const cfg=api.runtime.config.current(), gateway=cfg.gateway;
      if(gateway?.bind!=='loopback'||gateway?.auth?.mode!=='token'||!gateway.auth.token)throw Error('source_runtime_unavailable');
      const response=await fetch(`http://127.0.0.1:${gateway.port}/tools/invoke`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+gateway.auth.token},body:JSON.stringify({name,args,sessionKey:'agent:main:mac-source-'+proposal.requestId.slice(0,32)})});
      const body=await response.json();if(!response.ok||body?.ok!==true)throw Error('source_tool_failed');
      return body.result?.details??body.result;
    };
    let retrieval=null;
    const gate=createGate({settings,key,observability,contentTelemetry,execute:(body,signal)=>body.operation==='answer_local'?local(body,signal):remote(body,signal),retrieve:request=>{retrieval??=createSourceRetrieval({manifest:currentCapabilityManifest(),invoke:invokeWeb});return retrieval.retrieve(request);}});
    api.registerCommand({name:'gate',description:'Mac-owned hybrid reasoning with exact disclosure approvals',acceptsArgs:true,requireAuth:true,requiredScopes:['operator.admin'],handler:gate});
    const work=createWorkCommand({api,base,settings,key,remote});
    api.registerCommand({name:'work',description:'Owner-selected bounded PRIVATE_LEAD Work Mode',acceptsArgs:true,requireAuth:true,requiredScopes:['operator.admin'],handler:work});
    // A separate launch agent also sweeps after gateway crashes. This timer makes
    // ordinary operation independent of UI polling.
    let sweeping=false;
    const timer=setInterval(async()=>{if(sweeping)return;sweeping=true;try{await gate.sweep();}finally{sweeping=false;}},30000);timer.unref();
    api.on('gateway_stop',async()=>{clearInterval(timer);await gate.close();await boundedShutdown(observability);});
  }
};
