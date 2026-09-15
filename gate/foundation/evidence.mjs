/* Model-neutral Source-First records. Web material remains untrusted data. */
import {canonical,deepFreeze,digest,isRecord} from './contracts.mjs';

export const EVIDENCE_VERSION='sanctum-evidence/v1';
const needs=new Set(['NONE','WEB_HELPFUL','WEB_REQUIRED']);
const adequacy=new Set(['NOT_REQUIRED','ADEQUATE','PARTIAL','INADEQUATE']);
const statuses=new Set(['CANDIDATE','FETCHED','FETCH_FAILED','REDIRECT_FAILED','TRUNCATED','REJECTED_UNSAFE','EXTRACTION_FAILED']);
const classes=new Set(['OFFICIAL_PRIMARY','AUTHORITATIVE_INSTITUTION','REPUTABLE_SECONDARY','COMMUNITY','UNCLASSIFIED']);
const kinds=new Set(['LOCATOR','METADATA','SNIPPET','FETCHED_CONTENT','STRUCTURED_DIRECT_FACT','DETERMINISTIC_COMPUTED_RESULT']);
const grounding=new Set(['GROUNDED','PARTIAL','INSUFFICIENT','NOT_APPLICABLE']);
const exact=(v,k)=>isRecord(v)&&Object.keys(v).length===k.length&&k.every(x=>Object.hasOwn(v,x));
const text=(v,n=4000)=>typeof v==='string'&&v.length<=n&&!v.includes('\0');
const url=v=>typeof v==='string'&&v.length>0&&v.length<=2048&&/^https?:\/\//.test(v);
const id=v=>typeof v==='string'&&/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(v);
const code=v=>typeof v==='string'&&/^[A-Z][A-Z0-9_:-]{0,79}$/.test(v);

export const EVIDENCE_PROFILES=Object.freeze({
 LOCAL_4B:Object.freeze({id:'LOCAL_COMPACT',maxSources:2,maxChars:6000}),
 PRIVATE_80B:Object.freeze({id:'PRIVATE_RICH',maxSources:3,maxChars:12000}),
 PRIVATE_LEAD:Object.freeze({id:'PRIVATE_RICH',maxSources:3,maxChars:12000}),
 HOSTED_235B:Object.freeze({id:'HOSTED_RICH',maxSources:3,maxChars:12000}),
 OPENAI_FRONTIER:Object.freeze({id:'FRONTIER_RICH',maxSources:3,maxChars:12000}),
 MULTIMODAL:Object.freeze({id:'MULTIMODAL_COMBINED',maxSources:2,maxChars:6000}),
});

export function validateEvidenceItem(v){
 const keys=['sourceId','url','finalUrl','title','sourceClass','publishedAt','retrievedAt','fetchStatus','fragments','truncated','untrusted','provenance'];
 if(!exact(v,keys)||!id(v.sourceId)||!url(v.url)||!(v.finalUrl===null||url(v.finalUrl))||!text(v.title,512)||!classes.has(v.sourceClass)||!(v.publishedAt===null||text(v.publishedAt,64))||!text(v.retrievedAt,64)||!statuses.has(v.fetchStatus)||!Array.isArray(v.fragments)||v.fragments.length>6||typeof v.truncated!=='boolean'||v.untrusted!==true||!isRecord(v.provenance))return {ok:false,code:'EVIDENCE_ITEM_SHAPE'};
 if(!v.fragments.every(x=>exact(x,['kind','text'])&&kinds.has(x.kind)&&text(x.text,4000)))return {ok:false,code:'EVIDENCE_FRAGMENT_SHAPE'};
 const retrieved=['FETCHED','TRUNCATED'].includes(v.fetchStatus);
 if(retrieved&&!v.fragments.some(x=>x.kind==='FETCHED_CONTENT'))return {ok:false,code:'EVIDENCE_FETCH_MISSING'};
 if(!retrieved&&v.fragments.some(x=>x.kind==='FETCHED_CONTENT'))return {ok:false,code:'EVIDENCE_FETCH_FALSE'};
 if(v.fetchStatus==='TRUNCATED'&&v.truncated!==true)return {ok:false,code:'EVIDENCE_TRUNCATION_FALSE'};
 return {ok:true,value:deepFreeze(structuredClone(v))};
}

