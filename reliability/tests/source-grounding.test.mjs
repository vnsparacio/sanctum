import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import {normalize,modelResult} from '../output.mjs';
import {gmailSearchResult} from '../../plugins/gmail-read-tools/dist/index.js';
import {messagesModelResult} from '../../plugins/messages-read-tools/dist/index.js';
import {fileMetadataResult} from '../../plugins/file-steward/dist/index.js';
const cases=JSON.parse(fs.readFileSync(new URL('../source-grounding-v1/fixtures.json',import.meta.url)));
test('source-grounding fixtures survive normalization with distinct content, metadata and trust',()=>{
 for(const c of cases)for(const s of c.steps){
  let raw=s.result;
  if(s.tool==='gmail_search')raw=gmailSearchResult(raw);
  if(s.tool.startsWith('messages_'))raw=messagesModelResult(raw);
  if(s.tool.startsWith('steward_'))raw=fileMetadataResult(raw);
  const r=normalize(s.tool,raw);
  if(!['calc','date_math','unit_convert'].includes(s.tool))assert.equal(r.untrusted,true,c.id);
  assert.equal(r.ok,true,c.id);
  const text=JSON.stringify(r);
  if(s.tool==='messages_search'||s.tool==='messages_history'){assert.ok(text.includes('messageSentAt'));assert.ok(!text.includes('created_at'));}
  if(s.tool==='gmail_search'){assert.ok(text.includes('emailReceivedAt'));assert.ok(!text.includes('"date":'));assert.ok(text.includes('metadataOnly'));}
  if(s.tool==='steward_list'||s.tool==='steward_inspect'){assert.ok(text.includes('fileModifiedAt'));assert.ok(!text.includes('"modified":'));}
  assert.deepEqual(normalize(s.tool,modelResult(s.tool,{details:raw,content:[{type:"text",text:JSON.stringify(raw)}]})),r,c.id);
 }
});
test('truncated/unavailable source content never becomes invented content in normalized results',()=>{
 for(const [tool,raw]of [['steward_inspect',{ok:true,preview_available:false,preview_reason:'unsupported file type'}],['vinceai__convert_to_markdown',{markdown:'x'.repeat(9000),truncated:true}]]){
  const r=normalize(tool,raw);assert.equal(r.untrusted,true);
  if(tool==='steward_inspect'){assert.equal(r.data.preview_available,false);assert.equal(r.data.preview,undefined);}
  else assert.equal(r.truncated,true);
 }
 const absent=normalize('structured_parse',{ok:true,valid:true,value:{status:'pending'}});assert.equal(absent.data.value.reservationDate,undefined);
});

test('Messages fixture fields are retained by the actual broker sanitizers',()=>{
 const script=new URL('../source-grounding-v1/check-message-fixtures.py',import.meta.url);
 assert.match(execFileSync('python3',[script.pathname],{encoding:'utf8'}),/PASS/);
});
