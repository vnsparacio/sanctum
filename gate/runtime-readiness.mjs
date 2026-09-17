/* Non-inference preparation using the exact production schema/request builders. */
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {preflightCurrentWorkIntentSchemas} from './preflight-work-intent.mjs';
import {deriveCapabilityManifest} from './foundation/manifest.mjs';
import {decisionSurface} from './foundation/decision-surface.mjs';
import {workModeTools} from './plugin/workspace-tools.mjs';
import {buildWorkRequest,argumentsMatchSchema,MUTABLE_WORKTREE_COMPLETION_POLICY} from './plugin/work-mode.mjs';
import {buildReviewerRequest} from './plugin/work-command.mjs';
import {profileSystem} from './plugin/private-lead.mjs';
import {digest} from './foundation/contracts.mjs';

export const SURFACES=Object.freeze(['ordinaryIneligible','ordinaryEligible','researchIneligible','researchEligible','testOnlyIneligible','reviewer']);
const examples={
 worktree_list:{path:'.',max_entries:10},worktree_read:{path:'index.js',max_chars:100},
 worktree_patch:{patch:'--- a/index.js\n+++ b/index.js\n@@ -1 +1 @@\n-old\n+new\n'},
 worktree_command:{operation:'test'},source_first_research:{source_need:'WEB_REQUIRED'},
};
function representative(branch){
 const kind=branch.properties.kind.const;
 if(kind==='FINAL')return {kind,text:'Synthetic result'};
 if(kind==='ESCALATION')return {kind,reason:'SYNTHETIC_UNAVAILABLE'};
 const capability=branch.properties.capability.const;
 const args=structuredClone(examples[capability]);
 // Fill only the real semantic arguments. Every example is checked below.
 return {kind,capability,arguments:args};
}
export function hostSemanticReadiness(schema,representatives){
 const accepts=value=>schema.oneOf.filter(branch=>argumentsMatchSchema(value,branch)).length===1;
 if(representatives.length!==schema.oneOf.length||representatives.some((value,i)=>!argumentsMatchSchema(value,schema.oneOf[i])||!accepts(value)))throw Error('readiness_semantic_invalid');
 const controls=[];
 function check(branch,path,keyword,value){
  const candidate=structuredClone(representatives[branch]);
  let target=candidate;for(const key of path.slice(0,-1))target=target[key];
  target[path.at(-1)]=value;
  if(accepts(candidate))throw Error('readiness_semantic_negative_accepted');
  controls.push({branch,path:path.join('.'),keyword,rejected:true});
 }
 schema.oneOf.forEach((branch,index)=>{
  check(index,['unexpected_field'],'additionalProperties',true);
  function visit(node,path){
   if(node.type==='object')for(const [key,child] of Object.entries(node.properties??{})){
    let value=representatives[index];for(const part of [...path,key])value=value?.[part];
    if(value!==undefined)visit(child,[...path,key]);
   }
   if(node.type==='string'){
    check(index,path,'type',42);
    if(node.minLength>0)check(index,path,'minLength','');
    if(Number.isInteger(node.maxLength))check(index,path,'maxLength','x'.repeat(node.maxLength+1));
    if(node.pattern)for(const value of ['../synthetic','/synthetic','synthetic\u0000']){
     if(!new RegExp(node.pattern,'u').test(value))check(index,path,'pattern',value);
    }
   }
  }
  visit(branch,[]);
 });
 return {schema:'sanctum-host-semantic-readiness/v1',status:'PASS',semanticSchemaDigest:digest(schema),representativesDigest:digest(representatives),positiveBranches:representatives.length,negativeControls:controls};
}
export function readinessArtifact(){
 const preflight=preflightCurrentWorkIntentSchemas();
 const names=workModeTools.map(x=>x.name),manifest=deriveCapabilityManifest({schemas:workModeTools.map(x=>({name:x.name,description:x.description,parameters:x.parameters})),declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
 const surfaces=Object.fromEntries(SURFACES.map(name=>{
  const row=preflight.schemas[name],objects=row.request.schema.oneOf.map(branch=>name==='reviewer'?{kind:'FINAL',text:JSON.stringify({verdict:'ACCEPT',findings:[]})}:representative(branch));
  if(objects.some((value,i)=>!argumentsMatchSchema(value,row.request.schema.oneOf[i])))throw Error('readiness_representative_invalid');
  const semantic=decisionSurface({manifest,names:row.capabilities,reviewer:name==='reviewer',testOnly:name==='testOnlyIneligible',terminalKinds:row.request.schema.oneOf.map(b=>b.properties.kind.const).filter(k=>k!=='TOOL_PROPOSAL')}).authoritativeSchema;
  const hostSemanticValidation=hostSemanticReadiness(semantic,objects);
  return [name,{...row,semanticSchema:semantic,representatives:objects,hostSemanticValidation}];
 }));

 const profile=JSON.parse(readFileSync(new URL('./runtime/private-lead-interface-profile.json',import.meta.url)));
 const messages={};
 function request(label,{observations=[],correction=null,testOnly=false}={}){
  const selected=testOnly?['worktree_command']:['worktree_list','worktree_read','worktree_patch','worktree_command'];
  const artifact=decisionSurface({manifest,names:selected,testOnly,terminalKinds:['ESCALATION']});
  if(correction)correction={...correction,resultRequirements:artifact.resultRequirements,diagnostic:null,schemaVersion:artifact.request.version,schemaDigest:artifact.request.schemaDigest,allowedCapabilities:artifact.capabilities,allowedTerminalKinds:['ESCALATION']};
  const state={task:'Synthetic offline inspection task.',phase:'PLAN',iteration:testOnly||correction?1:observations.length,tests:{passed:null,required:testOnly},observations,correction,workspaceGeneration:testOnly?1:0};
  const value=buildWorkRequest({requestId:'synthetic',scope:'a'.repeat(32),state,decisionState:testOnly?'TEST_REQUIRED':'WORK_REQUIRED',decisionArtifact:artifact,phaseVisible:artifact.specs,eligibility:{eligible:false,reason:testOnly?'POST_PATCH_TEST_REQUIRED':'NO_COMPLETABLE_DIFF'},completionPolicy:MUTABLE_WORKTREE_COMPLETION_POLICY,captured:{digest:'b'.repeat(64)},manifest,terminalKinds:['ESCALATION']});
  messages[label]={system:profileSystem(profile),request:value};return value;
 }
 request('ordinaryInitial');
 const observations=Array.from({length:6},()=>({provenance:'MAC_CAPABILITY',data:'Synthetic observation. '.repeat(180)}));
 request('accumulatedObservations',{observations});
 request('activeCorrection',{observations,correction:{code:'REASONER_RESULT_SCHEMA',attempt:1,correctionsRemaining:1}});
 let low=0,high=64000;
 while(low<high){const n=Math.ceil((low+high)/2);try{request('nearCharacterLimit',{observations:[{provenance:'MAC_CAPABILITY',data:'x'.repeat(n)}]});low=n;}catch(e){if(e.message!=='model_context_limit')throw e;high=n-1;}}
 request('nearCharacterLimit',{observations:[{provenance:'MAC_CAPABILITY',data:'x'.repeat(low)}]});
 request('postPatchTestOnly',{testOnly:true});
 messages.reviewer={system:profileSystem(profile),request:buildReviewerRequest({task:{id:'a'.repeat(32)},requestId:'synthetic-review',reviewGoal:'Synthetic offline review.',state:{iteration:0,tests:{passed:true,required:false},observations:[]},claim:'Synthetic completion.',reviewEvidence:{checks:[],diffStable:true,diffDigest:'b'.repeat(64),workspaceDiff:'Synthetic diff.'},manifest})};
 return {schema:'sanctum-runtime-readiness/v1',surfaces,messages,profile:{model:profile.model,revision:profile.revision,modelWindow:profile.context.model_window_tokens,reservedOutput:profile.context.reserved_output_tokens},hostValidation:'SOURCE_DIALECT_AND_HOST_ONLY',exactCompiler:'NOT_RUN',liveEndpoint:'NOT_RUN',tokenMeasurement:'NOT_RUN'};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(readinessArtifact()));
