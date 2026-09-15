#!/usr/bin/env node
/* Review the executable capability projection. It never writes a manifest. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {deriveCapabilityManifest} from '../gate/foundation/manifest.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const schemas=JSON.parse(fs.readFileSync(path.join(root,'reliability/schema-snapshot.json'),'utf8'));
const declared=[];
for(const name of fs.readdirSync(path.join(root,'plugins')).sort()){
  const file=path.join(root,'plugins',name,'openclaw.plugin.json');
  if(!fs.existsSync(file))continue;
  const plugin=JSON.parse(fs.readFileSync(file,'utf8'));
  declared.push(...(plugin.contracts?.tools??[]));
}
for(const file of ['reliability/openclaw.plugin.json']){
  const plugin=JSON.parse(fs.readFileSync(path.join(root,file),'utf8'));
  declared.push(...(plugin.contracts?.tools??[]));
}
const manifest=deriveCapabilityManifest({schemas,declaredTools:declared,runtimeConfig:{tools:{alsoAllow:[]}}});
const output={schema:manifest.schema,digest:manifest.digest,capabilities:manifest.capabilities.map(x=>({name:x.name,digest:x.digest,runtime:x.runtime,policy:x.policy})),mismatches:manifest.mismatches};
if(process.argv.includes('--check')){
  // Mismatches are expected review signals, not an excuse to auto-capture a
  // changed schema. The projection marks them non-exposed/fail-closed.
  if(output.capabilities.some(x=>x.runtime.exposed&&!x.runtime.schemaCaptured))throw Error('exposed_capability_without_schema');
}
process.stdout.write(JSON.stringify(output,null,2)+'\n');
