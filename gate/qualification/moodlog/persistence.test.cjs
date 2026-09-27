/* Owner acceptance oracle. Copy unchanged into the private candidate and protect it.
 * Run candidate code only in the isolated Work Mode runner, never on the host.
 */
'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const vm=require('node:vm');
function adapter(){
 const file=path.join(__dirname,'storage.js');
 const context=vm.createContext({module:{exports:{}},exports:{}});
 new vm.Script(fs.readFileSync(file,'utf8'),{filename:'storage.js'}).runInContext(context,{timeout:1000});
 const api=context.module.exports;
 for(const name of ['loadHistory','saveHistory','clearStoredHistory'])assert.equal(typeof api[name],'function',`storage.js must export ${name}`);
 // Every candidate call has a VM deadline; the outer container remains the sandbox.
 return Object.fromEntries(['loadHistory','saveHistory','clearStoredHistory'].map(name=>[name,(...args)=>{
  context.__args=args;context.__method=name;
  return new vm.Script('module.exports[__method](...__args)').runInContext(context,{timeout:1000});
 }]));
}
const plain=value=>JSON.parse(JSON.stringify(value));
function memory(){
 const values=new Map();
 return {values,getItem:key=>values.get(String(key))??null,setItem:(key,value)=>values.set(String(key),String(value)),removeItem:key=>values.delete(String(key))};
}
const entry=(i=0)=>({mood:['Great','Good','Okay','Low','Rough'][i%5],note:i===0?null:`synthetic ${i}`,timestamp:1700000000000+i});

test('moodlog: save and reload the newest five entries',()=>{
 const store=memory(),rows=Array.from({length:7},(_,i)=>entry(6-i));
 assert.equal(adapter().saveHistory(store,rows),true);
 assert.ok(store.values.size>0,'must write storage');
 assert.deepEqual(plain(adapter().loadHistory(store)),rows.slice(0,5));
 assert.deepEqual(rows,Array.from({length:7},(_,i)=>entry(6-i)),'must not mutate caller input');
});
test('moodlog: clearing persists across a fresh load',()=>{
 const store=memory();assert.equal(adapter().saveHistory(store,[entry()]),true);
 assert.equal(adapter().clearStoredHistory(store),true);
 assert.deepEqual(plain(adapter().loadHistory(store)),[]);
});
test('moodlog: malformed stored data is safe and invalid entries are discarded',()=>{
 const store=memory();assert.deepEqual(plain(adapter().loadHistory(store)),[]);
 adapter().saveHistory(store,[entry()]);assert.equal(store.values.size,1,'use one history key');
 const key=[...store.values.keys()][0];
 for(const bad of ['{broken','null','{}','42','"text"']){
  store.values.set(key,bad);assert.deepEqual(plain(adapter().loadHistory(store)),[]);
 }
 const invalid=[null,{}, {...entry(),mood:'invalid'},{...entry(),note:'x'.repeat(121)},{...entry(),note:42},{...entry(),timestamp:'yesterday'},{...entry(),timestamp:-1}];
 store.values.set(key,JSON.stringify([...invalid,entry(),{...entry(1),note:'x'.repeat(120)}]));
 assert.deepEqual(plain(adapter().loadHistory(store)),[entry(),{...entry(1),note:'x'.repeat(120)}]);
 store.values.set(key,JSON.stringify(Array.from({length:7},(_,i)=>entry(i))));
 assert.equal(adapter().loadHistory(store).length,5);
});
test('moodlog: unavailable storage returns an explicit failure without throwing',()=>{
 const store={getItem(){throw Error('denied');},setItem(){throw Error('quota');},removeItem(){throw Error('denied');}};
 assert.deepEqual(plain(adapter().loadHistory(store)),[]);
 assert.equal(adapter().saveHistory(store,[entry()]),false);
 assert.equal(adapter().clearStoredHistory(store),false);
 for(const missing of [null,undefined]){
  assert.deepEqual(plain(adapter().loadHistory(missing)),[]);
  assert.equal(adapter().saveHistory(missing,[entry()]),false);
  assert.equal(adapter().clearStoredHistory(missing),false);
 }
});
