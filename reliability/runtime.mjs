import Ajv from 'ajv';
import Ajv2020 from 'ajv/dist/2020.js';
import {repair,consequential} from './registry.mjs';
const options={strict:false,strictNumbers:true,allErrors:false,coerceTypes:false,useDefaults:false,removeAdditional:false,validateFormats:false,ownProperties:true};
const ajv=new Ajv(options),ajv2020=new Ajv2020(options);
export const failure=(code,message='Arguments could not be validated; retain all constraints and ask for clarification.')=>({ok:false,error:{code,message}});
export function compile(schemas){return new Map(schemas.map(s=>[s.name,{schema:s.parameters,validate:(s.parameters.$schema?.includes('2020-12')?ajv2020:ajv).compile(s.parameters)}]));}
export function prepare(name,input,validators){
 const entry=validators.get(name);
 if(!entry)return {ok:false,code:'UNKNOWN_SCHEMA',attempts:0,rules:[]};
 if(!input||typeof input!=='object'||Array.isArray(input)||JSON.stringify(input).length>65536)return {ok:false,code:'INVALID_ARGUMENT',attempts:0,rules:[]};
 const firstValid=entry.validate(input);
 // Approved semantic aliases also normalize valid strings, without changing scope.
 const candidate=repair(name,input,entry.schema);
 if(candidate.conflict)return {ok:false,code:'AMBIGUOUS_ARGUMENT',attempts:1,rules:[],firstValid};
 const changed=candidate.applied.length>0;
 if(firstValid&&!changed)return {ok:true,params:input,attempts:0,rules:[],firstValid};
 if(consequential.has(name))return {ok:false,code:'CONSEQUENTIAL_REPAIR_BLOCKED',attempts:0,rules:[],firstValid};
 if(!changed||!entry.validate(candidate.params))return {ok:false,code:'INVALID_ARGUMENT',attempts:1,rules:candidate.applied,firstValid};
 return {ok:true,params:candidate.params,attempts:1,rules:candidate.applied,firstValid};
}
// One repair before any execution; a backend action is never replayed.
export async function executeBounded(tool,args,validators){
 const p=prepare(tool.name,args,validators);
 if(!p.ok)return {result:failure(p.code),preparation:p,executions:0};
 try{return {result:await tool.execute(p.params),preparation:p,executions:1};}
 catch{return {result:failure('BACKEND_FAILURE','Tool failed; no automatic execution retry.'),preparation:p,executions:1};}
}
