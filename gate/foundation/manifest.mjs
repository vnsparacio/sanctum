/* Runtime projection of executable registration, captured schema and Mac policy. */
import {CONTRACT_VERSION,canonical,deepFreeze,digest,isRecord} from './contracts.mjs';

const localUtilities=new Set(['calc','date_math','unit_convert','structured_parse']);
const mutations=new Map([
  ['save_local_markdown',{mode:'CREATE_ONLY',undo:null}],
  ['steward_create_folder',{mode:'UNDO_CAPABILITY',undo:'steward_undo_last'}],
  ['steward_move',{mode:'UNDO_CAPABILITY',undo:'steward_undo_last'}],
  ['steward_rename',{mode:'UNDO_CAPABILITY',undo:'steward_undo_last'}],
  ['steward_undo_last',{mode:'NONE',undo:null}],
]);
const owned=new Set([
  ...localUtilities,'messages_chats','messages_history','messages_contact_history','messages_search',
  'gmail_search','gmail_read','calendar_calendars','calendar_events','calendar_search','calendar_event',
  'save_local_markdown','steward_list','steward_inspect','steward_create_folder','steward_move','steward_rename','steward_undo_last',
]);
export const PINNED_ADAPTER_TOOLS=Object.freeze(['browser','web_search','web_fetch','vinceai__get_current_time','vinceai__convert_to_markdown','vinceai__hub_repo_search']);
const supported=new Set([...owned,...PINNED_ADAPTER_TOOLS]);
const personal=/^(messages_|gmail_|calendar_|steward_|save_local_markdown$)/;
const approvals=new Set(['browser','steward_move','steward_rename','steward_undo_last','vinceai__hub_repo_search']);

export function capabilityPolicy(name,repairRules=[]){
  if(!supported.has(name))return deepFreeze({supported:false,effect:'READ',rollback:'NONE',undoCapability:null,authority:'DENY',egress:'UNSUPPORTED',inputDataClass:'RESTRICTED',outputDataClass:'RESTRICTED',untrusted:true,repairRules:[],verifiers:[],remoteResultEligible:false});
  const rollback=mutations.get(name)??{mode:'NONE',undo:null};
  const effect=mutations.has(name)?'MUTATION':name==='browser'?'CONTROL':'READ';
  const personalOutput=personal.test(name)||name==='browser';
  const personalInput=personalOutput||['web_search','web_fetch','vinceai__hub_repo_search'].includes(name);
  let egress='LOCAL_ONLY';
  if(/^(gmail_|calendar_)/.test(name))egress='BROKER_BOUND';
  if(['web_search','web_fetch'].includes(name))egress='CONFIGURATION_BOUND';
  if(name==='browser')egress='BROWSER_POLICY_BOUND';
  if(name==='vinceai__hub_repo_search')egress='DESTINATION_BOUND';
  return deepFreeze({supported:true,effect,rollback:rollback.mode,undoCapability:rollback.undo,authority:approvals.has(name)?'NATIVE_ALLOW_ONCE_OR_DENY':'MAC_POLICY',egress,inputDataClass:personalInput?'PERSONAL':'PUBLIC',outputDataClass:personalOutput?'PERSONAL':'PUBLIC',untrusted:!localUtilities.has(name),repairRules:[...repairRules],verifiers:localUtilities.has(name)?['exact_utility']:[],remoteResultEligible:false});
}

const normalizeRegistered=value=>typeof value==='string'?{name:value,source:'RUNTIME_DECLARATION'}:value;
const addUnique=(map,row,error)=>{
  if(!isRecord(row)||typeof row.name!=='string'||!row.name||map.has(row.name))throw Error(error);
  map.set(row.name,row);
};