export function createEvidencePack({requestDigest,scope,revision,sourceNeed,reasonCodes=[],items=[],failureCodes=[],adequacy:state='NOT_REQUIRED',createdAt='1970-01-01T00:00:00Z',budget={candidates:0,fetched:0,chars:0}}={}){
 if(typeof requestDigest!=='string'||!/^[a-f0-9]{64}$/.test(requestDigest)||!text(scope,256)||!Number.isSafeInteger(revision)||revision<0||!needs.has(sourceNeed)||!Array.isArray(reasonCodes)||!reasonCodes.every(code)||!Array.isArray(failureCodes)||!failureCodes.every(code)||!adequacy.has(state)||!Array.isArray(items)||items.length>6||!isRecord(budget)||!Number.isSafeInteger(budget.candidates)||budget.candidates<0||budget.candidates>6||!Number.isSafeInteger(budget.fetched)||budget.fetched<0||budget.fetched>3||!Number.isSafeInteger(budget.chars)||budget.chars<0||budget.chars>12000||!text(createdAt,64))throw Error('evidence_pack_shape');
 const checked=items.map(x=>{const r=validateEvidenceItem(x);if(!r.ok)throw Error(r.code);return r.value;});
 const pack={schema:EVIDENCE_VERSION,requestDigest,scope,revision,sourceNeed,reasonCodes:[...reasonCodes],adequacy:state,createdAt,budget:{...budget},failureCodes:[...failureCodes],items:checked};
 if(canonical(pack).length>20000)throw Error('evidence_pack_limit');
 return deepFreeze({...pack,packDigest:digest(pack)});
}

export function presentEvidence(pack,tier){
 if(!pack||pack.schema!==EVIDENCE_VERSION||typeof pack.packDigest!=='string')throw Error('evidence_pack_invalid');
 const profile=EVIDENCE_PROFILES[tier]??EVIDENCE_PROFILES.LOCAL_4B;let used=0,items=[];
 for(const item of pack.items){if(items.length>=profile.maxSources)break;const fragments=[];for(const f of item.fragments.filter(x=>['FETCHED_CONTENT','STRUCTURED_DIRECT_FACT','DETERMINISTIC_COMPUTED_RESULT'].includes(x.kind))){if(used>=profile.maxChars)break;const value=f.text.slice(0,Math.max(0,profile.maxChars-used));if(value){fragments.push({kind:f.kind,text:value});used+=value.length;}}if(fragments.length)items.push({sourceId:item.sourceId,url:item.finalUrl??item.url,sourceClass:item.sourceClass,retrievedAt:item.retrievedAt,fetchStatus:item.fetchStatus,truncated:item.truncated,untrusted:true,fragments});}
 return deepFreeze({schema:EVIDENCE_VERSION,profile:profile.id,packDigest:pack.packDigest,sourceNeed:pack.sourceNeed,adequacy:pack.adequacy,items});
}

export function validateGroundedAnswer(answer,pack,presented=null){
 if(!exact(answer,['kind','text','grounding','citations','inferences','missingReasons','escalation'])||answer.kind!=='GROUNDED_FINAL'||!text(answer.text,32768)||!grounding.has(answer.grounding)||!Array.isArray(answer.citations)||answer.citations.length>6||!Array.isArray(answer.inferences)||!answer.inferences.every(x=>text(x,512))||!Array.isArray(answer.missingReasons)||!answer.missingReasons.every(code)||!['NONE','HOSTED_235B','OPENAI_FRONTIER'].includes(answer.escalation))return {ok:false,code:'GROUNDED_ANSWER_SHAPE'};
 const byId=new Map(pack?.items?.map(x=>[x.sourceId,x]));
 const delivered=new Map(presented?.items?.map(x=>[x.sourceId,x]));
 for(const c of answer.citations){if(!exact(c,['sourceId','url'])||!id(c.sourceId)||!url(c.url))return {ok:false,code:'CITATION_SHAPE'};const item=byId.get(c.sourceId),view=presented?delivered.get(c.sourceId):item;if(!item||!['FETCHED','TRUNCATED'].includes(item.fetchStatus)||(item.finalUrl??item.url)!==c.url||!view?.fragments?.some(x=>x.kind==='FETCHED_CONTENT'))return {ok:false,code:'CITATION_UNDELIVERED'};}
 if(pack?.sourceNeed==='WEB_REQUIRED'&&(pack.adequacy!=='ADEQUATE'||answer.grounding!=='GROUNDED'||answer.citations.length===0))return {ok:false,code:'GROUNDING_REQUIRED'};
 return {ok:true,value:deepFreeze(structuredClone(answer))};
}
