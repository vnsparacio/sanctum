import {failure} from './runtime.mjs';
import {createToolResultEnvelope} from '../gate/foundation/contracts.mjs';
const LOCAL=new Set(['calc','date_math','unit_convert']);
const OMIT=new Set(['tookMs','durationMs','requestId','request_id','debug','debugInfo','providerDebug']);
const KEEP=new Set(['id','file_id','chat_id','message_id','event_id','calendar_id','calendarId','cursor','next_cursor','nextPageToken','source','policy','provenance','privacy','authority','approval','approvalId','code','url','uri']);
export function normalize(name,result,{maxChars=10000,maxText=2400,maxItems=24}={}){
 const content=result?.content;
 const texts=Array.isArray(content)?content.filter(x=>x.type==='text').map(x=>x.text):[];
 const parse=text=>{try{return JSON.parse(text);}catch{return {text};}};
 const details=result?.details;
 // OpenClaw MCP details are transport metadata, not the tool's answer.
 // Retain every text block and structured payload, with provenance alongside it.
 const mcp=details&&typeof details==='object'&&typeof details.mcpServer==='string';
 let raw;
 if(mcp){
  raw={...details};
  const body=texts.filter(t=>!(details.structuredContent!==undefined&&t===`structuredContent:\n${JSON.stringify(details.structuredContent,null,2)}`));
  if(body.length===1)raw.content=parse(body[0]);
  else if(body.length)raw.content=body.map(parse);
 }else if(result?.structuredContent!==undefined){
  raw={structuredContent:result.structuredContent,...(texts.length?{content:texts.map(parse)}:{})};
 }else if(details!==undefined){
  raw=details;
  // Native plugins commonly mirror details as text. Preserve additional text
  // without duplicating that mirror or rewrapping our own canonical envelope.
  const extra=texts.filter(t=>{try{return JSON.stringify(JSON.parse(t))!==JSON.stringify(details);}catch{return true;}});
  if(extra.length)raw=details&&typeof details==='object'&&!Array.isArray(details)?{...details,supplemental_text:extra.map(parse)}:{details,content:extra.map(parse)};
 }else if(texts.length===1)raw=parse(texts[0]);
 else if(texts.length>1)raw={content:texts.map(parse)};
 else if(Array.isArray(content))raw={}; // Media stays outside the JSON envelope.
 if(raw===undefined)raw=result;
 let truncated=false;
 const clean=(v,depth=0,key='')=>{
  if(depth>16){truncated=true;return '[depth limit]';}
  if(typeof v==='string'&&v.length>maxText&&!KEEP.has(key)){truncated=true;return v.slice(0,maxText);}
  if(Array.isArray(v)){if(v.length>maxItems)truncated=true;return v.slice(0,maxItems).map(x=>clean(x,depth+1));}
  if(v&&typeof v==='object')return Object.fromEntries(Object.entries(v).filter(([k])=>name==='structured_parse'||depth>0||!OMIT.has(k)).map(([k,x])=>[k,clean(x,depth+1,k)]));
  return v;
 };
 const failed=result?.isError===true||raw?.ok===false||raw?.isError===true||raw?.status==='error'||raw?.status==='blocked';
 const untrusted=!LOCAL.has(name)||raw?.untrusted===true;
 let envelope;
 if(failed){
  const safeCodes=new Set(['INVALID_ARGUMENT','INCOMPATIBLE_ARGUMENT','AMBIGUOUS_DATE','AMBIGUOUS_ARGUMENT','OFFSET_REQUIRED','UNKNOWN_OR_AMBIGUOUS_UNIT','INCOMPATIBLE_UNITS','UNSAFE_REGEX','DUPLICATE_JSON_KEY','UNSUPPORTED_EXPRESSION','UTILITY_TIMEOUT','UTILITY_UNAVAILABLE','CANCELLED','OUTPUT_LIMIT','INPUT_LIMIT','NUMERIC_LIMIT','BELOW_ABSOLUTE_ZERO','UNUSED_ARGUMENT','EXPONENT_LIMIT','CONSEQUENTIAL_REPAIR_BLOCKED','SCHEMA_SNAPSHOT_STALE','POLICY_BLOCKED','NONFINITE_JSON']);
  const safeCode=safeCodes.has(raw?.error?.code)?raw.error.code:'BACKEND_FAILURE';
  envelope={...failure(safeCode,'Tool failed or was blocked. No automatic execution retry.'),source:name,...(untrusted?{untrusted:true}:{})};
 }else{
  const data=raw&&typeof raw==='object'&&!Array.isArray(raw)?Object.fromEntries(Object.entries(raw).filter(([k])=>!['ok','untrusted'].includes(k)&&(k!=='source'||raw.source!==name))):raw;
  envelope={ok:true,source:name,...(untrusted?{untrusted:true}:{}),data:clean(data)};
  // Unwrap only the recognized canonical envelope, not arbitrary nested provider data.
  if(raw?.ok===true&&Object.keys(data??{}).length===1&&Object.hasOwn(data,'data'))envelope.data=clean(data.data);
 }
 if(truncated||raw?.truncated===true)envelope.truncated=true;
 if(JSON.stringify(envelope).length>maxChars){
  // Bounded whole-result failure preserves completion uncertainty and never invites replay.
  envelope={ok:!failed,source:name,...(untrusted?{untrusted:true}:{}),truncated:true,data:{result_omitted:true,operation_completed:!failed,notice:'Result exceeds model budget. Do not repeat consequential actions; request a narrower read for details.'}};
 }
 return envelope;
}
export function modelResult(name,result,options){
 // Preserve binary/media blocks, native error bit and metadata outside model-facing text.
 const envelope=normalize(name,result,options);
 const media=(result?.content??[]).filter(x=>x.type!=='text');
 return {...result,isError:result?.isError===true||!envelope.ok,content:[{type:'text',text:JSON.stringify(envelope)},...media],details:envelope};
}

// Compatibility view for the shared foundation. `normalize` remains the
// model-facing shape so existing tool prompts and source-grounding semantics do
// not change while later reasoners receive a typed boundary.
export function capabilityResultEnvelope(name,result,{capabilityDigest='0'.repeat(64),executionState,resultOptions,repairRules=[],verifier='UNKNOWN',rollback='NONE'}={}){
 const normalized=normalize(name,result,resultOptions);
 return createToolResultEnvelope({capability:name,capabilityDigest,executionState:executionState??(normalized.ok?'COMPLETED':'NOT_STARTED'),result:normalized,provenance:normalized.source??name,dataClass:normalized.untrusted?'PERSONAL':'PUBLIC',untrusted:normalized.untrusted===true,truncated:normalized.truncated===true,repairRules,verifier,rollback});
}
