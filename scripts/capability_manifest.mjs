#!/usr/bin/env node
/* Derive and verify the source/runtime capability projection without writing it. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {deriveCapabilityManifest,PINNED_ADAPTER_TOOLS} from '../gate/foundation/manifest.mjs';
import {rules} from '../reliability/registry.mjs';
import {utilityTools} from '../reliability/schemas.mjs';
import {workModeTools} from '../gate/plugin/workspace-tools.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const schemas=JSON.parse(fs.readFileSync(path.join(root,'reliability/schema-snapshot.json'),'utf8'));
const declared=[], registered=[];
const pluginDirs=fs.readdirSync(path.join(root,'plugins')).sort();
for(const name of pluginDirs){
  const directory=path.join(root,'plugins',name), file=path.join(directory,'openclaw.plugin.json');
  if(!fs.existsSync(file))continue;
  const plugin=JSON.parse(fs.readFileSync(file,'utf8')), actual=[];
  const entry=(await import(pathToFileURL(path.join(directory,'dist/index.js')))).default;
  entry.register?.({registerTool:tool=>actual.push(tool),on:()=>{}});
  const advertised=[...(plugin.contracts?.tools??[])].sort(), observed=actual.map(x=>x.name).sort();
  if(JSON.stringify(advertised)!==JSON.stringify(observed))throw Error(`plugin_tool_declaration_drift:${plugin.id}`);
  declared.push(...advertised);
  registered.push(...actual.map(x=>({name:x.name,description:x.description,parameters:x.parameters,source:`plugin:${plugin.id}`})));
}
const reliability=JSON.parse(fs.readFileSync(path.join(root,'reliability/openclaw.plugin.json'),'utf8'));
const reliabilityTools=[...utilityTools,...workModeTools];
const utilityNames=reliabilityTools.map(x=>x.name).sort();
if(JSON.stringify([...(reliability.contracts?.tools??[])].sort())!==JSON.stringify(utilityNames))throw Error('plugin_tool_declaration_drift:vinceai-reliability');
declared.push(...utilityNames);
registered.push(...reliabilityTools.map(x=>({...x,source:'plugin:vinceai-reliability'})));
const repairRulesByTool={};
for(const rule of rules)for(const tool of rule.tools)(repairRulesByTool[tool]??=[]).push(rule.id);
const manifest=deriveCapabilityManifest({schemas,declaredTools:declared,registeredTools:registered,adaptedTools:PINNED_ADAPTER_TOOLS,runtimeConfig:{tools:{alsoAllow:[]}},repairRulesByTool,allowedRepairRules:rules.map(x=>x.id)});
const output={schema:manifest.schema,digest:manifest.digest,capabilities:manifest.capabilities.map(x=>({name:x.name,digest:x.digest,implementation:x.implementation,runtime:x.runtime,policy:x.policy})),mismatches:manifest.mismatches};
if(process.argv.includes('--check')){
  const allowed=new Set(['calendar_search:REGISTERED_SCHEMA_MISSING','messages_contact_history:REGISTERED_SCHEMA_MISSING','memory_get:SCHEMA_UNREGISTERED','memory_search:SCHEMA_UNREGISTERED','read:SCHEMA_UNREGISTERED','session_status:SCHEMA_UNREGISTERED']);
  const unexpected=output.mismatches.filter(x=>!allowed.has(`${x.name}:${x.kind}`));
  if(unexpected.length||output.mismatches.length!==allowed.size)throw Error('capability_projection_drift:'+JSON.stringify(unexpected));
}
process.stdout.write(JSON.stringify(output,null,2)+'\n');
