import {createHash} from 'node:crypto';
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
 writeFileSync,
} from 'node:fs';
import {isAbsolute,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import Ajv from 'ajv';

export const QUALITY_ANNOTATION_SCHEMA_VERSION='sanctum.quality-annotation/v1';
export const QUALITY_ANNOTATION_MAX_BYTES=16384;

const schemaPath=fileURLToPath(new URL('../../config/schemas/quality-annotation-v1.schema.json',import.meta.url));
export const qualityAnnotationSchema=Object.freeze(JSON.parse(readFileSync(schemaPath,'utf8')));
const validateSchema=new Ajv({allErrors:true,strict:true}).compile(qualityAnnotationSchema);
const PRIVATE_DIRECTORY_MODE=0o700;
const PRIVATE_FILE_MODE=0o600;
const OPEN_EXCLUSIVE=constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|(constants.O_NOFOLLOW??0);
const INPUT_KEYS=Object.freeze([
 'operation_id','interaction_id','source','owner_rating','evaluator','benchmark','scores','pass',
 'semantic_failure_category','grounding','citation',
]);

function error(code,message,keywords=[]){return Object.assign(new TypeError(message),{code,keywords});}
function byteLength(value){return Buffer.byteLength(JSON.stringify(value),'utf8');}
function annotationId(input){
 return 'qa-'+createHash('sha256').update(JSON.stringify([input.interaction_id,input.operation_id])).digest('hex');
}
function payload(record){return Object.fromEntries(INPUT_KEYS.map(key=>[key,record[key]]));}
function samePayload(left,right){return JSON.stringify(payload(left))===JSON.stringify(payload(right));}
function assertPrivate(path,{directory}){
 const stat=lstatSync(path);
 if(directory?!stat.isDirectory():!stat.isFile())throw error('QUALITY_ANNOTATION_STORAGE','unsafe quality annotation object');
 if(stat.isSymbolicLink()||(stat.mode&0o077)!==0)throw error('QUALITY_ANNOTATION_STORAGE','unsafe quality annotation permissions');
 if(typeof process.getuid==='function'&&stat.uid!==process.getuid())throw error('QUALITY_ANNOTATION_STORAGE','unsafe quality annotation owner');
}
function ensurePrivateDirectory(path){
 if(!existsSync(path))mkdirSync(path,{mode:PRIVATE_DIRECTORY_MODE});
 assertPrivate(path,{directory:true});chmodSync(path,PRIVATE_DIRECTORY_MODE);
}
function syncDirectory(path){const fd=openSync(path,constants.O_RDONLY);try{fsyncSync(fd);}finally{closeSync(fd);}}
function parseExisting(path){
 assertPrivate(path,{directory:false});
 const text=readFileSync(path,'utf8');
 if(!text.endsWith('\n')||text.indexOf('\n')!==text.length-1)throw error('QUALITY_ANNOTATION_STORAGE','invalid stored quality annotation');
 return prepareQualityAnnotationRecord(JSON.parse(text.slice(0,-1)));
}

export function prepareQualityAnnotationRecord(record){
 if(!record||typeof record!=='object'||Array.isArray(record))throw error('QUALITY_ANNOTATION_SCHEMA','invalid quality annotation',['type']);
 const prepared=structuredClone(record);
 if(!validateSchema(prepared)){
  const keywords=[...new Set((validateSchema.errors??[]).map(item=>item.keyword))].sort();
  throw error('QUALITY_ANNOTATION_SCHEMA','invalid quality annotation',keywords);
 }
 if(new Set(prepared.scores.map(item=>item.name)).size!==prepared.scores.length)throw error('QUALITY_ANNOTATION_SCHEMA','invalid quality annotation',['uniqueScoreNames']);
 if(byteLength(prepared)>QUALITY_ANNOTATION_MAX_BYTES)throw error('QUALITY_ANNOTATION_SIZE','quality annotation exceeds byte limit');
 return Object.freeze(prepared);
}

export function createQualityAnnotation(input,{now=()=>Date.now()}={}){
 if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(key=>!INPUT_KEYS.includes(key)))throw error('QUALITY_ANNOTATION_SCHEMA','invalid quality annotation input',['additionalProperties']);
 const complete={
  schema_version:QUALITY_ANNOTATION_SCHEMA_VERSION,
  annotation_id:annotationId(input),
  recorded_at:new Date(now()).toISOString(),
  authority_effect:'NONE',
  ...structuredClone(input),
 };
 return prepareQualityAnnotationRecord(complete);
}

export function createQualityAnnotationStore({root,now=()=>Date.now()}={}){
 const valid=typeof root==='string'&&isAbsolute(root);

 function append(input){
  if(!valid)throw error('QUALITY_ANNOTATION_STORAGE','quality annotation root must be absolute');
  const candidate=createQualityAnnotation(input,{now});
  ensurePrivateDirectory(root);
  const path=join(root,`${candidate.annotation_id}.jsonl`);
  if(existsSync(path)){
   const existing=parseExisting(path);
   if(samePayload(existing,candidate))return Object.freeze({status:'unchanged',annotation:existing});
   throw error('QUALITY_ANNOTATION_CONFLICT','quality annotation operation conflicts with existing evidence');
  }
  let fd;
  try{
   fd=openSync(path,OPEN_EXCLUSIVE,PRIVATE_FILE_MODE);
   writeFileSync(fd,JSON.stringify(candidate)+'\n','utf8');fsyncSync(fd);closeSync(fd);fd=undefined;
   assertPrivate(path,{directory:false});syncDirectory(root);
   return Object.freeze({status:'created',annotation:candidate});
  }catch(cause){
   if(fd!==undefined)closeSync(fd);
   if(cause?.code==='EEXIST'){
    const existing=parseExisting(path);
    if(samePayload(existing,candidate))return Object.freeze({status:'unchanged',annotation:existing});
    throw error('QUALITY_ANNOTATION_CONFLICT','quality annotation operation conflicts with existing evidence');
   }
   throw cause;
  }
 }

 return Object.freeze({append,enabled:valid});
}
