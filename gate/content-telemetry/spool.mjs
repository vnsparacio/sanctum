import {
 chmodSync,
 closeSync,
 constants,
 existsSync,
 fsyncSync,
 lstatSync,
 mkdirSync,
 openSync,
 readFileSync,
 readdirSync,
 renameSync,
 unlinkSync,
 writeFileSync,
} from 'node:fs';
import {dirname,isAbsolute,join} from 'node:path';
import {randomUUID} from 'node:crypto';
import {
 CONTENT_TELEMETRY_MAX_RECORD_BYTES,
 prepareContentTelemetryRecord,
 validateContentTelemetryConfig,
} from './contract.mjs';

export const CONTENT_TELEMETRY_SPOOL_DEFAULTS=Object.freeze({
 max_records:1000,
 max_bytes:64*1024*1024,
});

const AREAS=Object.freeze(['pending','failed','quarantine','staging']);
const PRIVATE_DIRECTORY_MODE=0o700;
const PRIVATE_FILE_MODE=0o600;
const OPEN_EXCLUSIVE=constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|(constants.O_NOFOLLOW??0);

function safeLimits(limits){
 const value={...CONTENT_TELEMETRY_SPOOL_DEFAULTS,...limits};
 if(!Number.isSafeInteger(value.max_records)||value.max_records<1||value.max_records>100000)return null;
 if(!Number.isSafeInteger(value.max_bytes)||value.max_bytes<CONTENT_TELEMETRY_MAX_RECORD_BYTES||value.max_bytes>1024*1024*1024)return null;
 if(Object.keys(value).some(key=>!['max_records','max_bytes'].includes(key)))return null;
 return Object.freeze(value);
}

function assertPrivate(path,{directory}){
 const stat=lstatSync(path);
 if(directory?!stat.isDirectory():!stat.isFile())throw new Error('unsafe content telemetry spool object');
 if(stat.isSymbolicLink()||(stat.mode&0o077)!==0)throw new Error('unsafe content telemetry spool permissions');
 if(typeof process.getuid==='function'&&stat.uid!==process.getuid())throw new Error('unsafe content telemetry spool owner');
}

function ensurePrivateDirectory(path){
 if(!existsSync(path))mkdirSync(path,{mode:PRIVATE_DIRECTORY_MODE});
 assertPrivate(path,{directory:true});
 chmodSync(path,PRIVATE_DIRECTORY_MODE);
}

function syncDirectory(path){
 const fd=openSync(path,constants.O_RDONLY);
 try{fsyncSync(fd);}finally{closeSync(fd);}
}

function inventory(paths){
 let records=0,bytes=0;
 for(const area of AREAS){
  for(const name of readdirSync(paths[area])){
   const file=join(paths[area],name),stat=lstatSync(file);
   if(!stat.isFile()||stat.isSymbolicLink())throw new Error('unsafe content telemetry spool entry');
   if((stat.mode&0o077)!==0)throw new Error('unsafe content telemetry spool permissions');
   if(typeof process.getuid==='function'&&stat.uid!==process.getuid())throw new Error('unsafe content telemetry spool owner');
   records+=1;bytes+=stat.size;
  }
 }
 return {records,bytes};
}

function canonicalSegment(file){
 const stat=lstatSync(file);
 if(!stat.isFile()||stat.isSymbolicLink()||(stat.mode&0o077)!==0)return null;
 if(typeof process.getuid==='function'&&stat.uid!==process.getuid())return null;
 if(stat.size<2||stat.size>CONTENT_TELEMETRY_MAX_RECORD_BYTES+1)return null;
 const text=readFileSync(file,'utf8');
 if(!text.endsWith('\n')||text.indexOf('\n')!==text.length-1)return null;
 const parsed=JSON.parse(text.slice(0,-1));
 const prepared=prepareContentTelemetryRecord(parsed);
 return JSON.stringify(prepared)+'\n'===text?text:null;
}

function destination(paths,area,suffix='jsonl'){
 return join(paths[area],`${Date.now()}-${randomUUID()}.${suffix}`);
}

