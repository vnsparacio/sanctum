#!/usr/bin/env node
/* Offline production-schema preflight for the pinned PRIVATE_LEAD decoder. */
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {deriveCapabilityManifest} from './foundation/manifest.mjs';
import {decisionSurface} from './foundation/decision-surface.mjs';
import {projectVllmGenerationSchema,validateVllmGenerationSchema} from './foundation/vllm-structured-output.mjs';
import {workModeTools} from './plugin/workspace-tools.mjs';

const names=Object.freeze(workModeTools.map(tool=>tool.name));
function manifest(){
 return deriveCapabilityManifest({
   schemas:workModeTools.map(tool=>({name:tool.name,description:tool.description,parameters:tool.parameters})),
   declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}},
 });
}
function surface(current,label,selected,options={}){
 const built=decisionSurface({manifest:current,names:selected,limit:label==='allEligible'?5:4,reviewer:label==='reviewer',...options}),request=built.request,projection=projectVllmGenerationSchema(built.authoritativeSchema),checked=validateVllmGenerationSchema(request.schema);
 if(!checked.ok)throw Error('structured_schema_preflight');
 return {label,capabilities:built.capabilities,version:request.version,dialect:request.dialect,schemaDigest:request.schemaDigest,semanticSchemaDigest:request.semanticSchemaDigest,branches:request.schema.oneOf.length,projectionOmissions:projection.omitted,request};
}
export function preflightCurrentWorkIntentSchemas(){
 const current=manifest();
 const schemas={
   allEligible:surface(current,'allEligible',names,{terminalKinds:['FINAL','ESCALATION']}),
   ordinaryIneligible:surface(current,'ordinaryIneligible',['worktree_list','worktree_read','worktree_edit','worktree_command'],{terminalKinds:['ESCALATION']}),
   ordinaryEligible:surface(current,'ordinaryEligible',['worktree_list','worktree_read','worktree_edit','worktree_command'],{terminalKinds:['FINAL','ESCALATION']}),
   researchIneligible:surface(current,'researchIneligible',['worktree_list','worktree_read','source_first_research','worktree_command'],{terminalKinds:['ESCALATION']}),
   researchEligible:surface(current,'researchEligible',['worktree_list','worktree_read','source_first_research','worktree_command'],{terminalKinds:['FINAL','ESCALATION']}),
   testOnlyIneligible:surface(current,'testOnlyIneligible',['worktree_command'],{testOnly:true,terminalKinds:['ESCALATION']}),
   reviewer:surface(current,'reviewer',[],{terminalKinds:['FINAL']}),
 };
 return {ok:true,schema:'sanctum-work-intent-preflight/v1',manifestDigest:current.digest,schemas};
}
function summary(value){
 return {...value,schemas:Object.fromEntries(Object.entries(value.schemas).map(([key,row])=>[key,Object.fromEntries(Object.entries(row).filter(([name])=>name!=='request'))]))};
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===resolve(process.argv[1])){
 try{const result=preflightCurrentWorkIntentSchemas();console.log(JSON.stringify(process.argv.includes('--json')?result:summary(result)));}
 catch{console.error('REFUSED: structured_schema_preflight');process.exitCode=1;}
}
