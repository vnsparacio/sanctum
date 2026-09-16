/*
 * A host-owned command boundary for Work Mode.  The model never supplies a
 * command line: it can only ask for a named, reviewed operation.  The default
 * implementation refuses when the macOS sandbox executor is unavailable.
 */
import {spawn} from 'node:child_process';
import {realpathSync,existsSync} from 'node:fs';
import path from 'node:path';

const MAX_OUTPUT=65536;
const CATALOG=Object.freeze({
 git_status:{file:'/usr/bin/git',args:['status','--short'],network:false},
 git_diff:{file:'/usr/bin/git',args:['diff','--'],network:false},
 test_node:{file:'/usr/bin/env',args:['node','--test'],network:false},
 test_python:{file:'/usr/bin/env',args:['python3','-B','-m','unittest'],network:false},
});
const escape=value=>`"${String(value).replace(/[\\"]/g,'\\$&')}"`;
function profile(root,tmp){return `(version 1)\n(deny default)\n(allow process-exec)\n(allow process-fork)\n(allow file-read* (subpath ${escape(root)}) (subpath "/usr") (subpath "/bin") (subpath "/System"))\n(allow file-write* (subpath ${escape(root)}) (subpath ${escape(tmp)}))\n(allow file-read-metadata)\n(deny network*)`;}
function contained(root,target){
 const resolved=realpathSync(target),base=realpathSync(root);
 return resolved===base||resolved.startsWith(base+path.sep);
}

export function createCommandBroker({sandbox='/usr/bin/sandbox-exec',spawnProcess=spawn,now=()=>Date.now()}={}){
 return Object.freeze({async execute({workspace,operation,timeoutMs=120000,allowNetwork=false}={}){
   if(!CATALOG[operation]||allowNetwork||!existsSync(sandbox))return {ok:false,code:'ENVIRONMENT_FAILURE',executionState:'NOT_STARTED'};
   if(typeof workspace!=='string'||!contained(workspace,workspace))return {ok:false,code:'WORKSPACE_CONTAINMENT',executionState:'NOT_STARTED'};
   const root=realpathSync(workspace),tmp=path.join(root,'.sanctum-workmode-tmp');
   // A host-created temporary directory may be passed only after containment;
   // this broker does not resolve model-provided paths or mount the home tree.
   if(!existsSync(tmp))return {ok:false,code:'SANDBOX_TEMP_UNAVAILABLE',executionState:'NOT_STARTED'};
   const item=CATALOG[operation], started=now();
   return await new Promise(resolve=>{
     let out=Buffer.alloc(0),done=false;
     const finish=value=>{if(done)return;done=true;clearTimeout(timer);resolve(value);};
     let child;
     try { child=spawnProcess(sandbox,['-p',profile(root,tmp),item.file,...item.args],{cwd:root,shell:false,uid:process.getuid?.(),gid:process.getgid?.(),env:{PATH:'/usr/bin:/bin',LANG:'C',LC_ALL:'C',TMPDIR:tmp,HOME:'/nonexistent'}}); }
     catch { return finish({ok:false,code:'ENVIRONMENT_FAILURE',executionState:'NOT_STARTED'}); }
     const timer=setTimeout(()=>{child.kill('SIGKILL');finish({ok:false,code:'COMMAND_TIMEOUT',executionState:'COMPLETION_UNKNOWN'});},Math.min(timeoutMs,120000));
     child.stdout?.on('data',c=>{out=Buffer.concat([out,c]);if(out.length>MAX_OUTPUT){child.kill('SIGKILL');finish({ok:false,code:'OUTPUT_LIMIT',executionState:'COMPLETION_UNKNOWN'});}});
     child.stderr?.on('data',c=>{out=Buffer.concat([out,c]);if(out.length>MAX_OUTPUT){child.kill('SIGKILL');finish({ok:false,code:'OUTPUT_LIMIT',executionState:'COMPLETION_UNKNOWN'});}});
     child.on('error',()=>finish({ok:false,code:'ENVIRONMENT_FAILURE',executionState:'NOT_STARTED'}));
     child.on('close',code=>finish({ok:code===0,code:code===0?'OK':'COMMAND_FAILED',executionState:'COMPLETED',output:out.toString('utf8'),elapsedMs:now()-started}));
   });
 }});
}

export const commandCatalog=Object.freeze(Object.keys(CATALOG));