function move(paths,source,area,suffix){
 const target=destination(paths,area,suffix);
 const stat=lstatSync(source),privateRegular=stat.isFile()&&!stat.isSymbolicLink();
 renameSync(source,target);
 if(privateRegular)chmodSync(target,PRIVATE_FILE_MODE);
 syncDirectory(dirname(source));
 syncDirectory(paths[area]);
 return target;
}

function staleWriter(lock){
 try{
  const value=JSON.parse(readFileSync(lock,'utf8'));
  if(!Number.isSafeInteger(value?.pid)||value.pid<1)return false;
  try{process.kill(value.pid,0);return false;}
  catch(error){return error?.code==='ESRCH';}
 }catch{return false;}
}

export function createContentTelemetrySpool({config,root,limits}={}){
 const enabled=config?.enabled===true;
 const bounded=safeLimits(limits);
 const valid=validateContentTelemetryConfig(config)&&bounded&&typeof root==='string'&&isAbsolute(root);
 const paths=valid?Object.fromEntries(AREAS.map(area=>[area,join(root,area)])):null;

 function initialize(){
  if(!valid)throw new Error('invalid content telemetry spool configuration');
  ensurePrivateDirectory(root);
  for(const area of AREAS)ensurePrivateDirectory(paths[area]);
 }

 function withLock(callback){
  initialize();
  const lock=join(root,'.writer.lock');
  let fd,acquired=false;
  try{
   try{fd=openSync(lock,OPEN_EXCLUSIVE,PRIVATE_FILE_MODE);}
   catch(error){
    if(error?.code!=='EEXIST'||!staleWriter(lock))throw error;
    unlinkSync(lock);syncDirectory(root);
    fd=openSync(lock,OPEN_EXCLUSIVE,PRIVATE_FILE_MODE);
   }
   acquired=true;
   writeFileSync(fd,JSON.stringify({pid:process.pid})+'\n','utf8');fsyncSync(fd);closeSync(fd);fd=undefined;
   assertPrivate(lock,{directory:false});
   return callback();
  }finally{
   if(fd!==undefined)closeSync(fd);
   if(acquired)try{unlinkSync(lock);syncDirectory(root);}catch{}
  }
 }

 function append(record){
  if(!enabled||!valid)return false;
  try{
   const prepared=prepareContentTelemetryRecord(record);
   const segment=JSON.stringify(prepared)+'\n';
   const segmentBytes=Buffer.byteLength(segment,'utf8');
   return withLock(()=>{
    const used=inventory(paths);
    if(used.records>=bounded.max_records||used.bytes+segmentBytes>bounded.max_bytes)return false;
    const staged=destination(paths,'staging','partial');
    let fd;
    try{
     fd=openSync(staged,OPEN_EXCLUSIVE,PRIVATE_FILE_MODE);
     writeFileSync(fd,segment,'utf8');fsyncSync(fd);closeSync(fd);fd=undefined;
     assertPrivate(staged,{directory:false});
     move(paths,staged,'pending','jsonl');
     return true;
    }finally{
     if(fd!==undefined)closeSync(fd);
    }
   });
  }catch{return false;}
 }

 function recover(){
  const summary={pending:0,failed:0,quarantined:0};
  if(!enabled||!valid)return Object.freeze(summary);
  try{
   return withLock(()=>{
    for(const area of ['staging','pending','failed']){
     for(const name of readdirSync(paths[area])){
      const file=join(paths[area],name);
      let complete=false;
      try{complete=canonicalSegment(file)!==null;}catch{}
      if(area==='staging'&&complete){move(paths,file,'pending','jsonl');continue;}
      if(!complete){move(paths,file,'quarantine','bad');summary.quarantined+=1;continue;}
     }
    }
    summary.pending=readdirSync(paths.pending).length;
    summary.failed=readdirSync(paths.failed).length;
    return Object.freeze(summary);
   });
  }catch{return Object.freeze(summary);}
 }

 return Object.freeze({append,recover,enabled:enabled&&Boolean(valid)});
}
