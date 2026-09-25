/* One bounded coordinator over the existing pinned web capabilities. */
import {createEvidencePack} from '../foundation/evidence.mjs';
import {CONTRACT_VERSION,digest,egressMatches,validateEgressDecision,validateToolProposal} from '../foundation/contracts.mjs';

const MAX_CANDIDATES=6, MAX_FETCHES=3, MAX_CHARS=12000, PER_SOURCE=4000;
const blocked=/(?:^(?:localhost|0\.0\.0\.0|127\.|10\.|192\.168\.|169\.254\.|198\.1[89]\.|172\.(?:1[6-9]|2\d|3[01])\.|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.|::1$|f[cd][0-9a-f:]*$|fe[89ab][0-9a-f:]*$)|\.(?:local|internal)$)/i;
const safeUrl=value=>{try{const u=new URL(value);u.hash='';const host=u.hostname.replace(/^\[|\]$/g,'');return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&!blocked.test(host)&&u.href.length<=2048?u:null;}catch{return null;}};
const sourceClass=url=>/\b(?:gov|edu)\b/i.test(url.hostname)?'AUTHORITATIVE_INSTITUTION':/(?:docs|developer|support|official)/i.test(url.hostname)?'OFFICIAL_PRIMARY':/(?:reddit|forum|community|stack)/i.test(url.hostname)?'COMMUNITY':'REPUTABLE_SECONDARY';
const common=new Set(['about','and','are','for','from','has','how','the','this','use','what','when','where','with','zip']);
const tokens=value=>(String(value).toLowerCase().match(/[a-z][a-z0-9]{2,}|\b\d{5}\b/g)??[]).filter(x=>!common.has(x));
const queryScaffolding=new Set(['latest','recent','current','today','tomorrow','headline','headlines','news','documentation','documented','docs','product','official','source','sources','information','find','report','tell','show','give','please']);
const newsAnswerScaffolding=new Set(['cite','fetched','publication','date','available','its']);
export const newsSubject=query=>[...new Set(tokens(query).filter(x=>!queryScaffolding.has(x)&&!newsAnswerScaffolding.has(x)))].slice(0,6).join(' ');
const fetchedTitle=value=>{
 if(typeof value!=='string')return null;
 const wrapped=value.match(/---\s*\n([^\n]+)\n<<<END_EXTERNAL_UNTRUSTED_CONTENT\b/);
 const title=(wrapped?.[1]??value).replace(/[\x00-\x1f\x7f]/g,' ').trim();
 return title&&title.length<=512&&!title.includes('<<<')?title:null;
};
function fetchedTopicMatch(query,content){
 const terms=[...new Set(tokens(query).filter(x=>!queryScaffolding.has(x)&&(!datedNews(query)||!newsAnswerScaffolding.has(x))))];
 if(!terms.length)return true;
 const words=new Set(tokens(content));
 const has=term=>words.has(term)||[...words].some(word=>term.length>=5&&word.startsWith(term.slice(0,Math.max(4,term.length-2))));
 return terms.filter(has).length>=Math.min(2,terms.length);
}
const weatherZip=query=>/\b(?:weather|forecast|temperature|rain|conditions)\b/i.test(query)?query.match(/\b\d{5}\b/)?.[0]??null:null;
const datedNews=query=>/\b(?:latest|newest|most recent)\b.{0,100}\b(?:headline|news|story|announcement)\b|\b(?:headline|news)\b.{0,100}\b(?:latest|newest)\b/i.test(query);
const isoDay=value=>{if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return null;const day=new Date(value+'T12:00:00Z');return Number.isNaN(day.getTime())||day.toISOString().slice(0,10)!==value?null:value;};
const dateMs=value=>{const parsed=Date.parse(value??'');return Number.isFinite(parsed)?parsed:null;};
const fresh=(date,current)=>{const a=dateMs(date),b=dateMs(current);return a!==null&&b!==null&&b-a>=-86400000&&b-a<=7*86400000;};
const publishedInBody=content=>{
 const match=content.slice(0,1800).match(/\b(?:date\s+published|published(?:\s+on)?|publication\s+date)\s*[:\-]?\s*([A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})/i);
 return match&&dateMs(match[1])!==null?new Date(dateMs(match[1])).toISOString().slice(0,10):null;
};
// Some fetched article bodies omit their page metadata. A publisher's dated
// final path can corroborate the independent search publication date, but a
// path or search date alone is not enough and conflicts must fail closed.
const publishedInDatedPath=(final,published)=>{
 const match=final.pathname.match(/\/(\d{4})\/(\d{2})\/(\d{2})(?:\/|$)/);
 if(!match)return null;
 const day=isoDay(`${match[1]}-${match[2]}-${match[3]}`);
 return day&&day===isoDay(String(published??'').slice(0,10))?day:null;
};
const verifiedPublication=(content,final,published)=>{
 const body=publishedInBody(content),search=isoDay(String(published??'').slice(0,10));
 if(body&&search&&body!==search)return null;
 return body??publishedInDatedPath(final,published);
};
const weekdays=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
export function weatherTargetDate(prompt,at=new Date()){
 if(typeof prompt!=='string'||!weatherZip(prompt))return null;
 const explicit=prompt.match(/\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,)?\s+(\d{4})\b/i);
 if(explicit){const months=['january','february','march','april','may','june','july','august','september','october','november','december'],month=months.indexOf(explicit[1].toLowerCase()),date=Number(explicit[2]),year=Number(explicit[3]);const day=new Date(Date.UTC(year,month,date,12));return day.getUTCFullYear()===year&&day.getUTCMonth()===month&&day.getUTCDate()===date?day.toISOString().slice(0,10):null;}
 if(!/\b(?:today|tomorrow)\b/i.test(prompt))return null;
 const day=new Date(at);if(/\btomorrow\b/i.test(prompt))day.setDate(day.getDate()+1);
 return day.getFullYear()+'-'+String(day.getMonth()+1).padStart(2,'0')+'-'+String(day.getDate()).padStart(2,'0');
}
function selectedWeatherPeriod(content,targetDate,zip){
 const day=weekdays[new Date(targetDate+'T12:00:00Z').getUTCDay()];
 // OpenClaw readability commonly flattens NWS headings into e.g.
 // "FridayMostly sunny... Friday NightPartly cloudy...". Split only at
 // recognized period labels, never on a numeric weather fact in another day.
 const tail=content.slice(Math.max(0,content.search(/\bDetailed Forecast\b/i)));
 const labels=/(?:^|[.\s])((?:This Afternoon|Today|Tonight|Sunday(?: Night)?|Monday(?: Night)?|Tuesday(?: Night)?|Wednesday(?: Night)?|Thursday(?: Night)?|Friday(?: Night)?|Saturday(?: Night)?))(?=[A-Z]|\s|:)/gi;
 const markers=[...tail.matchAll(labels)].map(match=>({name:match[1],start:match.index+match[0].length-match[1].length,end:match.index+match[0].length}));
 const index=markers.findIndex(marker=>marker.name.toLowerCase()===day.toLowerCase());if(index<0)return null;
 const rest=tail.slice(markers[index].end,markers[index+1]?.start??undefined);
 const fact=rest.trim().slice(0,700);
 return weatherFact.test(fact)?`Forecast for ZIP ${zip} on ${targetDate} (${day}): ${fact}`:null;
}
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

