// Only explicitly named, non-authoritative fields can be repaired.
// A rule never supplies identifiers, paths, recipients, accounts or permissions.
export const rules=[
 {id:'numeric_literal',tools:['messages_chats','messages_history','messages_search','gmail_search','calendar_calendars','calendar_events','calendar_search','steward_list','steward_inspect','calc','date_math','unit_convert'],pattern:'numeric string in registered numeric field',transformation:'finite number matching actual target type',security:'read-only; no identifiers',tests:'runtime.test.mjs'},
 {id:'boolean_literal',tools:['structured_parse'],pattern:'literal true/false when the actual schema requires boolean',transformation:'boolean',security:'CSV/TSV formatting only; never approval or authority flags',tests:'runtime.test.mjs'},
 {id:'bounded_limit',tools:['messages_chats','messages_history','messages_search','gmail_search','calendar_calendars','calendar_events','calendar_search','steward_list','steward_inspect'],pattern:'positive limit/max_chars above actual maximum',transformation:'maximum with repair provenance; never increase a limit',security:'read-only; explicit truncation metadata',tests:'runtime.test.mjs'},
 {id:'unit_parameter_alias',tools:['unit_convert'],pattern:'from/to and canonical from_unit/to_unit absent',transformation:'rename field; reject conflicting values',security:'pure local computation',tests:'runtime.test.mjs'},
 {id:'utility_enum_alias',tools:['unit_convert','structured_parse','date_math'],pattern:'registered exact alias',transformation:'approved canonical unit/format/date-operation spelling',security:'no date guessing or location inference',tests:'runtime.test.mjs'},
 {id:'from_contact_semantics',tools:['messages_search'],pattern:'from:<known contact>',transformation:'existing plugin maps Alex/Alex Example to chat 95 history',security:'UNCHANGED existing implementation; unknown mapping fails closed',tests:'integrations.test.mjs',owner:'plugins/messages-read-tools/dist/index.js'}
];
const fields={messages_chats:['limit'],messages_history:['limit'],messages_search:['limit'],gmail_search:['limit'],calendar_calendars:['limit'],calendar_events:['days','limit'],calendar_search:['days','limit'],steward_list:['limit'],steward_inspect:['max_chars'],date_math:['amount'],unit_convert:['value']};
export const consequential=new Set(['worktree_edit','worktree_patch','save_local_markdown','steward_create_folder','steward_move','steward_rename','steward_undo_last','browser','session_status','vinceai__hub_repo_search']);
const aliases={from:'from_unit',to:'to_unit'};
const unitAliases={celsius:'C',fahrenheit:'F',kelvin:'K',kilometers:'km',kilometres:'km',miles:'mi',gibibytes:'GiB',gigabytes:'GB'};
export function repair(name,input,schema){
 const params=structuredClone(input),applied=[];
 if(consequential.has(name))return {params,applied};
 if(name==='unit_convert')for(const [old,key]of Object.entries(aliases)){
  if(Object.hasOwn(params,old)){
   if(Object.hasOwn(params,key)&&params[key]!==params[old])return {params:input,applied:[],conflict:true};
   params[key]=params[old];delete params[old];applied.push('unit_parameter_alias');
  }
 }
 for(const key of fields[name]??[]){
  const target=schema.properties?.[key];let value=params[key];
  if(!target)continue;
  if(['integer','number'].includes(target.type)&&typeof value==='string'&&/^-?(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)){
   const n=Number(value);
   if(Number.isFinite(n)&&Math.abs(n)<=Number.MAX_SAFE_INTEGER&&(target.type!=='integer'||Number.isInteger(n))){params[key]=value=n;applied.push('numeric_literal');}
  }
  if(['limit','max_chars'].includes(key)&&typeof value==='number'&&Number.isInteger(value)&&value>0&&Number.isFinite(target.maximum)&&value>target.maximum){params[key]=target.maximum;applied.push('bounded_limit');}
 }
 if(name==='unit_convert')for(const key of ['from_unit','to_unit'])if(Object.hasOwn(unitAliases,params[key])){params[key]=unitAliases[params[key]];applied.push('utility_enum_alias');}
 if(name==='structured_parse'&&schema.properties?.headers?.type==='boolean'&&['true','false'].includes(params.headers)){params.headers=params.headers==='true';applied.push('boolean_literal');}
 if(name==='structured_parse'&&['JSON','CSV','TSV','URL'].includes(params.format)){params.format=params.format.toLowerCase();applied.push('utility_enum_alias');}
 if(name==='date_math'&&['day','week','month'].includes(params.unit)){params.unit+='s';applied.push('utility_enum_alias');}
 return {params,applied:[...new Set(applied)]};
}
