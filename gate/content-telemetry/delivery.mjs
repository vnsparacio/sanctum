import {
 chmodSync,closeSync,constants,existsSync,fsyncSync,lstatSync,openSync,
 readFileSync,readdirSync,renameSync,unlinkSync,writeFileSync,
} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname,isAbsolute,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
import {prepareContentTelemetryRecord} from './contract.mjs';

const PRIVATE_DIRECTORY_MODE=0o700;
const PRIVATE_FILE_MODE=0o600;
const OPEN_EXCLUSIVE=constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|(constants.O_NOFOLLOW??0);
const AREAS=Object.freeze(['pending','failed','quarantine','staging','uploading']);
const CONFIG_KEYS=Object.freeze([
 'schema','enabled','aws_cli','aws_profile','region','bucket','prefix',
 'max_batches_per_run','max_attempts','base_backoff_ms','max_backoff_ms',
]);

function privateObject(path,{directory}){
 const stat=lstatSync(path);
 return (directory?stat.isDirectory():stat.isFile())&&!stat.isSymbolicLink()&&
  (stat.mode&0o077)===0&&(typeof process.getuid!=='function'||stat.uid===process.getuid());
}

function syncDirectory(path){const fd=openSync(path,constants.O_RDONLY);try{fsyncSync(fd);}finally{closeSync(fd);}}
function safeInteger(value,min,max){return Number.isSafeInteger(value)&&value>=min&&value<=max;}

export function validateContentDeliveryConfig(config){
 if(!config||typeof config!=='object'||Array.isArray(config))return false;
 if(Object.keys(config).some(key=>!CONFIG_KEYS.includes(key)))return false;
 if(config.schema!=='sanctum.content-delivery/v1'||typeof config.enabled!=='boolean')return false;
 if(!isAbsolute(config.aws_cli??'')||!/^[A-Za-z0-9_./+@-]{1,1024}$/.test(config.aws_cli))return false;
 if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(config.aws_profile??''))return false;
 if(!/^[a-z]{2}(?:-gov)?-[a-z]+-\d$/.test(config.region??''))return false;
 if(!/^(?!.*\.\.)(?!-)[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/.test(config.bucket??''))return false;
 if(!/^(?!\/)(?!.*(?:^|\/)\.\.(?:\/|$))[A-Za-z0-9][A-Za-z0-9_./+=,@-]{0,511}\/$/.test(config.prefix??'')||config.prefix.split('/').includes('ops'))return false;
 if(!safeInteger(config.max_batches_per_run,1,1000)||!safeInteger(config.max_attempts,1,5))return false;
 if(!safeInteger(config.base_backoff_ms,1,60000)||!safeInteger(config.max_backoff_ms,config.base_backoff_ms,300000))return false;
 return true;
}

export function loadPrivateContentDeliveryConfig(path){
 if(typeof path!=='string'||!isAbsolute(path)||!privateObject(path,{directory:false}))throw new Error('invalid private content delivery configuration');
 const config=JSON.parse(readFileSync(path,'utf8'));
 if(!validateContentDeliveryConfig(config))throw new Error('invalid private content delivery configuration');
 return Object.freeze(config);
}

function canonicalBatch(path){
 if(!privateObject(path,{directory:false}))return null;
 const text=readFileSync(path,'utf8');
 if(!text.endsWith('\n')||text.indexOf('\n')!==text.length-1)return null;
 try{
  const record=prepareContentTelemetryRecord(JSON.parse(text.slice(0,-1)));
  if(JSON.stringify(record)+'\n'!==text)return null;
  return Object.freeze({text,record,digest:createHash('sha256').update(text).digest('hex')});
 }catch{return null;}
}

function objectKey(prefix,batch){
 const [year,month,day]=batch.record.timestamp.slice(0,10).split('-');
 return `${prefix}${year}/${month}/${day}/${encodeURIComponent(batch.record.event_id)}-${batch.digest}.jsonl`;
}

function staleLock(path){
 try{
  const value=JSON.parse(readFileSync(path,'utf8'));
  if(!Number.isSafeInteger(value?.pid)||value.pid<1)return false;
  try{process.kill(value.pid,0);return false;}catch(error){return error?.code==='ESRCH';}
 }catch{return false;}
}

function moveFile(source,target){renameSync(source,target);syncDirectory(dirname(source));syncDirectory(dirname(target));}
function availableTarget(directory,name){
 let target=join(directory,name),counter=0;
 while(existsSync(target)){counter+=1;target=join(directory,`${Date.now()}-${counter}-${name}`);}
 return target;
}

