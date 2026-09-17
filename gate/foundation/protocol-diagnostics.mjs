/* Diagnostics are data, never acceptance. No arbitrary keys, values or pointers. */
export const DIAGNOSTIC_VERSION='sanctum-protocol-diagnostic/v1';
const enums={stage:['STREAM','JSON_PARSE','BACKEND_RESULT','GENERIC_RESULT','WORK_INTENT','REQUEST'],validatorVersion:['stream/v1','json/v1','backend-result/v1','sanctum-capability/v1','sanctum-work-intent/v1','request/v1'],resultKind:['FINAL','ESCALATION','TOOL_PROPOSAL','UNKNOWN'],field:['root','kind','reason','text','capability','arguments','path','operation','patch','source_need','max_chars','max_entries','UNKNOWN'],keyword:['type','required','additionalProperties','pattern','minLength','maxLength','minimum','maximum','enum','const','visibility','forbiddenCharacter','syntax','duplicateKey','nonfinite','completion','toolCalls','refusal','choices','limit','UNKNOWN'],receivedType:['object','array','string','number','boolean','null','undefined','UNKNOWN'],streamStatus:['COMPLETE','INCOMPLETE','NOT_STREAMED','UNKNOWN'],finishStatus:['stop','length','tool_calls','content_filter','UNKNOWN'],parseStatus:['BEFORE_PARSE','PARSED','FAILED','UNKNOWN'],normalization:['UNCHANGED','NOT_REACHED','UNKNOWN']};
export function sanitizeProtocolDiagnostic(value){
 const out={schema:DIAGNOSTIC_VERSION};
 for(const [key,values] of Object.entries(enums))out[key]=values.includes(value?.[key])?value[key]:'UNKNOWN';
 for(const key of ['stringLength','unknownFieldCount'])out[key]=Number.isSafeInteger(value?.[key])&&value[key]>=0?Math.min(value[key],65537):null;
 out.patternMatch=typeof value?.patternMatch==='boolean'?value.patternMatch:null;
 out.missingField=value?.missingField===true;
 return out;
}
const type=v=>v===null?'null':Array.isArray(v)?'array':typeof v;
export function schemaDiagnostic(value,schema,{stage='WORK_INTENT',validatorVersion='sanctum-work-intent/v1'}={}){
 const base={stage,validatorVersion,resultKind:value?.kind,parseStatus:'PARSED',normalization:'UNCHANGED'};
 const fail=(v,field,keyword,extra={})=>sanitizeProtocolDiagnostic({...base,field,keyword,receivedType:type(v),stringLength:typeof v==='string'?v.length:null,...extra});
 function visit(v,s,field){
  if(s.oneOf){
   const branch=s.oneOf.find(x=>x.properties?.kind?.const===v?.kind&&(v?.kind!=='TOOL_PROPOSAL'||x.properties?.capability?.const===v?.capability));
   return branch?visit(v,branch,field):fail(v,field,'visibility');
  }
  if(s.type&&(s.type==='integer'?!Number.isSafeInteger(v):type(v)!==s.type))return fail(v,field,'type');
  if(Object.hasOwn(s,'const')&&v!==s.const)return fail(v,field,'const');
  if(s.enum&&!s.enum.includes(v))return fail(v,field,'enum');
  if(s.type==='object'){
   for(const key of s.required??[])if(!Object.hasOwn(v,key))return fail(undefined,key,'required',{missingField:true});
   const unknown=Object.keys(v).filter(k=>!Object.hasOwn(s.properties??{},k)).length;
   if(s.additionalProperties===false&&unknown)return fail(v,field,'additionalProperties',{unknownFieldCount:unknown});
   for(const [key,sub] of Object.entries(s.properties??{}))if(Object.hasOwn(v,key)){const error=visit(v[key],sub,key);if(error)return error;}
  }
  if(typeof v==='string'){
   if(s.minLength!==undefined&&v.length<s.minLength)return fail(v,field,'minLength');
   if(s.maxLength!==undefined&&v.length>s.maxLength)return fail(v,field,'maxLength');
   if(s.pattern&&!new RegExp(s.pattern,'u').test(v))return fail(v,field,'pattern',{patternMatch:false});
   if(s.noNul&&v.includes('\0'))return fail(v,field,'forbiddenCharacter');
  }
  if(typeof v==='number')for(const key of ['minimum','maximum'])if(s[key]!==undefined&&(key==='minimum'?v<s[key]:v>s[key]))return fail(v,field,key);
  return null;
 }
 return visit(value,schema,'root')??fail(value,'root','UNKNOWN');
}
export function genericResultDiagnostic(value){
 const properties=value?.kind==='ESCALATION'?{kind:{const:'ESCALATION'},reason:{type:'string',pattern:'^[A-Z][A-Z0-9_:-]{0,79}$'}}:value?.kind==='FINAL'?{kind:{const:'FINAL'},text:{type:'string',minLength:1,maxLength:32768,noNul:true}}:{kind:{const:'TOOL_PROPOSAL'},capability:{type:'string',pattern:'^[A-Za-z][A-Za-z0-9_.:-]{0,79}$'},arguments:{type:'object'}};
 return schemaDiagnostic(value,{type:'object',properties,required:Object.keys(properties),additionalProperties:false},{stage:'GENERIC_RESULT',validatorVersion:'sanctum-capability/v1'});
}
