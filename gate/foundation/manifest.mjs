/* Runtime projection of registered schema capture plus Mac-owned policy metadata. */
import {CONTRACT_VERSION,digest,isRecord} from './contracts.mjs';

const localUtilities=new Set(['calc','date_math','unit_convert','structured_parse']);
const mutations=new Map([
  ['save_local_markdown','CREATE_ONLY'],['steward_create_folder','UNDO_CAPABILITY'],['steward_move','UNDO_CAPABILITY'],['steward_rename','UNDO_CAPABILITY'],['steward_undo_last','NONE']
]);
const personal=/^(messages_|gmail_|calendar_|steward_|save_local_markdown$)/;
const external=new Set(['web_search','web_fetch','vinceai__hub_repo_search']);
const approvals=new Set(['browser','steward_move','steward_rename','steward_undo_last','vinceai__hub_repo_search']);

export function capabilityPolicy(name){
  const rollback=mutations.get(name)??'NONE';
  const effect=mutations.has(name)?'MUTATION':name==='browser'?'CONTROL':'READ';
  const personalOutput=personal.test(name)||name==='browser';
  // Egress tools may receive a query derived from private context even when
  // their own response is public. Classify their input conservatively.
  const personalInput=personalOutput||external.has(name);
  return Object.freeze({effect,rollback,authority:approvals.has(name)?'ASK_OR_ALLOW_ONCE':'ALLOW',egress:external.has(name)?'DESTINATION_BOUND':'LOCAL_ONLY',dataClass:personalInput?'PERSONAL':'PUBLIC',inputDataClass:personalInput?'PERSONAL':'PUBLIC',outputDataClass:personalOutput?'PERSONAL':'PUBLIC',untrusted:!localUtilities.has(name),repair:localUtilities.has(name)||/^(messages_|gmail_|calendar_|steward_)/.test(name)?'ALLOWLISTED':'NONE',verifiers:localUtilities.has(name)?['exact_utility']:[],remoteResultEligible:false});
}

export function deriveCapabilityManifest({schemas=[],declaredTools=[],runtimeConfig={}}={}){
  const schemaByName=new Map();
  for(const row of schemas){
    if(!isRecord(row)||typeof row.name!=='string'||!isRecord(row.parameters)||schemaByName.has(row.name))throw Error('capability_schema_capture_invalid');
    schemaByName.set(row.name,row.parameters);
  }
  const declared=new Set(declaredTools);
  const allow=new Set(runtimeConfig?.tools?.alsoAllow??[]);
  const names=[...new Set([...schemaByName.keys(),...declared])].sort();
  const capabilities=names.map(name=>{
    const schema=schemaByName.get(name), policy=capabilityPolicy(name);
    const runtime={registered:declared.has(name)||schema!==undefined,configured:allow.has(name),exposed:schema!==undefined&&allow.has(name),schemaCaptured:schema!==undefined,declared:declared.has(name)};
    const base={schema:CONTRACT_VERSION,name,arguments:schema??null,policy,runtime};
    return Object.freeze({...base,digest:digest(base)});
  });
  const byName=new Map(capabilities.map(x=>[x.name,x]));
  const mismatches=capabilities.filter(x=>x.runtime.declared!==x.runtime.schemaCaptured).map(x=>Object.freeze({name:x.name,kind:x.runtime.declared?'DECLARED_SCHEMA_MISSING':'SCHEMA_UNDECLARED'}));
  const projection={schema:CONTRACT_VERSION,capabilities:capabilities.map(({digest:ignored,...x})=>x)};
  return Object.freeze({schema:CONTRACT_VERSION,capabilities:Object.freeze(capabilities),byName,mismatches:Object.freeze(mismatches),digest:digest(projection)});
}
