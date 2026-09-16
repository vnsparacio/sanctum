/* Model-facing Work Mode intent.  Host bindings never cross this boundary. */
import {CONTRACT_VERSION,canonical,digest,isRecord} from './contracts.mjs';
import {projectVllmGenerationSchema} from './vllm-structured-output.mjs';

export const WORK_INTENT_VERSION='sanctum-work-intent/v1';
const hostFields=new Set(['schema','proposalId','requestId','revision','reasoner','capabilityDigest','task_id','scope','workspace','manifestDigest','authority','egress','approval']);
const own=(o,k)=>Object.hasOwn(o,k);
const typeOf=v=>v===null?'null':Array.isArray(v)?'array':typeof v;
const fail=(code,detail={})=>({ok:false,code,detail});

function semanticArguments(spec,{testOnly=false}={}){
 const schema=structuredClone(spec.arguments);
 delete schema.properties.task_id;
 schema.required=(schema.required??[]).filter(k=>k!=='task_id');
 if(testOnly&&spec.name==='worktree_command')schema.properties.operation={type:'string',enum:['test']};
 return schema;
}
export function workIntentSchema(specs,{testOnly=false}={}){
 const branches=specs.map(spec=>({type:'object',properties:{kind:{const:'TOOL_PROPOSAL'},capability:{const:spec.name},arguments:semanticArguments(spec,{testOnly})},required:['kind','capability','arguments'],additionalProperties:false}));
 branches.push({type:'object',properties:{kind:{const:'FINAL'},text:{type:'string',minLength:1,maxLength:32768}},required:['kind','text'],additionalProperties:false});
 branches.push({type:'object',properties:{kind:{const:'ESCALATION'},reason:{type:'string',pattern:'^[A-Z][A-Z0-9_:-]{0,79}$'}},required:['kind','reason'],additionalProperties:false});
 return {type:'object',oneOf:branches};
}
export function workIntentRequest(specs,options={}){
 const authoritative=workIntentSchema(specs,options),generation=projectVllmGenerationSchema(authoritative);
 return {version:WORK_INTENT_VERSION,dialect:generation.dialect,schema:generation.schema,schemaDigest:digest(generation.schema),semanticSchemaDigest:digest(authoritative)};
}
export function validateWorkIntent(value,{specs=[],testOnly=false}={}){
 if(!isRecord(value)||typeof value.kind!=='string')return fail('SEMANTIC_SHAPE',{receivedType:typeOf(value)});
 for(const key of Object.keys(value))if(hostFields.has(key))return fail('FORBIDDEN_HOST_FIELD',{field:key});
 if(value.kind==='FINAL')return Object.keys(value).length===2&&typeof value.text==='string'&&value.text.length>0&&value.text.length<=32768?{ok:true,value:structuredClone(value)}:fail('SEMANTIC_SHAPE');
 if(value.kind==='ESCALATION')return Object.keys(value).length===2&&typeof value.reason==='string'&&/^[A-Z][A-Z0-9_:-]{0,79}$/.test(value.reason)?{ok:true,value:structuredClone(value)}:fail('SEMANTIC_SHAPE');
 if(value.kind!=='TOOL_PROPOSAL'||Object.keys(value).length!==3||typeof value.capability!=='string'||!isRecord(value.arguments))return fail('SEMANTIC_SHAPE');
 const spec=specs.find(x=>x.name===value.capability);if(!spec)return fail('CAPABILITY_NOT_VISIBLE',{capability:'UNKNOWN'});
 const schema=semanticArguments(spec,{testOnly}); const a=value.arguments, props=schema.properties??{}, required=schema.required??[];
 if(Object.keys(a).some(k=>!own(props,k)))return fail('ARGUMENT_SCHEMA',{keyword:'additionalProperties',unknownFieldCount:Object.keys(a).filter(k=>!own(props,k)).length});
 const check=(v,s)=>{if(s.type==='string')return typeof v==='string'&&(s.minLength===undefined||v.length>=s.minLength)&&(s.maxLength===undefined||v.length<=s.maxLength)&&(!s.pattern||new RegExp(s.pattern,'u').test(v))&&(!s.enum||s.enum.includes(v));if(s.type==='integer')return Number.isSafeInteger(v)&&(s.minimum===undefined||v>=s.minimum)&&(s.maximum===undefined||v<=s.maximum);return false;};
 for(const key of required)if(!own(a,key))return fail('ARGUMENT_SCHEMA',{keyword:'required',field:key,missingRequired:true});
 for(const [key,v] of Object.entries(a))if(!check(v,props[key]))return fail('ARGUMENT_SCHEMA',{keyword:props[key].enum?'enum':'type',field:key,receivedType:typeOf(v)});
 return {ok:true,value:structuredClone(value),spec};
}
export function bindWorkIntent(intent,context){
 if(!intent?.ok||intent.value.kind!=='TOOL_PROPOSAL')throw Error('work_intent_bind');
 const {value,spec}=intent;
 const taskBound=Object.hasOwn(spec.arguments?.properties??{},'task_id')?{task_id:context.scope}:{};
 return {schema:CONTRACT_VERSION,proposalId:context.proposalId,requestId:context.requestId,revision:context.turn,reasoner:context.reasoner,capability:spec.name,capabilityDigest:context.specDigests[spec.name],arguments:{...taskBound,...value.arguments}};
}
export const workIntentDiagnostics=result=>({code:result.code,capability:result.detail?.capability??'UNKNOWN',keyword:result.detail?.keyword??null,field:['path','operation','source_need','max_chars','max_entries'].includes(result.detail?.field)?result.detail.field:null,receivedType:result.detail?.receivedType??null,missingRequired:result.detail?.missingRequired===true,unknownFieldCount:Number.isSafeInteger(result.detail?.unknownFieldCount)?result.detail.unknownFieldCount:0});
