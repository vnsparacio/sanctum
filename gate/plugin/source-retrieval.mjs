/* One bounded coordinator over the existing pinned web capabilities. */
import {createEvidencePack} from '../foundation/evidence.mjs';
import {CONTRACT_VERSION,digest,egressMatches,validateEgressDecision,validateToolProposal} from '../foundation/contracts.mjs';

const MAX_CANDIDATES=6, MAX_FETCHES=3, MAX_CHARS=12000, PER_SOURCE=4000;
const blocked=/(?:^(?:localhost|0\.0\.0\.0|127\.|10\.|192\.168\.|169\.254\.|198\.1[89]\.|172\.(?:1[6-9]|2\d|3[01])\.|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.|::1$|f[cd][0-9a-f:]*$|fe[89ab][0-9a-f:]*$)|\.(?:local|internal)$)/i;
const safeUrl=value=>{try{const u=new URL(value);u.hash='';const host=u.hostname.replace(/^\[|\]$/g,'');return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&!blocked.test(host)&&u.href.length<=2048?u:null;}catch{return null;}};
const sourceClass=url=>/\b(?:gov|edu)\b/i.test(url.hostname)?'AUTHORITATIVE_INSTITUTION':/(?:docs|developer|support|official)/i.test(url.hostname)?'OFFICIAL_PRIMARY':/(?:reddit|forum|community|stack)/i.test(url.hostname)?'COMMUNITY':'REPUTABLE_SECONDARY';
const common=new Set(['about','and','are','for','from','has','how','the','this','use','what','when','where','with','zip']);
const tokens=value=>(String(value).toLowerCase().match(/[a-z][a-z0-9]{2,}|\b\d{5}\b/g)??[]).filter(x=>!common.has(x));
const weatherZip=query=>/\b(?:weather|forecast|temperature|rain|conditions)\b/i.test(query)?query.match(/\b\d{5}\b/)?.[0]??null:null;
// Generic uses of "forecast" (including a forecaster's marketing copy) do
// not establish a usable forecast. Require an observed numeric condition.
const weatherFact=/\b(?:high|low|temperature)\s+(?:near|around|of|:)?\s*\d{1,3}(?:\s?°?\s?[FC])?\b|\bwind\b[^\n.]{0,40}\b\d{1,3}\s?(?:mph|kph|km\/h)\b|\b\d{1,3}\s?%\s+(?:chance\s+of\s+)?(?:rain|precipitation|showers)\b|\b\d{1,3}\s?°\s?[FC]?\b/i;
const score=(row,query)=>{
 const terms=tokens(query), page=tokens(`${row.title??''} ${row.description??''} ${row.url??''}`), present=new Set(page), pairs=new Set(page.slice(1).map((x,i)=>`${page[i]} ${x}`));
 const matches=terms.reduce((n,t)=>n+(present.has(t)?(t===weatherZip(query)?40:4):0),0);
 const phrases=terms.slice(1).reduce((n,t,i)=>n+(pairs.has(`${terms[i]} ${t}`)?8:0),0);
 const weight={AUTHORITATIVE_INSTITUTION:12,OFFICIAL_PRIMARY:10,REPUTABLE_SECONDARY:4,COMMUNITY:0}[sourceClass(new URL(row.url))];
 const weatherPrimary=weatherZip(query)&&sourceClass(new URL(row.url))==='AUTHORITATIVE_INSTITUTION'?100:0;
 return matches+phrases+weight+weatherPrimary+(row.url.startsWith('https://')?1:0);
};
const nowIso=()=>new Date().toISOString();

export function rankCandidates(results,query){
 const seen=new Set(), valid=[],zip=weatherZip(query);
 for(const row of Array.isArray(results)?results:[]){const u=safeUrl(row?.url);if(!u||seen.has(u.href))continue;seen.add(u.href);const snippet=typeof row.snippet==='string'?row.snippet:row.description;
   // Search rank alone cannot establish a location. For an explicit weather
   // ZIP, discard candidates that never identify that ZIP at all.
   if(zip&&!`${u.href} ${row.title??''}`.includes(zip))continue;
   valid.push({url:u.href,title:typeof row.title==='string'?row.title.slice(0,512):'',description:typeof snippet==='string'?snippet.slice(0,4000):'',published:typeof row.published==='string'?row.published.slice(0,64):null,sourceClass:sourceClass(u),score:score({...row,description:snippet,url:u.href},query)});}
 return valid.sort((a,b)=>b.score-a.score||a.url.localeCompare(b.url)).slice(0,MAX_CANDIDATES);
}

export function queryEgressDecision(request,capability='web_search',capabilityDigest='0'.repeat(64),now=Date.now()/1000){
 const mode=request.queryMode, args=mode==='PUBLIC_GENERALIZED'?{query:request.query,count:MAX_CANDIDATES}:{query:''};
 const outcome=mode==='PUBLIC_GENERALIZED'?'ALLOW':mode==='EXACT_APPROVAL_REQUIRED'?'ASK':'DENY';
 const decision={schema:CONTRACT_VERSION,outcome,capability,capabilityDigest,requestDigest:request.requestDigest,packetDigest:digest(args),scope:request.scope,revision:request.revision,dataClasses:[mode==='PUBLIC_GENERALIZED'?'PUBLIC':'PERSONAL'],destination:{kind:'EXTERNAL_SERVICE',service:'parallel',model:'web_search'},purpose:'PUBLIC_SEARCH',expires:outcome==='ASK'?now+300:null,oneUse:outcome==='ASK',approvalState:outcome==='ASK'?'PENDING':'NONE',reasonCodes:[outcome==='ALLOW'?'MAC_SOURCE_POLICY':outcome==='ASK'?'EXACT_OWNER_DISCLOSURE_REQUIRED':'PRIVATE_QUERY_DENIED']};
 const checked=validateEgressDecision(decision,now);if(!checked.ok)throw Error(checked.code);return checked.value;
}

