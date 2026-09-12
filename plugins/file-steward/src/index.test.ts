import {describe,expect,it} from 'vitest';
import entry, {fileMetadataResult} from './index.js';
describe('File Steward authority',()=>{
 it('labels file timestamps without claiming preview contents from metadata',()=>{
  const raw={ok:true,modified:1785946560,entries:[{name:'reservation-august.pdf',modified:1785946560,file_id:'synthetic'}],preview_available:false,preview_truncated:true};
  const out=fileMetadataResult(raw) as any;
  expect(out.fileModifiedAt).toBe(raw.modified);expect(out).not.toHaveProperty('modified');
  expect(out.entries[0].fileModifiedAt).toBe(raw.modified);expect(out.entries[0]).not.toHaveProperty('modified');
  expect(out.preview_available).toBe(false);expect(out.preview_truncated).toBe(true);expect(out).not.toHaveProperty('preview');
 });
 it('registers six scoped tools and retains approvals on consequential changes',async()=>{
  const tools:any[]=[];const hooks:any[]=[];
  entry.register!({registerTool:(t:any)=>tools.push(t),on:(name:string,fn:any)=>hooks.push(fn)} as any);
  expect(tools.map(t=>t.name)).toEqual(['steward_list','steward_inspect','steward_create_folder','steward_move','steward_rename','steward_undo_last']);
  for(const name of ['steward_move','steward_rename','steward_undo_last'])expect((await hooks[0]({toolName:name})).requireApproval.allowedDecisions).toEqual(['allow-once','deny']);
  for(const t of tools)expect(t.parameters.additionalProperties).toBe(false);
 });
});