export function deriveCapabilityManifest({schemas=[],declaredTools=[],registeredTools=[],adaptedTools=PINNED_ADAPTER_TOOLS,runtimeConfig={},repairRulesByTool={},allowedRepairRules=[]}={}){
  const schemaByName=new Map();
  for(const row of schemas)addUnique(schemaByName,row,'capability_schema_capture_invalid');
  for(const row of schemaByName.values())if(!isRecord(row.parameters))throw Error('capability_schema_capture_invalid');
  const declared=new Set();
  for(const name of declaredTools){if(typeof name!=='string'||!name||declared.has(name))throw Error('capability_declaration_duplicate');declared.add(name);}
  const registered=new Map();
  for(const value of registeredTools)addUnique(registered,normalizeRegistered(value),'capability_registration_invalid');
  for(const row of registered.values())if(typeof row.source!=='string'||!/^[A-Za-z][A-Za-z0-9_.:-]{0,159}$/.test(row.source))throw Error('capability_registration_invalid');
  if(!Array.isArray(adaptedTools)||adaptedTools.some(x=>typeof x!=='string'||!x))throw Error('capability_adapter_invalid');
  const adapted=new Set(adaptedTools);
  const allowList=runtimeConfig?.tools?.alsoAllow??[];
  if(!Array.isArray(allowList)||allowList.some(x=>typeof x!=='string'||!x)||new Set(allowList).size!==allowList.length)throw Error('capability_configuration_invalid');
  const allow=new Set(allowList);
  const names=[...new Set([...schemaByName.keys(),...declared,...registered.keys(),...adapted,...allow])].sort();
  const allowedRules=new Set(allowedRepairRules);
  for(const [name,rules] of Object.entries(repairRulesByTool))if(!supported.has(name)||!Array.isArray(rules)||rules.some(rule=>!allowedRules.has(rule)))throw Error('capability_repair_policy_invalid');
  const capabilities=names.map(name=>{
    const captured=schemaByName.get(name), implementation=registered.get(name), policy=capabilityPolicy(name,repairRulesByTool[name]??[]);
    const isAdapted=adapted.has(name), isRegistered=registered.has(name)||isAdapted;
    const schemaMatches=!implementation?.parameters||!captured?null:canonical(implementation.parameters)===canonical(captured.parameters);
    const runtime={registered:isRegistered,configured:allow.has(name),exposed:isRegistered&&captured!==undefined&&schemaMatches!==false&&allow.has(name)&&policy.supported,schemaCaptured:captured!==undefined,schemaMatches,declared:declared.has(name),registrationSource:implementation?.source??(isAdapted?'PINNED_RUNTIME_ADAPTER':null)};
    const base={schema:CONTRACT_VERSION,name,description:captured?.description??implementation?.description??'',arguments:captured?.parameters??null,implementation:{source:runtime.registrationSource},policy,limits:{maxResultChars:10000,maxTextChars:2400,maxItems:24},runtime};
    return deepFreeze({...base,digest:digest(base)});
  });
  const byName=Object.create(null);for(const x of capabilities)byName[x.name]=x;Object.freeze(byName);
  const mismatches=[];
  for(const x of capabilities){
    if(x.runtime.declared&&!x.runtime.registered)mismatches.push({name:x.name,kind:'DECLARED_REGISTRATION_MISSING'});
    if(x.runtime.registered&&!x.runtime.schemaCaptured)mismatches.push({name:x.name,kind:'REGISTERED_SCHEMA_MISSING'});
    if(x.runtime.schemaMatches===false)mismatches.push({name:x.name,kind:'REGISTERED_SCHEMA_DRIFT'});
    if(x.runtime.configured&&!x.runtime.exposed)mismatches.push({name:x.name,kind:'CONFIGURED_NOT_EXPOSED'});
    if(x.runtime.schemaCaptured&&!x.runtime.registered)mismatches.push({name:x.name,kind:'SCHEMA_UNREGISTERED'});
  }
  const projection={schema:CONTRACT_VERSION,capabilities:capabilities.map(({digest:ignored,...x})=>x)};
  return Object.freeze({schema:CONTRACT_VERSION,capabilities:Object.freeze(capabilities),byName,mismatches:deepFreeze(mismatches),digest:digest(projection)});
}