export function createSourceRetrieval({manifest,invoke,now=nowIso}){
 if(typeof invoke!=='function')throw Error('source_retrieval_invoke');
 function proposal(name,args,request){const spec=manifest?.byName?.[name];const p={schema:CONTRACT_VERSION,proposalId:`source-${digest(args).slice(0,16)}`,requestId:request.requestDigest,revision:request.revision,reasoner:'MAC_SOURCE_COORDINATOR',capability:name,capabilityDigest:spec?.digest??'0'.repeat(64),arguments:args};const checked=validateToolProposal(p,manifest);if(!checked.ok)throw Error(checked.code);return checked.value;}
 function decision(name,args,request,destination,purpose){const spec=manifest?.byName?.[name];return {schema:CONTRACT_VERSION,outcome:'ALLOW',capability:name,capabilityDigest:spec?.digest??'0'.repeat(64),requestDigest:request.requestDigest,packetDigest:digest(args),scope:request.scope,revision:request.revision,dataClasses:['PUBLIC'],destination,purpose,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['MAC_SOURCE_POLICY']};}
 function allowed(value,claim){const checked=egressMatches(value,claim);if(!checked.ok)throw Error(checked.code);}
 async function call(name,args,request,destination,purpose){const p=proposal(name,args,request), claim={requestDigest:request.requestDigest,packetDigest:digest(args),scope:request.scope,revision:request.revision,capability:name,capabilityDigest:p.capabilityDigest,dataClasses:['PUBLIC'],purpose,destination};allowed(decision(name,args,request,destination,purpose),claim);return invoke(name,args,p);}
 return {async retrieve(request){
   const searchSpec=manifest?.byName?.web_search, queryDecision=queryEgressDecision(request,'web_search',searchSpec?.digest??'0'.repeat(64));
   if(queryDecision.outcome!=='ALLOW'||request.queryMode!=='PUBLIC_GENERALIZED'||typeof request.query!=='string')return createEvidencePack({...request,items:[],failureCodes:[queryDecision.outcome==='ASK'?'QUERY_APPROVAL_REQUIRED':'QUERY_DENIED'],adequacy:request.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL',createdAt:now(),budget:{candidates:0,fetched:0,chars:0}});
   let found;try{found=await call('web_search',{query:request.query,count:MAX_CANDIDATES},request,{kind:'EXTERNAL_SERVICE',service:'parallel',model:'web_search'},'PUBLIC_SEARCH');}catch{return createEvidencePack({...request,items:[],failureCodes:['SEARCH_FAILED'],adequacy:request.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL',createdAt:now(),budget:{candidates:0,fetched:0,chars:0}});}
   const candidates=rankCandidates(found?.data?.results??found?.results,request.query), items=[], failures=[];let chars=0,fetched=0,weatherFacts=0;
   for(let n=0;n<candidates.length;n++){const c=candidates[n];const base={sourceId:`s${n+1}`,url:c.url,finalUrl:null,title:c.title,sourceClass:c.sourceClass,publishedAt:c.published,retrievedAt:now(),fetchStatus:'CANDIDATE',fragments:[{kind:'LOCATOR',text:c.url},{kind:'METADATA',text:c.title},{kind:'SNIPPET',text:c.description}],truncated:false,untrusted:true,provenance:{capability:'web_search'}};if(fetched>=MAX_FETCHES||chars>=MAX_CHARS){items.push(base);continue;}
     try{const value=await call('web_fetch',{url:c.url,extractMode:'text',maxChars:PER_SOURCE},request,{kind:'EXTERNAL_SERVICE',service:'openclaw-core',model:'web_fetch'},'PUBLIC_FETCH');const raw=value?.data??value;const final=safeUrl(raw?.finalUrl??raw?.url??c.url);if(!final)throw Error('redirect');const content=typeof raw?.text==='string'?raw.text.slice(0,Math.min(PER_SOURCE,MAX_CHARS-chars)):'';if(!content)throw Error('extract');const truncated=value?.truncated===true||raw?.truncated===true||raw.text.length>content.length;chars+=content.length;fetched++;if(weatherZip(request.query)&&!weatherFact.test(content)){failures.push('WEATHER_FACT_UNAVAILABLE');items.push({...base,finalUrl:final.href,fetchStatus:'REJECTED_IRRELEVANT',truncated,provenance:{capability:'web_fetch'}});continue;}weatherFacts++;items.push({...base,finalUrl:final.href,fetchStatus:truncated?'TRUNCATED':'FETCHED',truncated,fragments:[...base.fragments,{kind:'FETCHED_CONTENT',text:content}],provenance:{capability:'web_fetch'}});}catch(error){const status=error?.message==='redirect'?'REDIRECT_FAILED':error?.message==='extract'?'EXTRACTION_FAILED':'FETCH_FAILED';failures.push(status);items.push({...base,fetchStatus:status});}
   }
   if(weatherZip(request.query)&&fetched&&!weatherFacts)failures.push('WEATHER_FACT_UNAVAILABLE');
   if(weatherZip(request.query)&&!candidates.length)failures.push('WEATHER_LOCATION_UNVERIFIED');
   const adequate=weatherFacts?'ADEQUATE':request.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL';
   return createEvidencePack({...request,items,failureCodes:[...new Set(failures)],adequacy:adequate,createdAt:now(),budget:{candidates:candidates.length,fetched,chars}});
 }};
}
