/* Model-facing Work Mode intent.  Host bindings never cross this boundary. */
import {decisionNoteSchema,detachDecisionNote} from './decision-note.mjs';
import {CONTRACT_VERSION,canonical,digest,isRecord} from './contracts.mjs';
import {projectVllmGenerationSchema} from './vllm-structured-output.mjs';

export const WORK_INTENT_VERSION='sanctum-work-intent/v1';
export const WORK_INTENT_TERMINALS=Object.freeze(['FINAL','ESCALATION']);
const hostFields=new Set(['schema','proposalId','requestId','revision','reasoner','capabilityDigest','task_id','scope','workspace','manifestDigest','authority','egress','approval']);
const own=(o,k)=>Object.hasOwn(o,k);
const typeOf=v=>v===null?'null':Array.isArray(v)?'array':typeof v;
const fail=(code,detail={})=>({ok:false,code,detail});
const editShapes=Object.freeze([
 Object.freeze({operation:'replace',fields:['operation','path','old_text','new_text']}),
 Object.freeze({operation:'create',fields:['operation','path','new_text']}),
 Object.freeze({operation:'delete',fields:['operation','path']}),
 Object.freeze({operation:'move',fields:['operation','path','destination']}),
]);
const editName=shape=>shape.operation??'replace';
function visibleEditShapes(operations){
 const allowed=operations??['replace','create','delete','move'];
 if(!Array.isArray(allowed)||!allowed.length||new Set(allowed).size!==allowed.length||allowed.some(name=>!editShapes.some(shape=>editName(shape)===name)))throw Error('work_intent_edit_operations');
 return editShapes.filter(shape=>allowed.includes(editName(shape)));
}

