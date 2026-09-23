import test from 'node:test';
import assert from 'node:assert/strict';
import {
 chmodSync,
 existsSync,
 lstatSync,
 mkdirSync,
 mkdtempSync,
 readFileSync,
 readdirSync,
 renameSync,
 rmSync,
 symlinkSync,
 writeFileSync,
} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {prepareContentTelemetryRecord} from '../content-telemetry/contract.mjs';
import {createContentTelemetrySpool} from '../content-telemetry/spool.mjs';

const enabled=Object.freeze({enabled:true,retention_days:30,access_policy:'owner_only'});
const base=()=>({
 schema_version:'sanctum.ai-interaction/v1',event_id:'event-1',interaction_id:'interaction-1',
 timestamp:'2026-09-22T17:00:00.000Z',correlation:{run_id:'run-1'},
 user_query:'Synthetic question',delivered_response:'Synthetic answer',outcome:'success',failure:null,
 model:{role:'answer',model:'synthetic-model',revision:'r1',provider:'local'},
});

function fixture(){
 const parent=mkdtempSync(join(tmpdir(),'sanctum-content-spool-')),root=join(parent,'content');
 return {parent,root,cleanup:()=>rmSync(parent,{recursive:true,force:true})};
}

test('disabled content telemetry creates and writes nothing',()=>{
 const f=fixture();
 try{
  const spool=createContentTelemetrySpool({config:{...enabled,enabled:false},root:f.root});
  assert.equal(spool.enabled,false);assert.equal(spool.append(base()),false);assert.equal(existsSync(f.root),false);
 }finally{f.cleanup();}
});

test('valid redacted records rotate atomically into the separate private pending spool',()=>{
 const f=fixture();
 try{
  const spool=createContentTelemetrySpool({config:enabled,root:f.root});
  assert.equal(spool.append({...base(),user_query:'Authorization: Bearer do-not-persist'}),true);
  for(const directory of [f.root,'pending','failed','quarantine','staging'].map(name=>name===f.root?name:join(f.root,name)))assert.equal(lstatSync(directory).mode&0o777,0o700);
  const pending=readdirSync(join(f.root,'pending'));assert.equal(pending.length,1);
  const file=join(f.root,'pending',pending[0]);assert.equal(lstatSync(file).mode&0o777,0o600);
  const stored=readFileSync(file,'utf8');assert.equal(stored.endsWith('\n'),true);assert.equal(stored.includes('do-not-persist'),false);assert.match(stored,/REDACTED/);
  assert.equal(existsSync(join(f.root,'ops')),false);assert.equal(readdirSync(join(f.root,'staging')).length,0);
 }finally{f.cleanup();}
});

test('insecure or symlinked roots fail open without changing their contents',()=>{
 const f=fixture();
 try{
  mkdirSync(f.root,{mode:0o755});chmodSync(f.root,0o755);
  assert.equal(createContentTelemetrySpool({config:enabled,root:f.root}).append(base()),false);
  rmSync(f.root,{recursive:true});mkdirSync(join(f.parent,'target'),{mode:0o700});symlinkSync(join(f.parent,'target'),f.root);
  assert.equal(createContentTelemetrySpool({config:enabled,root:f.root}).append(base()),false);
  assert.deepEqual(readdirSync(join(f.parent,'target')),[]);
 }finally{f.cleanup();}
});

test('recovery preserves complete staged and failed records and quarantines partial or malformed files',()=>{
 const f=fixture();
 try{
  const spool=createContentTelemetrySpool({config:enabled,root:f.root});assert.equal(spool.append(base()),true);
  const pendingDir=join(f.root,'pending'),failedDir=join(f.root,'failed'),stagingDir=join(f.root,'staging');
  const first=readdirSync(pendingDir)[0];renameSync(join(pendingDir,first),join(failedDir,first));
  const complete=JSON.stringify(prepareContentTelemetryRecord({...base(),event_id:'event-2'}))+'\n';
  writeFileSync(join(stagingDir,'complete.partial'),complete,{mode:0o600,flag:'wx'});
  writeFileSync(join(stagingDir,'partial.partial'),complete.slice(0,-8),{mode:0o644,flag:'wx'});
  writeFileSync(join(pendingDir,'malformed.jsonl'),'{"schema_version":"bad"}\n',{mode:0o600,flag:'wx'});
  writeFileSync(join(f.root,'.writer.lock'),JSON.stringify({pid:2147483647})+'\n',{mode:0o600,flag:'wx'});
  const recovered=spool.recover();
  assert.deepEqual(recovered,{pending:1,failed:1,quarantined:2});
  assert.equal(readdirSync(failedDir).length,1);assert.equal(readdirSync(pendingDir).length,1);
  const quarantined=readdirSync(join(f.root,'quarantine'));assert.equal(quarantined.length,2);assert.equal(readdirSync(stagingDir).length,0);
  for(const name of quarantined)assert.equal(lstatSync(join(f.root,'quarantine',name)).mode&0o777,0o600);
  assert.equal(existsSync(join(f.root,'.writer.lock')),false);
 }finally{f.cleanup();}
});

test('record and byte limits reject new content without discarding pending state',()=>{
 const f=fixture();
 try{
  const one=createContentTelemetrySpool({config:enabled,root:f.root,limits:{max_records:1,max_bytes:65536}});
  assert.equal(one.append(base()),true);assert.equal(one.append({...base(),event_id:'event-2'}),false);assert.equal(readdirSync(join(f.root,'pending')).length,1);
  const g=fixture();
  try{
   const bytes=createContentTelemetrySpool({config:enabled,root:g.root,limits:{max_records:10,max_bytes:65536}});
   assert.equal(bytes.append({...base(),user_query:'x'.repeat(16000),delivered_response:'y'.repeat(32768)}),true);
   assert.equal(bytes.append({...base(),event_id:'event-2',user_query:'x'.repeat(16000),delivered_response:'y'.repeat(32768)}),false);
   assert.equal(readdirSync(join(g.root,'pending')).length,1);
  }finally{g.cleanup();}
 }finally{f.cleanup();}
});

test('malformed records and spool failures neither persist nor log raw content',()=>{
 const f=fixture(),messages=[];
 const original=console.error;console.error=(...args)=>messages.push(args.join(' '));
 try{
  const spool=createContentTelemetrySpool({config:enabled,root:f.root});
  assert.doesNotThrow(()=>assert.equal(spool.append({...base(),reasoning:'PRIVATE_RAW_CONTENT'}),false));
  assert.equal(existsSync(f.root),false);assert.deepEqual(messages,[]);
  writeFileSync(f.root,'not a directory',{mode:0o600});
  assert.doesNotThrow(()=>assert.equal(spool.append({...base(),user_query:'PRIVATE_RAW_CONTENT'}),false));assert.deepEqual(messages,[]);
 }finally{console.error=original;f.cleanup();}
});
