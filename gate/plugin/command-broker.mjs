/*
 * Model-independent adapter to the signed Mac worker's pinned OCI runner.
 * It accepts no executable, argv, environment, path, mount, or network flag.
 */
const CATALOG=Object.freeze(['status','diff','test','lint','build']);

export function createCommandBroker({invoke,taskId,profile}={}){
 return Object.freeze({async execute({workspace,operation,allowNetwork=false,signal}={}){
   if(typeof invoke!=='function'||!/^[a-f0-9]{32}$/.test(taskId??'')||typeof profile!=='string')return {ok:false,code:'ENVIRONMENT_FAILURE',executionState:'NOT_STARTED'};
   if(allowNetwork||workspace!==taskId||!CATALOG.includes(operation))return {ok:false,code:'WORKSPACE_CONTAINMENT',executionState:'NOT_STARTED'};
   try{
     const response=await invoke({task_id:taskId,operation,profile},signal);
     if(response?.status!=='OK'||!response.result||typeof response.result!=='object')return {ok:false,code:'ENVIRONMENT_FAILURE',executionState:'NOT_STARTED'};
     return response.result;
   }catch{return {ok:false,code:'ENVIRONMENT_FAILURE',executionState:'NOT_STARTED'};}
 }});
}

export const commandCatalog=CATALOG;
