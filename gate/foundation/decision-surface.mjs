/* One ordered production surface. Capability order comes from the manifest. */
import {deepFreeze,digest} from './contracts.mjs';
import {WORK_EDIT_LIMITS,workIntentRequest,workIntentSchema} from './work-intent.mjs';
export function selectCapabilities(manifest,{names=[],limit=4}={}){
 const allowed=names.length?new Set(names):null;
 return manifest.capabilities.filter(x=>x.runtime.exposed&&(!allowed||allowed.has(x.name))).filter(x=>x.policy.supported&&!['web_search','web_fetch'].includes(x.name)).slice(0,limit);
}
export function decisionSurface({manifest,names=[],limit=4,testOnly=false,terminalKinds,reviewer=false,editOperations}){
 const selected=reviewer?[]:selectCapabilities(manifest,{names,limit});
 const specs=testOnly?selected.filter(x=>x.name==='worktree_command'):selected;
 const options={testOnly,terminalKinds,editOperations,decisionNotes:!reviewer},authoritativeSchema=workIntentSchema(specs,options),request=workIntentRequest(specs,options);
 const capabilities=specs.map(x=>x.name);
 const escalation=authoritativeSchema.oneOf.find(branch=>branch.properties.kind.const==='ESCALATION');
 // The decoder omits this constraint; communicate the retained host contract.
 const resultRequirements=escalation?{ESCALATION:{reason:{
   pattern:escalation.properties.reason.pattern,
   description:'A 1–80-character code: first character ASCII A–Z; remaining characters ASCII A–Z, digits 0–9, underscore, colon, or hyphen. No spaces, line terminators, or extra prose.',
 }}}:{};
 if(specs.some(x=>x.name==='worktree_edit'))resultRequirements.worktree_edit={...WORK_EDIT_LIMITS,unit:'UTF-16 code units',strategy:'One short unique replacement per call. Build larger files incrementally: create a small scaffold, read it, then insert a chunk with an exact unique anchor retained for the next edit. Read again after each edit. Never emit a whole-file rewrite that exceeds these limits.'};
 return deepFreeze({specs,capabilities,terminalKinds:[...terminalKinds],authoritativeSchema,request,resultRequirements,identity:digest({capabilities,terminalKinds,schemaDigest:request.schemaDigest,semanticSchemaDigest:request.semanticSchemaDigest})});
}
