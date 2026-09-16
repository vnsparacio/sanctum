#!/usr/bin/env node
/* Offline production-schema preflight for the pinned PRIVATE_LEAD decoder. */
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {deriveCapabilityManifest} from './foundation/manifest.mjs';
import {workIntentRequest,workIntentSchema} from './foundation/work-intent.mjs';
import {projectVllmGenerationSchema,validateVllmGenerationSchema} from './foundation/vllm-structured-output.mjs';
import {workModeTools} from './plugin/workspace-tools.mjs';

const names=Object.freeze(workModeTools.map(tool=>tool.name));
function manifest(){
 return deriveCapabilityManifest({
   schemas:workModeTools.map(tool=>({name:tool.name,description:tool.description,parameters:tool.parameters})),
   declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}},
 });
}
function surface(byName,label,selected,options={}){
 const specs=selected.map(name=>byName[name]),request=workIntentRequest(specs,options),projection=projectVllmGenerationSchema(workIntentSchema(specs,options)),checked=validateVllmGenerationSchema(request.schema);
 if(!checked.ok)throw Error('structured_schema_preflight');
 return {label,capabilities:selected,version:request.version,dialect:request.dialect,schemaDigest:request.schemaDigest,semanticSchemaDigest:request.semanticSchemaDigest,branches:request.schema.oneOf.length,projectionOmissions:projection.omitted,request};
}
export function preflightCurrentWorkIntentSchemas(){
 const current=manifest(),byName=current.byName;
 const schemas={
   all:surface(byName,'all',names),
   ordinary:surface(byName,'ordinary',['worktree_list','worktree_read','worktree_patch','worktree_command']),
   research:surface(byName,'research',['worktree_list','worktree_read','source_first_research','worktree_command']),
   testOnly:surface(byName,'testOnly',['worktree_command'],{testOnly:true}),
   reviewer:surface(byName,'reviewer',[]),
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
