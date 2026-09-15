/* One bounded coordinator over the existing pinned web capabilities. */
import {createEvidencePack} from '../foundation/evidence.mjs';
import {CONTRACT_VERSION,digest,egressMatches,validateToolProposal} from '../foundation/contracts.mjs';

const MAX_CANDIDATES=6, MAX_FETCHES=3, MAX_CHARS=12000, PER_SOURCE=4000;
const blocked=/^(localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[?::1)/i;
const safeUrl=value=>{try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&!blocked.test(u.hostname)&&u.href.length<=2048?u:null;}catch{return null;}};
const sourceClass=url=>/\b(?:gov|edu)\b/i.test(url.hostname)?'AUTHORITATIVE_INSTITUTION':/(?:docs|developer|support|official)/i.test(url.hostname)?'OFFICIAL_PRIMARY':/(?:reddit|forum|community|stack)/i.test(url.hostname)?'COMMUNITY':'REPUTABLE_SECONDARY';
const score=(row,query)=>{const text=`${row.title??''} ${row.description??''}`.toLowerCase(), terms=query.toLowerCase().split(/\s+/).filter(Boolean);return terms.reduce((n,t)=>n+(text.includes(t)?4:0),0)+(sourceClass(new URL(row.url))==='OFFICIAL_PRIMARY'?8:0);};
const nowIso=()=>new Date().toISOString();

export function rankCandidates(results,query){
 const seen=new Set(), valid=[];
 for(const row of Array.isArray(results)?results:[]){const u=safeUrl(row?.url);if(!u||seen.has(u.href))continue;seen.add(u.href);valid.push({url:u.href,title:typeof row.title==='string'?row.title.slice(0,512):'',description:typeof row.description==='string'?row.description.slice(0,4000):'',published:typeof row.published==='string'?row.published.slice(0,64):null,sourceClass:sourceClass(u),score:score({...row,url:u.href},query)});}
 return valid.sort((a,b)=>b.score-a.score||a.url.localeCompare(b.url)).slice(0,MAX_CANDIDATES);
}

export function createSourceRetrieval({manifest,invoke,now=nowIso}){
 if(typeof invoke!=='function')throw Error('source_retrieval_invoke');
 function proposal(name,args,request){const spec=manifest?.byName?.[name];const p={schema:CONTRACT_VERSION,proposalId:`source-${digest(args).slice(0,16)}`,requestId:request.requestDigest,revision:request.revision,reasoner:'MAC_SOURCE_COORDINATOR',capability:name,capabilityDigest:spec?.digest??'0'.repeat(64),arguments:args};const checked=validateToolProposal(p,manifest);if(!checked.ok)throw Error(checked.code);return checked.value;}
 function decision(name,args,request,destination,purpose){const spec=manifest?.byName?.[name];return {schema:CONTRACT_VERSION,outcome:'ALLOW',capability:name,capabilityDigest:spec?.digest??'0'.repeat(64),requestDigest:request.requestDigest,packetDigest:digest(args),scope:request.scope,revision:request.revision,dataClasses:['PUBLIC'],destination,purpose,expires:null,oneUse:false,approvalState:'NONE',reasonCodes:['MAC_SOURCE_POLICY']};}
 function allowed(value,claim){const checked=egressMatches(value,claim);if(!checked.ok)throw Error(checked.code);}
 async function call(name,args,request,destination,purpose){const p=proposal(name,args,request), claim={requestDigest:request.requestDigest,packetDigest:digest(args),scope:request.scope,revision:request.revision,capability:name,capabilityDigest:p.capabilityDigest,dataClasses:['PUBLIC'],purpose,destination};allowed(decision(name,args,request,destination,purpose),claim);return invoke(name,args,p);}
 return {async retrieve(request){
   if(request.queryMode!=='PUBLIC_GENERALIZED'||typeof request.query!=='string')return createEvidencePack({...request,items:[],failureCodes:[request.queryMode==='EXACT_APPROVAL_REQUIRED'?'QUERY_APPROVAL_REQUIRED':'QUERY_DENIED'],adequacy:request.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL',createdAt:now(),budget:{candidates:0,fetched:0,chars:0}});
   let found;try{found=await call('web_search',{query:request.query,count:MAX_CANDIDATES},request,{kind:'EXTERNAL_SERVICE',service:'parallel',model:'web_search'},'PUBLIC_SEARCH');}catch{return createEvidencePack({...request,items:[],failureCodes:['SEARCH_FAILED'],adequacy:request.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL',createdAt:now(),budget:{candidates:0,fetched:0,chars:0}});}
   const candidates=rankCandidates(found?.data?.results??found?.results,request.query), items=[], failures=[];let chars=0,fetched=0;
   for(let n=0;n<candidates.length;n++){const c=candidates[n];const base={sourceId:`s${n+1}`,url:c.url,finalUrl:null,title:c.title,sourceClass:c.sourceClass,publishedAt:c.published,retrievedAt:now(),fetchStatus:'CANDIDATE',fragments:[{kind:'LOCATOR',text:c.url},{kind:'METADATA',text:c.title},{kind:'SNIPPET',text:c.description}],truncated:false,untrusted:true,provenance:{capability:'web_search'}};if(fetched>=MAX_FETCHES||chars>=MAX_CHARS){items.push(base);continue;}
     try{const value=await call('web_fetch',{url:c.url,extractMode:'text',maxChars:PER_SOURCE},request,{kind:'EXTERNAL_SERVICE',service:'firecrawl',model:'web_fetch'},'PUBLIC_FETCH');const raw=value?.data??value;const final=safeUrl(raw?.finalUrl??raw?.url??c.url);if(!final)throw Error('redirect');const content=typeof raw?.text==='string'?raw.text.slice(0,Math.min(PER_SOURCE,MAX_CHARS-chars)):'';if(!content)throw Error('extract');chars+=content.length;fetched++;items.push({...base,finalUrl:final.href,fetchStatus:raw?.truncated?'TRUNCATED':'FETCHED',truncated:raw?.truncated===true,fragments:[...base.fragments,{kind:'FETCHED_CONTENT',text:content}],provenance:{capability:'web_fetch'}});}catch{failures.push('FETCH_FAILED');items.push({...base,fetchStatus:'FETCH_FAILED'});}
   }
   const adequate=fetched?((request.sourceNeed==='WEB_REQUIRED'&&fetched<1)?'INADEQUATE':'ADEQUATE'):(request.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL');
   return createEvidencePack({...request,items,failureCodes:[...new Set(failures)],adequacy:adequate,createdAt:now(),budget:{candidates:candidates.length,fetched,chars}});
 }};
}
