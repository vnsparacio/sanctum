import {describe,expect,it} from 'vitest';
import entry from './index.js';
describe('Browser Guard boundaries',()=>{
 let hook:any;
 entry.register!({on:(_name:string,fn:any)=>{hook=fn;}} as any);
 it('permits isolated navigation while rejecting other browser identities',async()=>{
  expect(await hook({toolName:'browser',params:{action:'snapshot',profile:'openclaw'}})).toBeUndefined();
  expect((await hook({toolName:'browser',params:{action:'snapshot',profile:'chrome'}})).block).toBe(true);
 });
 it('blocks evaluate, predicate waits and unknown operations',async()=>{
  for(const params of [{action:'act',request:{kind:'evaluate'}},{action:'act',request:{kind:'wait',fn:'true'}},{action:'unreviewed'}])expect((await hook({toolName:'browser',params})).block).toBe(true);
 });
 it('requires bounded allow-once approval for interactive changes',async()=>{
  for(const params of [{action:'upload'},{action:'act',request:{kind:'click'}},{action:'act',request:{kind:'type'}}]){
   const x=await hook({toolName:'browser',params});expect(x.requireApproval.allowedDecisions).toEqual(['allow-once','deny']);expect(x.requireApproval.timeoutMs).toBe(120000);
  }
 });
});
