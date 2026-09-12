// Development challenge set: explicit malformed proposals, not measured Qwen emissions.
import fs from 'node:fs';
import {compile,prepare} from './runtime.mjs';
import {utilityTools} from './schemas.mjs';
const schemas=JSON.parse(fs.readFileSync(new URL('./fixtures/schemas-before.json',import.meta.url)));
const validators=compile([...schemas,...utilityTools]);
const cases=[
 ['numeric_limit','messages_search',{query:'from:Alex Example',limit:'10'}],
 ['maximum_limit','messages_search',{query:'from:Alex Example',limit:1000}],
 ['combined_limit','gmail_search',{query:'from:amazon newer_than:30d is:unread',limit:'1000'}],
 ['unit_alias','unit_convert',{value:'1',from:'miles',to:'kilometers'}],
 ['boolean_header','structured_parse',{format:'csv',text:'a\n1',headers:'true'}],
 ['format_alias','structured_parse',{format:'JSON',text:'{}'}],
 ['date_numeric','date_math',{operation:'add',date:'2026-01-01',amount:'90'}]
];
const rows=cases.map(([id,tool,args])=>{const first=validators.get(tool).validate(args);const after=prepare(tool,args,validators);return {id,tool,valid_before:first,valid_after:after.ok,attempts:after.attempts,rules:after.rules};});
fs.writeFileSync(new URL('./evidence/argument-replay.json',import.meta.url),JSON.stringify({dataset:'development challenge set; not acceptance or live Qwen rate',cases:rows,valid_before:rows.filter(r=>r.valid_before).length,valid_after:rows.filter(r=>r.valid_after).length,total:rows.length},null,2));
console.log('Development interface replay:',rows.filter(r=>r.valid_before).length,'→',rows.filter(r=>r.valid_after).length,'of',rows.length);
