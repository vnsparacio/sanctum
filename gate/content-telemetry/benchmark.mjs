import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import Ajv from 'ajv';
import {prepareContentTelemetryRecord,redactContentText} from './contract.mjs';

export const BENCHMARK_DATASET_SCHEMA_VERSION='sanctum.benchmark-dataset/v1';
export const BENCHMARK_REPLAY_SCHEMA_VERSION='sanctum.benchmark-replay/v1';

const datasetSchema=JSON.parse(readFileSync(fileURLToPath(new URL('../../config/schemas/benchmark-dataset-v1.schema.json',import.meta.url)),'utf8'));
const replaySchema=JSON.parse(readFileSync(fileURLToPath(new URL('../../config/schemas/benchmark-replay-v1.schema.json',import.meta.url)),'utf8'));
const ajv=new Ajv({allErrors:true,strict:true});
const validateDataset=ajv.compile(datasetSchema);
const validateReplay=ajv.compile(replaySchema);
const CONFIG_KEYS=Object.freeze(['configuration_id','model','revision','provider']);

function invalid(code,validator){
 const keywords=[...new Set((validator.errors??[]).map(item=>item.keyword))].sort();
 return Object.assign(new TypeError('invalid benchmark evidence'),{code,keywords});
}
function unique(values){return new Set(values).size===values.length;}
function prepare(value,validator,code){
 const clone=structuredClone(value);
 if(!validator(clone))throw invalid(code,validator);
 return Object.freeze(clone);
}
function timestamp(now){return new Date(now()).toISOString();}
function replayId(runId,dataset,configurations){
 const identity=[runId,dataset.dataset_id,dataset.dataset_version,configurations.map(item=>item.configuration_id)];
 return 'br-'+createHash('sha256').update(JSON.stringify(identity)).digest('hex');
}
function safeProviderResult(value){
 if(typeof value==='string')return {response:redactContentText(value),failure_category:'NONE',latency_ms:null};
 if(!value||typeof value!=='object'||Array.isArray(value))return {response:null,failure_category:'INVALID_RESULT',latency_ms:null};
 if(Object.keys(value).some(key=>!['response','latency_ms'].includes(key)))return {response:null,failure_category:'INVALID_RESULT',latency_ms:null};
 if(typeof value.response!=='string'||value.response.length>32768)return {response:null,failure_category:'INVALID_RESULT',latency_ms:null};
 if(value.latency_ms!==undefined&&(!Number.isSafeInteger(value.latency_ms)||value.latency_ms<0||value.latency_ms>86400000))return {response:null,failure_category:'INVALID_RESULT',latency_ms:null};
 return {response:redactContentText(value.response),failure_category:'NONE',latency_ms:value.latency_ms??null};
}

export function prepareBenchmarkDataset(value){
 const prepared=prepare(value,validateDataset,'BENCHMARK_DATASET_SCHEMA');
 if(!unique(prepared.cases.map(item=>item.test_case_id)))throw Object.assign(new TypeError('invalid benchmark evidence'),{code:'BENCHMARK_DATASET_DUPLICATE_CASE'});
 return prepared;
}

export function exportBenchmarkDataset({dataset_id,dataset_version,selections,interactions,now=()=>Date.now()}={}){
 if(!Array.isArray(selections)||!Array.isArray(interactions)||selections.length<1||selections.length>100)throw Object.assign(new TypeError('invalid benchmark selection'),{code:'BENCHMARK_SELECTION'});
 const records=interactions.map(prepareContentTelemetryRecord);
 if(!unique(records.map(item=>item.interaction_id)))throw Object.assign(new TypeError('duplicate interaction identity'),{code:'BENCHMARK_INTERACTION_DUPLICATE'});
 const byId=new Map(records.map(item=>[item.interaction_id,item]));
 const cases=selections.map(selection=>{
  if(!selection||typeof selection!=='object'||Array.isArray(selection)||Object.keys(selection).some(key=>!['interaction_id','test_case_id','test_case_version'].includes(key)))throw Object.assign(new TypeError('invalid benchmark selection'),{code:'BENCHMARK_SELECTION'});
  const record=byId.get(selection.interaction_id);
  if(!record)throw Object.assign(new TypeError('selected interaction not found'),{code:'BENCHMARK_INTERACTION_MISSING'});
  return {test_case_id:selection.test_case_id,test_case_version:selection.test_case_version,interaction_id:record.interaction_id,user_query:record.user_query,reference_response:record.delivered_response};
 });
 return prepareBenchmarkDataset({schema_version:BENCHMARK_DATASET_SCHEMA_VERSION,dataset_id,dataset_version,created_at:timestamp(now),authority_effect:'NONE',cases});
}