function semanticArguments(spec,{testOnly=false}={}){
 const schema=structuredClone(spec.arguments);
 delete schema.properties.task_id;
 schema.required=(schema.required??[]).filter(k=>k!=='task_id');
 if(spec.name==='worktree_edit'&&hasEditVariants(schema))schema.properties.operation.enum=['replace',...schema.properties.operation.enum];
 if(testOnly&&spec.name==='worktree_command')schema.properties.operation={type:'string',enum:['test']};
 return schema;
}
const hasEditVariants=schema=>schema?.properties?.operation?.enum?.includes('create')&&schema.properties.destination&&schema.properties.old_text&&schema.properties.new_text;
export function workIntentDescription(spec){
 if(spec.name!=='worktree_edit'||!hasEditVariants(spec.arguments))return spec.description;
 return 'Perform one bounded file action. Every Work Intent edit selects operation explicitly: replace {operation:replace,path,old_text,new_text}; create {operation:create,path,new_text}; delete {operation:delete,path}; move {operation:move,path,destination}. Use only fields belonging to that shape. Create requires an absent path and an existing parent directory. Replace, delete and move require reading the existing source first. Replace matches old_text exactly and uniquely; it is not a whole-file overwrite. The Mac enforces protected paths, symlinks, scope and exact diff authorization.';
}
function editArgumentsSchema(schema,operations){
 return {oneOf:visibleEditShapes(operations).map(shape=>({type:'object',properties:Object.fromEntries(shape.fields.map(field=>[field,field==='operation'?{const:shape.operation}:structuredClone(schema.properties[field])])),required:[...shape.fields],additionalProperties:false}))};
}
function exactEditShape(args,operations){
 return visibleEditShapes(operations).some(shape=>{
  if((own(args,'operation')?args.operation:null)!==shape.operation)return false;
  return Object.keys(args).length===shape.fields.length&&shape.fields.every(field=>own(args,field));
 });
}
function terminalVisibility(options){
 if(!Object.hasOwn(options,'terminalKinds')||!Array.isArray(options.terminalKinds))throw Error('work_intent_terminal_visibility');
 const unique=[...new Set(options.terminalKinds)];
 if(unique.length!==options.terminalKinds.length||unique.some(kind=>!WORK_INTENT_TERMINALS.includes(kind)))throw Error('work_intent_terminal_visibility');
 return new Set(unique);
}
export function workIntentSchema(specs,options={}){
 const {testOnly=false,editOperations}=options,terminals=terminalVisibility(options);
 const branches=specs.map(spec=>{const argumentsSchema=semanticArguments(spec,{testOnly});return {type:'object',properties:{kind:{const:'TOOL_PROPOSAL'},capability:{const:spec.name},arguments:spec.name==='worktree_edit'&&hasEditVariants(argumentsSchema)?editArgumentsSchema(argumentsSchema,editOperations):argumentsSchema},required:['kind','capability','arguments'],additionalProperties:false};});
 if(terminals.has('FINAL'))branches.push({type:'object',properties:{kind:{const:'FINAL'},text:{type:'string',minLength:1,maxLength:32768}},required:['kind','text'],additionalProperties:false});
 if(terminals.has('ESCALATION'))branches.push({type:'object',properties:{kind:{const:'ESCALATION'},reason:{type:'string',pattern:'^[A-Z][A-Z0-9_:-]{0,79}$'}},required:['kind','reason'],additionalProperties:false});
 if(!branches.length)throw Error('work_intent_empty_surface');
 if(options.decisionNotes!==false)for(const branch of branches)branch.properties.decision_note=decisionNoteSchema();
 return {type:'object',oneOf:branches};
}
export function workIntentRequest(specs,options={}){
 const authoritative=workIntentSchema(specs,options),generation=projectVllmGenerationSchema(authoritative);
 return {version:WORK_INTENT_VERSION,dialect:generation.dialect,schema:generation.schema,schemaDigest:digest(generation.schema),semanticSchemaDigest:digest(authoritative)};
}
export function validateWorkIntent(value,options={}){
 if(options.decisionNotes!==false)value=detachDecisionNote(value).value;
 let terminals;try{terminals=terminalVisibility(options);}catch{return fail('TERMINAL_VISIBILITY_REQUIRED');}
 const {specs=[],testOnly=false,editOperations}=options;
 if(!isRecord(value)||typeof value.kind!=='string')return fail('SEMANTIC_SHAPE',{receivedType:typeOf(value)});
 if(WORK_INTENT_TERMINALS.includes(value.kind)&&!terminals.has(value.kind))return fail('TERMINAL_NOT_VISIBLE',{terminal:value.kind});
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
 if(spec.name==='worktree_edit'&&hasEditVariants(schema)&&!exactEditShape(a,editOperations))return fail('ARGUMENT_SCHEMA',{keyword:'oneOf',field:'operation'});
 return {ok:true,value:structuredClone(value),spec};
}
export function bindWorkIntent(intent,context){
 if(!intent?.ok||intent.value.kind!=='TOOL_PROPOSAL')throw Error('work_intent_bind');
 const {value,spec}=intent;
 const taskBound=Object.hasOwn(spec.arguments?.properties??{},'task_id')?{task_id:context.scope}:{};
 // Translate the explicit model discriminator to the unchanged exact-edit tool.
 const argumentsValue=structuredClone(value.arguments);
 if(spec.name==='worktree_edit'&&hasEditVariants(spec.arguments)&&argumentsValue.operation==='replace')delete argumentsValue.operation;
 return {schema:CONTRACT_VERSION,proposalId:context.proposalId,requestId:context.requestId,revision:context.turn,reasoner:context.reasoner,capability:spec.name,capabilityDigest:context.specDigests[spec.name],arguments:{...taskBound,...argumentsValue}};
}
export const workIntentDiagnostics=result=>({code:result.code,capability:result.detail?.capability??'UNKNOWN',terminal:WORK_INTENT_TERMINALS.includes(result.detail?.terminal)?result.detail.terminal:null,keyword:result.detail?.keyword??null,field:['path','operation','source_need','max_chars','max_entries'].includes(result.detail?.field)?result.detail.field:null,receivedType:result.detail?.receivedType??null,missingRequired:result.detail?.missingRequired===true,unknownFieldCount:Number.isSafeInteger(result.detail?.unknownFieldCount)?result.detail.unknownFieldCount:0});
