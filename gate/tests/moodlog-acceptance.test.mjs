/* Synthetic oracle calibration only. No live candidate is imported by repo tests. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {stagePlan} from '../plugin/work-stages.mjs';
const oracle=readFileSync(new URL('../qualification/moodlog/persistence.test.cjs',import.meta.url),'utf8');
const contract=JSON.parse(readFileSync(new URL('../qualification/moodlog/task-protection.json',import.meta.url),'utf8'));
const prompt=readFileSync(new URL('../qualification/moodlog/task.txt',import.meta.url),'utf8');
// Deliberately separate synthetic control, never seeded into a Qwen workspace.
const control=`
const valid=x=>x&&['Great','Good','Okay','Low','Rough'].includes(x.mood)&&(x.note===null||typeof x.note==='string'&&x.note.length<=120)&&Number.isFinite(x.timestamp)&&x.timestamp>=0;
module.exports={
 loadHistory(s){try{const a=JSON.parse(s.getItem('synthetic'));return Array.isArray(a)?a.filter(valid).slice(0,5):[];}catch{return [];}},
 saveHistory(s,a){try{s.setItem('synthetic',JSON.stringify(a.slice(0,5)));return true;}catch{return false;}},
 clearStoredHistory(s){try{s.removeItem('synthetic');return true;}catch{return false;}}
};`;
function run(source){
 const env={...process.env};delete env.NODE_TEST_CONTEXT;
 const dir=mkdtempSync(join(tmpdir(),'sanctum-oracle-'));
 try{writeFileSync(join(dir,'persistence.test.cjs'),oracle);if(source!==null)writeFileSync(join(dir,'storage.js'),source);return spawnSync(process.execPath,['--test','persistence.test.cjs'],{cwd:dir,env,encoding:'utf8',timeout:15000});}
 finally{rmSync(dir,{recursive:true,force:true});}
}
test('MoodLog oracle and protected contract agree; focused prompt fits admission',()=>{
 assert.equal(prompt.length<4000,true);
 const continuation=readFileSync(new URL('../qualification/moodlog/continuation-task.txt',import.meta.url),'utf8');
 const stages=JSON.parse(readFileSync(new URL('../qualification/moodlog/continuation-stages.json',import.meta.url),'utf8'));
 const plan=stagePlan(continuation,stages);
 assert.equal(plan.length,3);
 for(const checkpoint of plan)assert.ok(checkpoint.task.length<=4000);
 assert.deepEqual(contract.protected,['persistence.test.cjs']);
 assert.equal(contract.acceptance.runner,'node-test-v1');
 assert.deepEqual([...oracle.matchAll(/^test\('([^']+)'/gm)].map(x=>x[1]),contract.acceptance.entries[0].names);
 const result=run(control);assert.equal(result.status,0,result.stdout+result.stderr);
});
test('post-UI MoodLog plan uses the repaired Node-only test environment',()=>{
 const goal=readFileSync(new URL('../qualification/moodlog/post-ui-task.txt',import.meta.url),'utf8');
 const stages=JSON.parse(readFileSync(new URL('../qualification/moodlog/post-ui-stages.json',import.meta.url),'utf8'));
 const plan=stagePlan(goal,stages);
 assert.deepEqual(plan.map(x=>x.name),['persistence-wiring','documentation']);
 for(const checkpoint of plan)assert.ok(checkpoint.task.length<=4000);
 assert.ok(stages[0].required_files.includes('ui.test.js'));
 const fixture=readFileSync(new URL('../qualification/moodlog/ui.test.js',import.meta.url),'utf8');
 const imports=[...fixture.matchAll(/^import .* from '([^']+)';$/gm)].map(x=>x[1]);
 assert.deepEqual(imports,['node:test','node:assert/strict','node:fs','node:vm']);
 assert.match(fixture,/runInContext\(readFileSync\(new URL\(filename, import\.meta\.url\)/);
 const syntax=spawnSync(process.execPath,['--check',fileURLToPath(new URL('../qualification/moodlog/ui.test.js',import.meta.url))],{encoding:'utf8',timeout:15000});
 assert.equal(syntax.status,0,syntax.stdout+syntax.stderr);
});
test('MoodLog acceptance rejects missing persistence and behavior regressions',()=>{
 for(const [name,source] of [
  ['missing module',null],
  ['reload erased',control.replace("const a=JSON.parse(s.getItem('synthetic'))","const a=[]")],
  ['save omitted',control.replace("s.setItem('synthetic',JSON.stringify(a.slice(0,5)));",'')],
  ['clear omitted',control.replace("s.removeItem('synthetic');",'')],
  ['unbounded history',control.replaceAll('.slice(0,5)','')],
  ['invalid data accepted',control.replace('.filter(valid)','')],
  ['write failure lied about',control.replaceAll('catch{return false;}','catch{return true;}')],
 ]){const result=run(source);assert.equal(result.error,undefined,name);assert.notEqual(result.status,0,name);}
});