// Search metadata is not factual evidence. Keep it only while it fits the
// evidence contract; never let provider-sized snippets discard fetched facts.
function boundedPack(input){
 const attempt=items=>createEvidencePack({...input,items});
 let items=input.items;
 try{return attempt(items);}catch(error){if(error?.message!=='evidence_pack_limit')throw error;}
 items=items.map(item=>({...item,fragments:item.fragments.map(fragment=>fragment.kind==='SNIPPET'?{...fragment,text:fragment.text.slice(0,256)}:fragment)}));
 try{return attempt(items);}catch(error){if(error?.message!=='evidence_pack_limit')throw error;}
 items=items.map(item=>({...item,fragments:item.fragments.filter(fragment=>fragment.kind==='FETCHED_CONTENT')}));
 try{return attempt(items);}catch(error){if(error?.message!=='evidence_pack_limit')throw error;}
 items=items.filter(item=>['FETCHED','TRUNCATED'].includes(item.fetchStatus));
 try{return attempt(items);}catch(error){if(error?.message!=='evidence_pack_limit')throw error;}
 for(let pass=0;pass<12;pass++){
   items=items.map(item=>({...item,fetchStatus:'TRUNCATED',truncated:true,fragments:item.fragments.map(fragment=>({...fragment,text:fragment.text.slice(0,Math.max(1,Math.floor(fragment.text.length/2)))}))}));
   try{return attempt(items);}catch(error){if(error?.message!=='evidence_pack_limit')throw error;}
 }
 return createEvidencePack({...input,items:[],adequacy:input.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL',failureCodes:[...input.failureCodes,'PACK_LIMIT']});
}

export function rankCandidates(results,query,at=nowIso()){
 const seen=new Set(), valid=[],zip=weatherZip(query),news=datedNews(query),subject=news?newsSubject(query):'';
 for(const row of Array.isArray(results)?results:[]){const u=safeUrl(row?.url);if(!u||seen.has(u.href))continue;seen.add(u.href);const snippet=typeof row.snippet==='string'?row.snippet:row.description;
   // Search rank alone cannot establish a location. For an explicit weather
   // ZIP, discard candidates that never identify that ZIP at all.
   if(zip&&!`${u.href} ${row.title??''}`.includes(zip))continue;
   if(news&&subject&&!subject.split(' ').some(term=>tokens(row.title??'').includes(term)))continue;
   valid.push({url:u.href,title:typeof row.title==='string'?row.title.slice(0,512):'',description:typeof snippet==='string'?snippet.slice(0,4000):'',published:typeof row.published==='string'?row.published.slice(0,64):null,sourceClass:sourceClass(u),score:score({...row,description:snippet,url:u.href},query)});}
 return valid.sort((a,b)=>{
   if(news){const af=fresh(a.published,at),bf=fresh(b.published,at);if(af!==bf)return af?-1:1;const ap=!!publishedInDatedPath(new URL(a.url),a.published),bp=!!publishedInDatedPath(new URL(b.url),b.published);if(ap!==bp)return ap?-1:1;const ad=dateMs(a.published),bd=dateMs(b.published);if(ad!==null&&bd!==null&&ad!==bd)return bd-ad;}
   return b.score-a.score||a.url.localeCompare(b.url);
 }).slice(0,MAX_CANDIDATES);
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
   const targetDate=isoDay(request.targetDate),zip=weatherZip(request.query),news=datedNews(request.query);
   const subject=news?newsSubject(request.query):'';
   const day=isoDay(now().slice(0,10)),previousDay=day?new Date(dateMs(day)-86400000).toISOString().slice(0,10):null;
   const query=targetDate&&zip?`${request.query} ${targetDate}`:news&&subject?`What is the latest headline about ${subject}? ${day}`:request.query;
   const queries=news&&subject&&previousDay?[query,`What is the latest headline about ${subject}? ${previousDay}`]:[query];
   const searchSpec=manifest?.byName?.web_search, queryDecision=queryEgressDecision({...request,query},'web_search',searchSpec?.digest??'0'.repeat(64));
   if(queryDecision.outcome!=='ALLOW'||request.queryMode!=='PUBLIC_GENERALIZED'||typeof request.query!=='string')return createEvidencePack({...request,items:[],failureCodes:[queryDecision.outcome==='ASK'?'QUERY_APPROVAL_REQUIRED':'QUERY_DENIED'],adequacy:request.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL',createdAt:now(),budget:{candidates:0,fetched:0,chars:0}});
   const foundResults=[];let searchesSucceeded=0;
   for(const variant of queries){try{const found=await call('web_search',{query:variant,count:MAX_CANDIDATES},request,{kind:'EXTERNAL_SERVICE',service:'parallel',model:'web_search'},'PUBLIC_SEARCH');searchesSucceeded++;foundResults.push(...(found?.data?.results??found?.results??[]));}catch{/* Other bounded public variant may still succeed. */}}
   if(!searchesSucceeded)return createEvidencePack({...request,items:[],failureCodes:['SEARCH_FAILED'],adequacy:request.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL',createdAt:now(),budget:{candidates:0,fetched:0,chars:0}});
   const candidates=rankCandidates(foundResults,query,now()), items=[], failures=[];let chars=0,fetched=0,usable=0;
   for(let n=0;n<candidates.length;n++){const c=candidates[n];const base={sourceId:`s${n+1}`,url:c.url,finalUrl:null,title:c.title,sourceClass:c.sourceClass,publishedAt:c.published,retrievedAt:now(),fetchStatus:'CANDIDATE',fragments:[{kind:'LOCATOR',text:c.url},{kind:'METADATA',text:c.title},{kind:'SNIPPET',text:c.description}],truncated:false,untrusted:true,provenance:{capability:'web_search'}};if(fetched>=MAX_FETCHES||chars>=MAX_CHARS){items.push(base);continue;}
     try{const value=await call('web_fetch',{url:c.url,extractMode:'text',maxChars:PER_SOURCE},request,{kind:'EXTERNAL_SERVICE',service:'openclaw-core',model:'web_fetch'},'PUBLIC_FETCH');const raw=value?.data??value;const final=safeUrl(raw?.finalUrl??raw?.url??c.url);if(!final)throw Error('redirect');let content=typeof raw?.text==='string'?raw.text.slice(0,Math.min(PER_SOURCE,MAX_CHARS-chars)):'';if(!content)throw Error('extract');const truncated=value?.truncated===true||raw?.truncated===true||raw.text.length>content.length;chars+=content.length;fetched++;
       if(targetDate&&zip){content=final.hostname==='forecast.weather.gov'?selectedWeatherPeriod(content,targetDate,zip):null;if(!content){failures.push('WEATHER_PERIOD_UNAVAILABLE');items.push({...base,finalUrl:final.href,fetchStatus:'REJECTED_IRRELEVANT',truncated,provenance:{capability:'web_fetch'}});continue;}}
       else if(zip&&!weatherFact.test(content)){failures.push('WEATHER_FACT_UNAVAILABLE');items.push({...base,finalUrl:final.href,fetchStatus:'REJECTED_IRRELEVANT',truncated,provenance:{capability:'web_fetch'}});continue;}
       else if(!zip&&!fetchedTopicMatch(request.query,content)){failures.push('FETCHED_TOPIC_MISMATCH');items.push({...base,finalUrl:final.href,fetchStatus:'REJECTED_IRRELEVANT',truncated,provenance:{capability:'web_fetch'}});continue;}
       const verifiedPublished=news?verifiedPublication(content,final,c.published):c.published;
       if(news&&!fresh(verifiedPublished,now())){failures.push('FRESH_PUBLICATION_UNAVAILABLE');items.push({...base,finalUrl:final.href,fetchStatus:'REJECTED_IRRELEVANT',truncated,provenance:{capability:'web_fetch'}});continue;}
       const title=fetchedTitle(raw?.title);
       usable++;items.push({...base,title:title??base.title,publishedAt:verifiedPublished,finalUrl:final.href,fetchStatus:truncated?'TRUNCATED':'FETCHED',truncated,fragments:[...base.fragments,{kind:'FETCHED_CONTENT',text:content}],provenance:{capability:'web_fetch',titleSource:title?'web_fetch':'web_search'}});}catch(error){const status=error?.message==='redirect'?'REDIRECT_FAILED':error?.message==='extract'?'EXTRACTION_FAILED':'FETCH_FAILED';failures.push(status);items.push({...base,fetchStatus:status});}
   }
   if(zip&&fetched&&!usable)failures.push(targetDate?'WEATHER_PERIOD_UNAVAILABLE':'WEATHER_FACT_UNAVAILABLE');
   if(zip&&!candidates.length)failures.push('WEATHER_LOCATION_UNVERIFIED');
   const adequate=usable?'ADEQUATE':request.sourceNeed==='WEB_REQUIRED'?'INADEQUATE':'PARTIAL';
   return boundedPack({...request,items,failureCodes:[...new Set(failures)],adequacy:adequate,createdAt:now(),budget:{candidates:candidates.length,fetched,chars}});
 }};
}
