import { readFileSync,lstatSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { createGate,createExecutor } from './core.mjs';
import { createLocalAgent } from './local-agent.mjs';
export default {
  id:'hybrid-ai-prompt-gate',name:'Mac privacy-first hybrid gate',
  register(api){
    const base=resolve(fileURLToPath(new URL('.',import.meta.url)),'..');
    for(const [name,expected] of Object.entries(JSON.parse(readFileSync(resolve(base,'FREEZE.json'),'utf8')))){
      const path=resolve(base,name);if(!path.startsWith(base+'/')||lstatSync(path).isSymbolicLink()||createHash('sha256').update(readFileSync(path)).digest('hex')!==expected)throw Error('Mac gate integrity check failed');
    }
    const raw=readFileSync(resolve(base,'SETTINGS.json'),'utf8'),settings=JSON.parse(raw);
    settings.settingsFileHash=createHash('sha256').update(raw).digest('hex');
    const path=resolve(settings.state_directory,'authority.key');if(lstatSync(path).isSymbolicLink()||(lstatSync(path).mode&0o077))throw Error('Invalid authority key');
    const key=readFileSync(path),remote=createExecutor(base,settings,key);
    const local=createLocalAgent({getConfig:()=>api.runtime.config.current(),localModel:settings.local_model});
    const gate=createGate({settings,key,execute:(body,signal)=>body.operation==='answer_local'?local(body,signal):remote(body,signal)});
    api.registerCommand({name:'gate',description:'Mac-owned hybrid reasoning with exact disclosure approvals',acceptsArgs:true,requireAuth:true,requiredScopes:['operator.admin'],handler:gate});
    // A separate launch agent also sweeps after gateway crashes. This timer makes
    // ordinary operation independent of UI polling.
    let sweeping=false;
    const timer=setInterval(async()=>{if(sweeping)return;sweeping=true;try{await gate.sweep();}finally{sweeping=false;}},30000);timer.unref();
  }
};
