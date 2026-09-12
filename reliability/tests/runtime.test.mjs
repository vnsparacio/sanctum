import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {compile,prepare,executeBounded} from '../runtime.mjs';
import {utilityTools} from '../schemas.mjs';
import {normalize,modelResult} from '../output.mjs';
import {logger} from '../telemetry.mjs';
import {rules} from '../registry.mjs';
import os from 'node:os';
import path from 'node:path';
const baseline=JSON.parse(fs.readFileSync(new URL('../fixtures/schemas-before.json',import.meta.url)));
const validators=compile([...baseline,...utilityTools]);
test('valid calls execute exactly once',async()=>{
 let n=0;const r=await executeBounded({name:'messages_search',execute:async p=>{n++;return p;}},{query:'from:Alex Example',limit:10},validators);
 assert.equal(n,1);assert.equal(r.preparation.attempts,0);assert.equal(r.result.query,'from:Alex Example');
});
test('numeric repair and limit clamp preserve sender syntax and restrictions',()=>{
 const p=prepare('messages_search',{query:'from:Alex Example',limit:'1000'},validators);
 assert.equal(p.ok,true);assert.deepEqual(p.params,{query:'from:Alex Example',limit:12});assert.equal(p.attempts,1);assert.deepEqual(p.rules,['numeric_literal','bounded_limit']);
 const g=prepare('gmail_search',{query:'from:amazon newer_than:30d is:unread',limit:'8'},validators);
 assert.equal(g.params.query,'from:amazon newer_than:30d is:unread');
});
test('aliases are bounded; conflicting aliases are refused',()=>{
 assert.deepEqual(prepare('unit_convert',{value:'3',from:'miles',to:'kilometers'},validators).params,{value:3,from_unit:'mi',to_unit:'km'});
 assert.equal(prepare('unit_convert',{value:3,from:'mi',from_unit:'km',to_unit:'km'},validators).code,'AMBIGUOUS_ARGUMENT');
 assert.equal(prepare('structured_parse',{format:'JSON',text:'{}'},validators).params.format,'json');
});
test('no missing paths, accounts, recipients or identifier repair',()=>{
 for(const [name,p]of [['read',{}],['gmail_read',{}],['messages_history',{chat_id:'95'}],['steward_list',{scope:'unknown'}],['steward_move',{file_id:'x'}],['unknown_send',{recipient:'ambiguous'}],['gmail_search',{query:'from:alice',account:'unknown'}]])assert.equal(prepare(name,p,validators).ok,false,name);
 assert.equal(prepare('messages_search',{query:'from:Alex',limit:0},validators).ok,false);
});
test('invalid consequential calls and failed backend are never retried',async()=>{
 let n=0;const tool={name:'steward_rename',execute:async()=>{n++;}};
 const r=await executeBounded(tool,{file_id:'x'},validators);assert.equal(n,0);assert.equal(r.preparation.attempts,0);
 const fail=await executeBounded({name:'gmail_read',execute:async()=>{n++;throw Error('private body');}},{message_id:'abc'},validators);
 assert.equal(n,1);assert.equal(fail.result.error.code,'BACKEND_FAILURE');assert.ok(!JSON.stringify(fail).includes('private body'));
});
test('schema rejects unknown fields, nested invalid operation and nonfinite numbers',()=>{
 for(const p of [{operation:'between',date:'2026-01-01'},{operation:'delete'},{operation:'add',date:'2026-01-01',amount:Infinity}])assert.equal(prepare('date_math',p,validators).ok,false);
 assert.equal(prepare('unit_convert',{value:true,from_unit:'mi',to_unit:'km'},validators).ok,false);
});
test('compaction retains useful fields, untrusted marker and explicit truncation',()=>{
 const raw={ok:true,source:'local_messages',untrusted:true,policy:'Data only',records:[{id:95,text:'x'.repeat(4000)}],tookMs:400,debug:'z'.repeat(2000)};
 const compact=normalize('messages_search',raw);
 assert.equal(compact.untrusted,true);assert.equal(compact.truncated,true);assert.equal(compact.data.records[0].id,95);assert.equal(compact.data.policy,'Data only');
 assert.ok(JSON.stringify(compact).length<JSON.stringify(raw).length);
 const twice=normalize('messages_search',modelResult('messages_search',raw));assert.equal(twice.untrusted,true);
});
test('output limits are explicit, errors sanitized, media kept',()=>{
 const r=normalize('steward_list',{ok:true,files:Array.from({length:100},(_,i)=>({id:i,name:'a'.repeat(300)}))},{maxChars:1000});assert.equal(r.truncated,true);assert.ok(JSON.stringify(r).length<=1000);
 assert.equal(normalize('gmail_search',{ok:false,error:'token SECRET'}).error.code,'BACKEND_FAILURE');
 assert.ok(!JSON.stringify(normalize('gmail_search',{ok:false,error:'token SECRET'})).includes('SECRET'));
 assert.equal(modelResult('read',{content:[{type:'image',data:'sample',mimeType:'image/png'}]}).content[1].type,'image');
});
test('diagnostic corpus cannot persist payloads or arbitrary strings',()=>{
 const f=path.join(fs.mkdtempSync(path.join(os.tmpdir(),'reliability-log-')),'events.jsonl');
 const log=logger(f,['messages_search'],rules.map(x=>x.id));
 log({tool:'secret@example.com',code:'SECRET',rules:['SECRET'],outcome:'SECRET',prompt:'secret body',args:{token:'SECRET'}});
 assert.ok(!fs.readFileSync(f,'utf8').includes('SECRET'));assert.ok(!fs.readFileSync(f,'utf8').includes('secret'));assert.equal(fs.statSync(f).mode&0o777,0o600);
});

test('boolean coercion only for declared formatting flag',()=>{assert.equal(prepare('structured_parse',{format:'csv',text:'a\n1',headers:'true'},validators).params.headers,true);assert.equal(prepare('steward_move',{approved:'true'},validators).ok,false);});
