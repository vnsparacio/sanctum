import test from 'node:test';
import assert from 'node:assert/strict';
import {
 CONTENT_TELEMETRY_DEFAULTS,
 CONTENT_TELEMETRY_MAX_RECORD_BYTES,
 prepareContentTelemetryRecord,
 redactContentText,
 validateContentTelemetryConfig,
} from '../content-telemetry/contract.mjs';

const base=()=>({
 schema_version:'sanctum.ai-interaction/v1',
 event_id:'event-1',
 interaction_id:'interaction-1',
 timestamp:'2026-09-22T17:00:00.000Z',
 correlation:{run_id:'run-1',session_id:'session-1',trace_id:'a'.repeat(32)},
 user_query:'Summarize this synthetic request.',
 delivered_response:'Synthetic delivered response.',
 outcome:'success',
 failure:null,
 model:{role:'answer',model:'synthetic-model',revision:'r1',provider:'local'},
 usage:{latency_ms:25,input_tokens:7,output_tokens:9},
});

test('contract represents success, failure, blocked, denied, and unknown outcomes',()=>{
 assert.equal(prepareContentTelemetryRecord(base()).outcome,'success');
 for(const outcome of ['failure','blocked','denied']){
  const record={...base(),outcome,delivered_response:null,failure:{stage:'MODEL',category:'UPSTREAM',code:'UNAVAILABLE'}};
  assert.equal(prepareContentTelemetryRecord(record).outcome,outcome);
 }
 const unknown={...base(),outcome:'unknown',delivered_response:null,failure:null};
 assert.equal(prepareContentTelemetryRecord(unknown).outcome,'unknown');
});

test('recognized credentials and private keys are redacted only in explicit content fields',()=>{
 const privateKey=`${['-----BEGIN','PRIVATE','KEY-----'].join(' ')}\nsynthetic-material\n${['-----END','PRIVATE','KEY-----'].join(' ')}`;
 const query='Authorization: Bearer synthetic-token api_key=synthetic-value '+privateKey;
 const response='Never repeat sk-proj-abcdefghijklmnop or ghp_abcdefghijklmnopqrstuvwxyz.';
 const prepared=prepareContentTelemetryRecord({...base(),user_query:query,delivered_response:response});
 const serialized=JSON.stringify(prepared);
 for(const secret of ['synthetic-token','synthetic-value','synthetic-material','sk-proj-abcdefghijklmnop','ghp_abcdefghijklmnopqrstuvwxyz'])assert.equal(serialized.includes(secret),false);
 assert.match(prepared.user_query,/\[REDACTED:CREDENTIAL\]/);
 assert.match(prepared.user_query,/\[REDACTED:PRIVATE_KEY\]/);
 assert.equal(redactContentText('ordinary text'),'ordinary text');
});

test('unknown and forbidden content-bearing fields are rejected without echoing values',()=>{
 for(const [field,value] of [['headers',{authorization:'synthetic'}],['cookies','synthetic'],['tool_body','synthetic'],['source_body','synthetic'],['file_contents','synthetic'],['reasoning','synthetic chain']]){
  assert.throws(()=>prepareContentTelemetryRecord({...base(),[field]:value}),error=>error.code==='CONTENT_TELEMETRY_SCHEMA'&&error.keywords.includes('additionalProperties')&&!error.message.includes('synthetic'));
 }
});

test('failure is structured and raw exception text is not accepted',()=>{
 assert.throws(()=>prepareContentTelemetryRecord({...base(),outcome:'failure',delivered_response:null,failure:{stage:'MODEL',category:'UPSTREAM',code:'UNAVAILABLE',message:'raw exception'}}),error=>error.code==='CONTENT_TELEMETRY_SCHEMA');
 assert.throws(()=>prepareContentTelemetryRecord({...base(),outcome:'failure',delivered_response:null,failure:null}),error=>error.code==='CONTENT_TELEMETRY_SCHEMA');
});

test('field and serialized record bounds are enforced',()=>{
 assert.throws(()=>prepareContentTelemetryRecord({...base(),user_query:'x'.repeat(16385)}),error=>error.code==='CONTENT_TELEMETRY_SCHEMA');
 const record={...base(),user_query:'x'.repeat(16000),delivered_response:'y'.repeat(32768)};
 assert.ok(Buffer.byteLength(JSON.stringify(prepareContentTelemetryRecord(record)))<=CONTENT_TELEMETRY_MAX_RECORD_BYTES);
 assert.throws(()=>prepareContentTelemetryRecord({...record,user_query:'😀'.repeat(16000),delivered_response:'😀'.repeat(32768)}),error=>error.code==='CONTENT_TELEMETRY_SIZE');
});

test('configuration is disabled by default and exposes bounded policy hooks only',()=>{
 assert.deepEqual(CONTENT_TELEMETRY_DEFAULTS,{enabled:false,retention_days:null,access_policy:'owner_only'});
 assert.equal(validateContentTelemetryConfig(CONTENT_TELEMETRY_DEFAULTS),true);
 assert.equal(validateContentTelemetryConfig({enabled:true,retention_days:30,access_policy:'owner_authorized_reviewers'}),true);
 assert.equal(validateContentTelemetryConfig({...CONTENT_TELEMETRY_DEFAULTS,endpoint:'private.example'}),false);
 assert.equal(validateContentTelemetryConfig({...CONTENT_TELEMETRY_DEFAULTS,retention_days:0}),false);
});