export function createAwsCliContentClient(config,{run=spawnSync}={}){
 const common=['--profile',config.aws_profile,'--region',config.region,'--no-cli-pager'];
 function execute(args){return run(config.aws_cli,args,{encoding:'utf8',timeout:120000,maxBuffer:1024*1024,stdio:['ignore','pipe','pipe']});}
 return Object.freeze({
  async putObject({key,digest,file}){
   const result=execute(['s3api','put-object','--bucket',config.bucket,'--key',key,'--body',file,
    '--content-type','application/x-ndjson','--metadata',`content-sha256=${digest}`,'--if-none-match','*',...common]);
   if(result.status===0)return 'uploaded';
   return /(?:\(412\)|PreconditionFailed)/i.test(String(result.stderr??''))?'exists':'unknown';
  },
 });
}

export function createContentTelemetryDelivery({config,root,client,sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms))}={}){
 const valid=validateContentDeliveryConfig(config)&&typeof root==='string'&&isAbsolute(root)&&
  client&&typeof client.putObject==='function';
 const paths=valid?Object.fromEntries(AREAS.map(area=>[area,join(root,area)])):null;

 function initialize(){
  if(!valid||!existsSync(root)||!privateObject(root,{directory:true}))return false;
  for(const area of AREAS)if(!existsSync(paths[area])||!privateObject(paths[area],{directory:true}))return false;
  return true;
 }

 function quarantine(file){
  const target=availableTarget(paths.quarantine,`${Date.now()}-${createHash('sha256').update(file).digest('hex').slice(0,16)}.bad`);
  moveFile(file,target);chmodSync(target,PRIVATE_FILE_MODE);return target;
 }

 function fail(file,name){
  moveFile(file,availableTarget(paths.failed,name));
 }

 async function deliver(file,name,batch){
  const key=objectKey(config.prefix,batch);
  for(let attempt=1;attempt<=config.max_attempts;attempt+=1){
   let put='unknown';
   try{put=await client.putObject({bucket:config.bucket,key,digest:batch.digest,file,body:batch.text});}catch{}
   if(put==='uploaded'){unlinkSync(file);syncDirectory(paths.uploading);return 'uploaded';}
   if(put==='exists'){unlinkSync(file);syncDirectory(paths.uploading);return 'reconciled';}
   if(attempt===config.max_attempts)return 'failed';
   await sleep(Math.min(config.max_backoff_ms,config.base_backoff_ms*(2**(attempt-1))));
  }
  return 'failed';
 }

 async function run(){
  const summary={examined:0,uploaded:0,reconciled:0,failed:0,quarantined:0};
  if(!config?.enabled||!initialize())return Object.freeze(summary);
  const lock=join(root,'.delivery.lock');let fd,acquired=false;
  try{
   try{fd=openSync(lock,OPEN_EXCLUSIVE,PRIVATE_FILE_MODE);}catch(error){
    if(error?.code!=='EEXIST'||!staleLock(lock))return Object.freeze(summary);
    unlinkSync(lock);syncDirectory(root);fd=openSync(lock,OPEN_EXCLUSIVE,PRIVATE_FILE_MODE);
   }
   acquired=true;writeFileSync(fd,JSON.stringify({pid:process.pid})+'\n','utf8');fsyncSync(fd);closeSync(fd);fd=undefined;
   for(const name of readdirSync(paths.uploading)){
    const file=join(paths.uploading,name),batch=canonicalBatch(file);
    if(batch)moveFile(file,availableTarget(paths.pending,name));else{quarantine(file);summary.quarantined+=1;}
   }
   const candidates=[];
   for(const area of ['pending','failed'])for(const name of readdirSync(paths[area]).sort())candidates.push({area,name});
   for(const {area,name} of candidates.slice(0,config.max_batches_per_run)){
    const source=join(paths[area],name),batch=canonicalBatch(source);summary.examined+=1;
    if(!batch){quarantine(source);summary.quarantined+=1;continue;}
    const claimed=join(paths.uploading,name);moveFile(source,claimed);
    const result=await deliver(claimed,name,batch);
    if(result==='uploaded')summary.uploaded+=1;
    else if(result==='reconciled')summary.reconciled+=1;
    else{fail(claimed,name);summary.failed+=1;}
   }
   return Object.freeze(summary);
  }catch{return Object.freeze(summary);}
  finally{
   if(fd!==undefined)closeSync(fd);
   if(acquired)try{unlinkSync(lock);syncDirectory(root);}catch{}
  }
 }
 return Object.freeze({enabled:Boolean(valid&&config?.enabled),run});
}

async function main(argv){
 if(argv.length!==4||argv[0]!=='--config'||argv[2]!=='--root'||!isAbsolute(argv[3]))throw new Error('invalid content delivery invocation');
 const config=loadPrivateContentDeliveryConfig(argv[1]);
 const delivery=createContentTelemetryDelivery({config,root:argv[3],client:createAwsCliContentClient(config)});
 const summary=await delivery.run();
 process.stdout.write(JSON.stringify(summary)+'\n');
 if(summary.failed||summary.quarantined)process.exitCode=1;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main(process.argv.slice(2)).catch(()=>{
 process.stderr.write('content telemetry delivery failed\n');process.exitCode=1;
});
