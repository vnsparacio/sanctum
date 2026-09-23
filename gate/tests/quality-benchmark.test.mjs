import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,readdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {prepareContentTelemetryRecord} from '../content-telemetry/contract.mjs';
import {
 compareBenchmarkReplay,
 exportBenchmarkDataset,
 runOfflineReplay,
} from '../content-telemetry/benchmark.mjs';
import {
 createQualityAnnotation,
 createQualityAnnotationStore,
 prepareQualityAnnotationRecord,
} from '../content-telemetry/quality.mjs';

const fixturePath=fileURLToPath(new URL('./fixtures/quality-interactions.json',import.meta.url));
const interactions=()=>JSON.parse(readFileSync(fixturePath,'utf8'));
const annotation=(operation_id='rating-1')=>({
 operation_id,interaction_id:'interaction-quality-1',source:'OWNER_MANUAL',owner_rating:4,
 evaluator:null,benchmark:null,scores:[],pass:null,semantic_failure_category:'NONE',grounding:null,citation:null,
});

test('one interaction accepts multiple append-only annotations and exact operation replay is idempotent',()=>{
 const parent=mkdtempSync(join(tmpdir(),'sanctum-quality-')),root=join(parent,'annotations');
 try{
  let tick=0;
  const store=createQualityAnnotationStore({root,now:()=>Date.UTC(2026,8,22,17,0,tick++)});
  const first=store.append(annotation()),replay=store.append(annotation()),second=store.append({...annotation('evaluation-1'),source:'EVALUATOR',owner_rating:null,evaluator:{evaluator_id:'eval',evaluator_version:'v1',model:'judge',model_revision:'r2'},scores:[{name:'correctness',value:0.75}],pass:false,semantic_failure_category:'INCOMPLETE'});
  assert.equal(first.status,'created');assert.equal(replay.status,'unchanged');assert.equal(second.status,'created');
  assert.equal(first.annotation.annotation_id,replay.annotation.annotation_id);
  assert.notEqual(first.annotation.annotation_id,second.annotation.annotation_id);
  assert.equal(readdirSync(root).length,2);
  assert.throws(()=>store.append({...annotation(),owner_rating:1}),error=>error.code==='QUALITY_ANNOTATION_CONFLICT');
  assert.equal(readdirSync(root).length,2);
 }finally{rmSync(parent,{recursive:true,force:true});}
});

test('quality metadata is bounded, queryable, and cannot carry private content or authority',()=>{
 const record=createQualityAnnotation({...annotation('benchmark-1'),source:'BENCHMARK_REPLAY',owner_rating:null,benchmark:{benchmark_id:'suite',benchmark_version:'v1',test_case_id:'case-1',test_case_version:'v2'},scores:[{name:'groundedness',value:0.5}],pass:false,semantic_failure_category:'GROUNDING_ERROR',grounding:{status:'PARTIAL',score:0.5},citation:{status:'FAIL',score:0}},{now:()=>Date.UTC(2026,8,22,17)});
 assert.equal(record.authority_effect,'NONE');assert.equal(record.semantic_failure_category,'GROUNDING_ERROR');
 for(const [field,value] of [['reasoning','private chain'],['source_body','private source'],['tool_body','private tool output'],['instructions','authorize completion']]){
  assert.throws(()=>prepareQualityAnnotationRecord({...record,[field]:value}),error=>error.code==='QUALITY_ANNOTATION_SCHEMA'&&error.keywords.includes('additionalProperties')&&!error.message.includes('private'));
 }
 assert.throws(()=>prepareQualityAnnotationRecord({...record,evaluator:{evaluator_id:'eval',evaluator_version:'v1',model:'judge',model_revision:'r1',prompt:'private source body'}}),error=>error.code==='QUALITY_ANNOTATION_SCHEMA');
 assert.throws(()=>prepareContentTelemetryRecord({...interactions()[0],quality:{owner_rating:5}}),error=>error.code==='CONTENT_TELEMETRY_SCHEMA');
});

test('selected fixture interactions export to a bounded dataset and replay two model revisions',async()=>{
 const dataset=exportBenchmarkDataset({
  dataset_id:'synthetic-suite',dataset_version:'v1',interactions:interactions(),
  selections:[
   {interaction_id:'interaction-quality-1',test_case_id:'case-1',test_case_version:'v1'},
   {interaction_id:'interaction-quality-2',test_case_id:'case-2',test_case_version:'v1'},
  ],now:()=>Date.UTC(2026,8,22,18),
 });
 assert.deepEqual(dataset.cases.map(item=>item.interaction_id),['interaction-quality-1','interaction-quality-2']);
 const configurations=[
  {configuration_id:'model-r1',model:'synthetic-model',revision:'r1',provider:'operator-local'},
  {configuration_id:'model-r2',model:'synthetic-model',revision:'r2',provider:'operator-local'},
 ];
 const providers={
  'model-r1':async item=>({response:item.reference_response,latency_ms:1}),
  'model-r2':async item=>({response:item.test_case_id==='case-1'?item.reference_response:'different',latency_ms:2}),
 };
 const options={run_id:'replay-1',dataset,configurations,providers,now:()=>Date.UTC(2026,8,22,19)};
 const first=await runOfflineReplay(options),replay=await runOfflineReplay(options);
 assert.equal(first.replay_id,replay.replay_id);assert.equal(first.result_sets.length,2);
 assert.deepEqual(compareBenchmarkReplay(first).comparisons,[{configuration_id:'model-r2',exact_response_matches:1,case_count:2}]);
});

test('benchmark and replay inputs reject duplicates and provider metadata leakage',async()=>{
 const records=interactions();
 assert.throws(()=>exportBenchmarkDataset({dataset_id:'suite',dataset_version:'v1',interactions:[records[0],records[0]],selections:[{interaction_id:'interaction-quality-1',test_case_id:'case',test_case_version:'v1'}]}),error=>error.code==='BENCHMARK_INTERACTION_DUPLICATE');
 const dataset=exportBenchmarkDataset({dataset_id:'suite',dataset_version:'v1',interactions:[records[0]],selections:[{interaction_id:'interaction-quality-1',test_case_id:'case',test_case_version:'v1'}]});
 const configurations=[{configuration_id:'a',model:'m',revision:'r1',provider:'local'},{configuration_id:'b',model:'m',revision:'r2',provider:'local'}];
 const replay=await runOfflineReplay({run_id:'privacy-replay',dataset,configurations,providers:{a:async()=>({response:'safe',source_body:'PRIVATE_SOURCE'}),b:async()=>({response:'safe',reasoning:'PRIVATE_REASONING'})}});
 const serialized=JSON.stringify(replay);
 assert.equal(serialized.includes('PRIVATE_SOURCE'),false);assert.equal(serialized.includes('PRIVATE_REASONING'),false);
 assert.deepEqual(replay.result_sets.map(set=>set.results[0].failure_category),['INVALID_RESULT','INVALID_RESULT']);
 await assert.rejects(()=>runOfflineReplay({run_id:'duplicate',dataset,configurations:[configurations[0],configurations[0]],providers:{a:async()=>''}}),error=>error.code==='BENCHMARK_REPLAY_DUPLICATE_CONFIGURATION');
});
