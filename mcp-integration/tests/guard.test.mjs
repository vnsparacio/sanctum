import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {decide,INPUT} from '../guard/policy.js';
const call=(tool,params)=>decide({toolName:'vinceai__'+tool,params});
test('unrelated existing brokers are untouched',()=>assert.equal(decide({toolName:'gmail_read',params:{}}),undefined));
test('management, resource access and unapproved tools are blocked',()=>{
  for(const name of ['mcp-add','mcp-find','mcp-remove','mcp-config-set','resources_read','browser_run_code','merge_pull_request']) assert.equal(call(name,{}).block,true);
});
test('time accepts deterministic arguments only',()=>{
  assert.equal(call('get_current_time',{timezone:'Asia/Tokyo'}),undefined);
  assert.equal(call('get_current_time',{timezone:'Asia/Tokyo',secret:'hidden'}).block,true);
  assert.equal(call('convert_time',{source_timezone:'UTC',target_timezone:'Asia/Tokyo',time:'09:00'}).block,true);
  assert.equal(call('convert_time',{source_timezone:'UTC',target_timezone:'bad zone',time:'99:99'}).block,true);
});
test('all external tools require one-call operator approval',()=>{
  for(const [name,p] of [['hub_repo_search',{query:'private data'}]]) {
    const r=call(name,p);assert.deepEqual(r.requireApproval.allowedDecisions,['allow-once','deny']);
    assert.ok(!r.requireApproval.description.includes('private data'));
  }
});
test('unsafe URL forms are blocked before approval',()=>{
  for(const url of ['file:///etc/passwd','http://127.0.0.1:8080','http://host.docker.internal','http://169.254.169.254','http://[::1]','https://user:pass@example.com','https://example.com:9999'])assert.equal(call('fetch',{url}).block,true);
  assert.equal(call('read_documentation',{url:'https://evil.example/docs.aws.amazon.com'}).block,true);
});
test('bounded query and retrieval output',()=>{
  assert.equal(call('search_papers',{query:'x'.repeat(2001)}).block,true);
  assert.equal(call('hub_repo_search',{query:'x'.repeat(2001)}).block,true);
  assert.equal(call('hub_repo_search',{query:'Qwen',limit:100}).params.limit,1);
  assert.equal(call('search_papers',{query:'attention',max_results:50}).block,true);
});
test('offline document path stays inside one read-only mount',()=>{
  fs.mkdirSync(INPUT,{recursive:true});fs.writeFileSync(path.join(INPUT,'guard-test.html'),'<p>test</p>');
  try{
    assert.equal(call('convert_to_markdown',{uri:'file:///mcp-input/guard-test.html'}).params.uri,'file:///mcp-input/guard-test.html');
    for(const uri of ['https://example.com/a.pdf','data:text/plain,private','file:///etc/passwd','file:///mcp-input/../../etc/passwd']) assert.equal(call('convert_to_markdown',{uri}).block,true);
    fs.symlinkSync('/etc/passwd',path.join(INPUT,'guard-link'));
    assert.equal(call('convert_to_markdown',{uri:'file:///mcp-input/guard-link'}).block,true);
  }finally{fs.rmSync(path.join(INPUT,'guard-link'),{force:true});fs.rmSync(path.join(INPUT,'guard-test.html'),{force:true});}
});

test('configured private input replaces repository fixtures',async()=>{
  const {spawnSync}=await import('node:child_process');
  const os=await import('node:os');
  const dir=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'mcp-input-')));
  try{
    fs.writeFileSync(path.join(dir,'private.html'),'<p>synthetic</p>');
    const result=spawnSync(process.execPath,['--input-type=module','-e',`import {decide,INPUT} from ${JSON.stringify(new URL('../guard/policy.js',import.meta.url).href)};const r=decide({toolName:'vinceai__convert_to_markdown',params:{uri:'file:///mcp-input/private.html'}});if(INPUT!==process.env.VINCEAI_MCP_INPUT_DIR||r?.params?.uri!=='file:///mcp-input/private.html')process.exit(1);`],{env:{...process.env,VINCEAI_MCP_INPUT_DIR:dir}});
    assert.equal(result.status,0);
  }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
