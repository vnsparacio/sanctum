import test from 'node:test';
import assert from 'node:assert/strict';
import {chmodSync,mkdtempSync,readFileSync,readdirSync,rmSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {createContentTelemetrySpool} from '../content-telemetry/spool.mjs';
import {createAwsCliContentClient,createContentTelemetryDelivery,validateContentDeliveryConfig} from '../content-telemetry/delivery.mjs';

const policy=Object.freeze({enabled:true,retention_days:30,access_policy:'owner_only'});
const config=Object.freeze({schema:'sanctum.content-delivery/v1',enabled:true,aws_cli:'/synthetic/aws',aws_profile:'sanctum-content-writer',region:'us-west-2',bucket:'synthetic-content-bucket',prefix:'content/',max_batches_per_run:10,max_attempts:3,base_backoff_ms:1,max_backoff_ms:2});
const record=(event_id='event-1')=>({schema_version:'sanctum.ai-interaction/v1',event_id,interaction_id:'interaction-1',timestamp:'2026-09-22T17:00:00.000Z',correlation:{run_id:'run-1'},user_query:'Synthetic question',delivered_response:'Synthetic answer',outcome:'success',failure:null,model:{role:'answer',model:'synthetic-model',revision:'r1',provider:'local'}});
function fixture(){const parent=mkdtempSync(join(tmpdir(),'sanctum-content-delivery-')),root=join(parent,'content');return {parent,root,cleanup:()=>rmSync(parent,{recursive:true,force:true})};}
function fakeClient({ambiguous=false,alwaysFail=false}={}){
 const objects=new Map(),puts=[];
 return {objects,puts,async putObject({key,digest,body}){puts.push({key,digest,body});if(alwaysFail)return 'unknown';if(objects.has(key))return 'exists';objects.set(key,{digest,body});return ambiguous?'unknown':'uploaded';}};
}

test('one complete batch maps to one immutable content object and leaves ops untouched',async()=>{
 const f=fixture();try{
  const spool=createContentTelemetrySpool({config:policy,root:f.root});assert.equal(spool.append(record()),true);
  const client=fakeClient(),delivery=createContentTelemetryDelivery({config,root:f.root,client,sleep:async()=>{}});
  assert.deepEqual(await delivery.run(),{examined:1,uploaded:1,reconciled:0,failed:0,quarantined:0});
  assert.equal(client.objects.size,1);assert.equal(client.puts.length,1);assert.match(client.puts[0].key,/^content\/2026\/09\/22\/event-1-[a-f0-9]{64}\.jsonl$/);
  assert.equal(client.puts[0].body.endsWith('\n'),true);assert.deepEqual(readdirSync(join(f.root,'pending')),[]);assert.equal(readdirSync(f.root).includes('ops'),false);
 }finally{f.cleanup();}
});

test('ambiguous completion is reconciled and replay never overwrites',async()=>{
 const f=fixture();try{
  const spool=createContentTelemetrySpool({config:policy,root:f.root});assert.equal(spool.append(record()),true);
  const client=fakeClient({ambiguous:true}),delivery=createContentTelemetryDelivery({config,root:f.root,client,sleep:async()=>{}});
  assert.deepEqual(await delivery.run(),{examined:1,uploaded:0,reconciled:1,failed:0,quarantined:0});
  assert.equal(client.puts.length,2);assert.equal(spool.append(record()),true);
  assert.deepEqual(await delivery.run(),{examined:1,uploaded:0,reconciled:1,failed:0,quarantined:0});assert.equal(client.puts.length,3);assert.equal(client.objects.size,1);
 }finally{f.cleanup();}
});

test('bounded retries preserve failed batches for a later run',async()=>{
 const f=fixture(),delays=[];try{
  const spool=createContentTelemetrySpool({config:policy,root:f.root});spool.append(record());
  const client=fakeClient({alwaysFail:true}),delivery=createContentTelemetryDelivery({config,root:f.root,client,sleep:async ms=>delays.push(ms)});
  assert.deepEqual(await delivery.run(),{examined:1,uploaded:0,reconciled:0,failed:1,quarantined:0});assert.equal(client.puts.length,3);assert.deepEqual(delays,[1,2]);assert.equal(readdirSync(join(f.root,'failed')).length,1);
  client.putObject=async({key,digest,body})=>{client.objects.set(key,{digest,body});return 'uploaded';};
  assert.deepEqual(await delivery.run(),{examined:1,uploaded:1,reconciled:0,failed:0,quarantined:0});assert.deepEqual(readdirSync(join(f.root,'failed')),[]);
 }finally{f.cleanup();}
});

test('partial, malformed, and non-private batches are quarantined without upload',async()=>{
 const f=fixture();try{
  createContentTelemetrySpool({config:policy,root:f.root}).append(record());const pending=join(f.root,'pending');
  writeFileSync(join(pending,'partial.jsonl'),'{"partial":',{mode:0o600});writeFileSync(join(pending,'malformed.jsonl'),'{"schema_version":"bad"}\n',{mode:0o600});writeFileSync(join(pending,'public.jsonl'),readFileSync(join(pending,readdirSync(pending)[0])),{mode:0o600});chmodSync(join(pending,'public.jsonl'),0o644);
  const client=fakeClient(),summary=await createContentTelemetryDelivery({config,root:f.root,client,sleep:async()=>{}}).run();
  assert.deepEqual(summary,{examined:4,uploaded:1,reconciled:0,failed:0,quarantined:3});assert.equal(client.puts.length,1);assert.equal(readdirSync(join(f.root,'quarantine')).length,3);
 }finally{f.cleanup();}
});

test('destination refuses ops and unknown or credential-like configuration fields',()=>{
 assert.equal(validateContentDeliveryConfig(config),true);
 assert.equal(validateContentDeliveryConfig({...config,prefix:'ops/content/'}),false);
 assert.equal(validateContentDeliveryConfig({...config,prefix:'content/ops/'}),false);
 assert.equal(validateContentDeliveryConfig({...config,aws_secret_access_key:'synthetic-secret'}),false);
});

test('AWS adapter uses conditional put and suppresses provider output',async()=>{
 const calls=[],client=createAwsCliContentClient(config,{run:(command,args,options)=>{calls.push({command,args,options});return {status:255,stdout:'PRIVATE_OUTPUT',stderr:'PreconditionFailed (412) PRIVATE_DIAGNOSTIC'};}});
 assert.equal(await client.putObject({key:'content/key.jsonl',digest:'a'.repeat(64),file:'/private/batch.jsonl'}),'exists');
 assert.equal(calls.length,1);assert.equal(calls[0].command,'/synthetic/aws');assert.equal(calls[0].options.stdio[0],'ignore');
 assert.deepEqual(calls[0].args.slice(0,2),['s3api','put-object']);assert.equal(calls[0].args.includes('--if-none-match'),true);assert.equal(calls[0].args[calls[0].args.indexOf('--if-none-match')+1],'*');
 assert.equal(JSON.stringify(calls[0]).includes('AWS_SECRET_ACCESS_KEY'),false);
});
