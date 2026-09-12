// Narrow exact-answer checks. No prose fact checker or model confidence input.
const NUMBER='[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?';
function decimal(text){
 if(typeof text!=='string'||text.length>2048||!new RegExp(`^${NUMBER}$`).test(text))return;
 let [mantissa,exponent='0']=text.toLowerCase().split('e');
 if(Math.abs(Number(exponent))>10000)return;
 const negative=mantissa.startsWith('-');mantissa=mantissa.replace(/^[+-]/,'');
 const [whole,fraction='']=mantissa.split('.');
 let digits=(whole+fraction).replace(/^0+/,'');let power=Number(exponent)-fraction.length;
 if(!digits)return '0';
 while(digits.endsWith('0')){digits=digits.slice(0,-1);power++;}
 return `${negative?'-':''}${digits}e${power}`;
}
const units={kilometers:'km',kilometres:'km',kilometer:'km',kilometre:'km',miles:'mi',mile:'mi',celsius:'C',fahrenheit:'F',kelvin:'K',gigabytes:'GB',gibibytes:'GiB',days:'days',day:'days'};
export function exactFact(tool,args,result){
 if(result?.ok!==true||result.truncated||result.untrusted)return;
 const d=result.data;
 if(!d||typeof d!=='object')return;
 if(tool==='calc'&&decimal(d.value)!==undefined)return {tool,kind:'number',value:d.value};
 if(tool==='unit_convert'&&decimal(d.value)!==undefined)return {tool,kind:'number',value:d.value,unit:args.to_unit};
 if(tool==='date_math'){
  if(args.operation==='between'&&Number.isSafeInteger(d.days))return {tool,kind:'number',value:String(d.days),unit:'days'};
  if(args.operation==='weekday'&&typeof d.weekday==='string')return {tool,kind:'weekday',value:d.weekday};
  if(['add','resolve'].includes(args.operation)&&/^\d{4}-\d{2}-\d{2}$/.test(d.date??''))return {tool,kind:'date',value:d.date};
 }
}
export function verifyExactAnswer(fact,answer){
 if(!fact||typeof answer!=='string'||answer.length>4096)return {status:'not_applicable'};
 let text=answer.trim().replace(/^\*\*([^*]+)\*\*$/,'$1').replace(/^`([^`]+)`$/,'$1');
 text=text.replace(/^(?:the )?(?:exact )?(?:answer|result|date|weekday)(?: is|:)\s*/i,'').replace(/[.!]$/,'').trim();
 let match,agrees;
 if(fact.kind==='number'){
  match=new RegExp(`^(${NUMBER})(?:\\s+([A-Za-z°/]+))?$`).exec(text);
  if(!match)return {status:'not_applicable'};
  // Unrecognized units are not interpreted or guessed.
  const label=match[2],unit=label&&(units[label]??label);
  if(label&&!fact.unit)return {status:'not_applicable'};
  if(label&&unit!==fact.unit)return {status:'not_applicable'};
  const value=decimal(match[1]);if(value===undefined)return {status:'not_applicable'};
  agrees=value===decimal(fact.value);
 }else if(fact.kind==='date'){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(text))return {status:'not_applicable'};
  agrees=text===fact.value;
 }else if(fact.kind==='weekday'){
  if(!/^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$/i.test(text))return {status:'not_applicable'};
  agrees=text.toLowerCase()===fact.value.toLowerCase();
 }else return {status:'not_applicable'};
 return {status:agrees?'verified':'contradiction',tool:fact.tool};
}
export const exactFallback=fact=>`The exact local result is ${fact.value}${fact.unit?' '+fact.unit:''}. The model's conflicting answer was not verified; stronger-model escalation is unavailable under the current policy.`;

export function createVerification({escalate,record,now=Date.now}){
 const runs=new Map(),proofs=new Map();
 function prune(){for(const [key,value]of runs)if(now()-value.at>900000)runs.delete(key);while(runs.size>256)runs.delete(runs.keys().next().value);while(proofs.size>256)proofs.delete(proofs.keys().next().value);}
 function state(id){prune();if(!id)return;let s=runs.get(id);if(!s){s={at:now(),facts:[],tools:new Set()};runs.set(id,s);}return s;}
 return {
  proposed(run,tool){const s=state(run);if(s)s.tools.add(tool);return s?.failed===true;},
  proof(id,tool,args,result){prune();if(id){const fact=exactFact(tool,args,result);if(fact)proofs.set(id,{fact,serialized:JSON.stringify(result),at:now()});}},
  result(run,id,tool,result){const proof=proofs.get(id);proofs.delete(id);const s=state(run);if(s)s.tools.add(tool);if(s&&proof&&now()-proof.at<900000&&proof.fact.tool===tool&&proof.serialized===JSON.stringify(result)){if(s.facts.length<2)s.facts.push(proof.fact);record({tool,outcome:'VERIFICATION_READY'});}else if(['calc','unit_convert','date_math'].includes(tool))record({tool,outcome:'VERIFICATION_SKIPPED'});},
  async finalize(event,ctx){
   record({outcome:'VERIFICATION_CHECK'});
   const id=event.runId??ctx?.runId,s=runs.get(id);prune();
   if(!s||now()-s.at>=900000||s.facts.length!==1||s.tools.size!==1)return;
   const fact=s.facts[0],check=verifyExactAnswer(fact,event.lastAssistantMessage);
   if(check.status==='verified'){record({tool:fact.tool,status:'ok',outcome:'VERIFIED'});return;}
   if(check.status!=='contradiction'||s.failed)return;
   // Set synchronously before awaiting policy so no simultaneous call can replay.
   s.failed=true;s.fallback=exactFallback(fact);
   await escalate(fact.tool,'VERIFICATION_FAILED');
   return {action:'revise',reason:'VERIFICATION_FAILED',retry:{instruction:`Do not call any tools or perform further reasoning. Reply exactly: ${s.fallback}`,idempotencyKey:'vinceai-exact-verification',maxAttempts:1}};
  },
  delivery(event){const s=runs.get(event.runId);prune();if(s?.failed&&now()-s.at<900000&&event.kind==='final')return {payload:{...event.payload,text:s.fallback}};},
  end(id){const s=runs.get(id);if(s&&!s.failed)runs.delete(id);prune();}
 };
}
