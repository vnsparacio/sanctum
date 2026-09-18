/* Installed diagnostic only. This prepares a future separately authorized run.
 * All actions and workspace state in the three probes are host-synthetic.
 */
import {readFileSync,writeFileSync,chmodSync} from 'node:fs';
import {spawn} from 'node:child_process';
import {createHash,randomBytes} from 'node:crypto';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createExecutor} from './plugin/core.mjs';
import {createPrivateLeadReasoner} from './plugin/private-lead.mjs';
import {deriveCapabilityManifest} from './foundation/manifest.mjs';
import {workModeTools} from './plugin/workspace-tools.mjs';
import {runProtocolMicroprobes} from './protocol-microprobe.mjs';
const base=dirname(fileURLToPath(import.meta.url));
const hash=x=>createHash('sha256').update(x).digest('hex');

export function verifyAuthorization(a,identity,now=Date.now()/1000){
 const gates=['independentReview','installedBytes','doctor','authenticatedWorkHelp','schemaPreflight','exactCompiler','tokenMeasurement','janitor','zeroOwnership','pricingAndCharges'];
 if(a?.schema!=='sanctum-diagnostic-authorization/v1'||a.ownerAuthorized!==true||a.allocationLimit!==1||a.seconds!==900||a.computeCeilingUsd!==0.75||!Number.isFinite(a.hourlyUsd)||a.hourlyUsd<=0||a.hourlyUsd>3||!Number.isFinite(a.expires)||a.expires<=now||a.expires>now+900||gates.some(k=>a.gates?.[k]!==true)||Object.keys(identity).some(k=>a[k]!==identity[k]))throw Error('experiment_authorization');
 return a;
}

export async function runInstalledExperiment({authorizationFile,bindingFile,receiptFile}){
 const settingsRaw=readFileSync(resolve(base,'SETTINGS.json')),settings=JSON.parse(settingsRaw);
 let activeSignal=null;
 const control=(command,args=[])=>new Promise((done,fail)=>{
  const child=spawn(settings.python,['-B',resolve(base,'experiment_control.py'),command,...args],{stdio:['ignore','pipe','ignore']});let raw='';
  child.stdout.on('data',part=>{raw+=part;if(raw.length>65536)child.kill();});child.on('error',()=>fail(Error('experiment_control_failed')));
  const cancelChild=()=>{child.kill('SIGTERM');const timer=setTimeout(()=>child.kill('SIGKILL'),2000);timer.unref();};
  const cancellable=['allocate','ready'].includes(command);if(cancellable){activeSignal?.addEventListener('abort',cancelChild,{once:true});if(activeSignal?.aborted)cancelChild();}
  child.on('close',code=>{activeSignal?.removeEventListener('abort',cancelChild);try{const result=JSON.parse(raw);if(code)throw Error('experiment_control_failed');done(result);}catch{fail(Error('experiment_control_failed'));}});
 });
 const identity=await control('identity'),authorization=verifyAuthorization(JSON.parse(readFileSync(authorizationFile)),identity);
 const binding={...identity,experiment_id:randomBytes(16).toString('hex'),deadline:Math.min(Date.now()/1000+900,authorization.expires)};
 writeFileSync(bindingFile,JSON.stringify(binding)+'\n',{mode:0o600,flag:'wx'});
 const args=['--binding',bindingFile];const created=await control('create',[...args,'--owner-pid',String(process.pid)]);
 if(created.counts?.reserved!==0||Object.entries({total:6,readiness:1,proposal:5,readiness_tokens:16,proposal_tokens:1024}).some(([k,v])=>created.limits?.[k]!==v)){await control('stop',args);throw Error('experiment_initial_ledger');}
 const abort=new AbortController();activeSignal=abort.signal;const cancel=()=>abort.abort();process.once('SIGINT',cancel);process.once('SIGTERM',cancel);
 // Detached guard survives this caller; the launchd janitor can restart cleanup.
 const watch=spawn(settings.python,['-B',resolve(base,'watch.py'),'--release','PRIVATE_LEAD'],{detached:true,stdio:'ignore'});watch.unref();
 let result=null;let outcome='PROBE_FAILED';
 try{
  const limit=Date.now()+15000;
  while(true){const r=await control('status',args);if(r.supervisor_heartbeat&&Date.now()/1000-r.supervisor_heartbeat<30)break;if(Date.now()>limit||abort.signal.aborted)throw Error('experiment_supervisor_missing');await new Promise(r=>setTimeout(r,250));}
  if(abort.signal.aborted)throw Error('experiment_cancelled');
  await control('allocate',[...args,'--owner-authorized-one-allocation','--hourly-ceiling',String(authorization.hourlyUsd)]);
  if(abort.signal.aborted)throw Error('experiment_cancelled');
  await control('ready',[...args,'--owner-authorized-one-allocation']);
  const key=readFileSync(resolve(settings.state_directory,'authority.key'));
  const execute=createExecutor(base,settings,key),scope=randomBytes(16).toString('hex');
  const profile=JSON.parse(readFileSync(resolve(base,'runtime/private-lead-interface-profile.json')));
  const reasoner=createPrivateLeadReasoner({execute,profile,body:(operation,tier,packet,approval)=>({operation,tier,packet:{...packet,experiment:binding},approval,scope,strong:false,state:{scope,revision:0,privacy_floor:'PERSONAL',high_stakes:false},nonce:randomBytes(32).toString('hex'),expires:Math.min(Date.now()/1000+300,binding.deadline),spec_sha256:hash(settingsRaw)})});
  const names=workModeTools.map(x=>x.name);
  const manifest=deriveCapabilityManifest({schemas:workModeTools.map(x=>({name:x.name,description:x.description,parameters:x.parameters})),declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
  result=await runProtocolMicroprobes({reasoner,manifest,scope,experiment:binding,signal:abort.signal});
  outcome=result.passed?'PROBES_COMPLETE':'PROBE_FAILED';
 }finally{
  await control('stop',[...args,'--outcome',abort.signal.aborted?'CANCELLED':outcome]);
  // The supervisor owns uncertain cleanup even if this bounded wait ends.
  let state=await control('sweep',args);
  while(state.state!=='COMPLETE'&&Date.now()/1000<binding.deadline){await new Promise(r=>setTimeout(r,1000));state=await control('sweep',args);}
  writeFileSync(receiptFile,JSON.stringify({schema:'sanctum-diagnostic-receipt/v1',experiment:state,probes:result,cleanupConfirmed:state.state==='COMPLETE',billingCessationClaim:false},null,2)+'\n',{mode:0o600,flag:'wx'});chmodSync(receiptFile,0o600);
  process.removeListener('SIGINT',cancel);process.removeListener('SIGTERM',cancel);
 }
 return result;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const [flag,authorizationFile,bindingFile,receiptFile]=process.argv.slice(2);
 if(flag!=='--owner-authorized-one-allocation'||!authorizationFile||!bindingFile||!receiptFile)throw Error('experiment_live_authorization_required');
 runInstalledExperiment({authorizationFile,bindingFile,receiptFile}).catch(()=>{console.error('REFUSED: experiment_failed; retain supervisor and private receipt.');process.exitCode=1;});
}