export function prepareBenchmarkReplay(value){
 const prepared=prepare(value,validateReplay,'BENCHMARK_REPLAY_SCHEMA');
 if(!unique(prepared.result_sets.map(item=>item.configuration_id)))throw Object.assign(new TypeError('duplicate replay configuration'),{code:'BENCHMARK_REPLAY_DUPLICATE_CONFIGURATION'});
 for(const resultSet of prepared.result_sets)if(!unique(resultSet.results.map(item=>item.test_case_id)))throw Object.assign(new TypeError('duplicate replay result'),{code:'BENCHMARK_REPLAY_DUPLICATE_RESULT'});
 return prepared;
}

export async function runOfflineReplay({run_id,dataset,configurations,providers,now=()=>Date.now()}={}){
 const preparedDataset=prepareBenchmarkDataset(dataset);
 if(!Array.isArray(configurations)||configurations.length<2||configurations.length>8||!providers||typeof providers!=='object')throw Object.assign(new TypeError('at least two operator-supplied replay configurations are required'),{code:'BENCHMARK_REPLAY_CONFIGURATIONS'});
 for(const config of configurations){
  if(!config||typeof config!=='object'||Array.isArray(config)||Object.keys(config).some(key=>!CONFIG_KEYS.includes(key))||typeof providers[config.configuration_id]!=='function')throw Object.assign(new TypeError('missing operator-supplied replay provider'),{code:'BENCHMARK_REPLAY_PROVIDER'});
 }
 if(!unique(configurations.map(item=>item.configuration_id)))throw Object.assign(new TypeError('duplicate replay configuration'),{code:'BENCHMARK_REPLAY_DUPLICATE_CONFIGURATION'});
 const result_sets=[];
 for(const config of configurations){
  const results=[];
  for(const item of preparedDataset.cases){
   let result;
   try{
    const packet=Object.freeze({test_case_id:item.test_case_id,user_query:item.user_query,reference_response:item.reference_response});
    result=safeProviderResult(await providers[config.configuration_id](packet));
   }catch{result={response:null,failure_category:'PROVIDER_ERROR',latency_ms:null};}
   results.push({test_case_id:item.test_case_id,...result});
  }
  result_sets.push({...structuredClone(config),results});
 }
 return prepareBenchmarkReplay({schema_version:BENCHMARK_REPLAY_SCHEMA_VERSION,replay_id:replayId(run_id,preparedDataset,configurations),run_id,created_at:timestamp(now),dataset:{dataset_id:preparedDataset.dataset_id,dataset_version:preparedDataset.dataset_version},authority_effect:'NONE',result_sets});
}

export function compareBenchmarkReplay(value){
 const replay=prepareBenchmarkReplay(value),[baseline,...others]=replay.result_sets;
 const baselineByCase=new Map(baseline.results.map(item=>[item.test_case_id,item]));
 return Object.freeze({
  replay_id:replay.replay_id,
  baseline_configuration_id:baseline.configuration_id,
  comparisons:others.map(candidate=>Object.freeze({
   configuration_id:candidate.configuration_id,
   exact_response_matches:candidate.results.filter(item=>item.response!==null&&item.response===baselineByCase.get(item.test_case_id)?.response).length,
   case_count:candidate.results.length,
  })),
 });
}
