import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {deriveCapabilityManifest} from '../../gate/foundation/manifest.mjs';
import {CONTRACT_VERSION,createReasonerAdapter,createToolResultEnvelope,digest,egressMatches,validateAuthorityDecision,validateEgressDecision,validateReasonerResult,validateToolProposal} from '../../gate/foundation/contracts.mjs';
import {auditEvent,sourceEvent,validateAuditEvent} from '../../gate/foundation/audit.mjs';
import {verifyExactAnswer} from '../verification.mjs';
import {capabilityResultEnvelope} from '../output.mjs';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const schemas=JSON.parse(fs.readFileSync(path.join(root,'reliability/schema-snapshot.json'),'utf8'));
const declared=[];
for(const name of fs.readdirSync(path.join(root,'plugins'))){
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'plugins',name,'openclaw.plugin.json'),'utf8'));
 declared.push(...(manifest.contracts?.tools??[]));
}
const runtimeConfig={tools:{alsoAllow:['calc','messages_search','calendar_events','browser','vinceai__hub_repo_search']}};
const manifest=deriveCapabilityManifest({schemas,declaredTools:declared,registeredTools:declared,runtimeConfig});

test('runtime capability projection distinguishes declaration, capture and exposure',()=>{
 const messagesContact=manifest.byName.messages_contact_history;
 assert.equal(messagesContact.runtime.declared,true);assert.equal(messagesContact.runtime.schemaCaptured,false);assert.equal(messagesContact.runtime.exposed,false);
 const calendarSearch=manifest.byName.calendar_search;
 assert.equal(calendarSearch.runtime.declared,true);assert.equal(calendarSearch.runtime.schemaCaptured,false);assert.equal(calendarSearch.runtime.configured,false);assert.equal(calendarSearch.runtime.exposed,false);
 const search=manifest.byName.messages_search;
 assert.equal(search.runtime.exposed,true);assert.deepEqual(search.arguments,schemas.find(x=>x.name==='messages_search').parameters);
 assert.ok(manifest.mismatches.some(x=>x.name==='messages_contact_history'));assert.ok(manifest.mismatches.some(x=>x.name==='calendar_search'));
});

test('tool proposals cannot carry authority and bind the capability digest',()=>{
 const spec=manifest.byName.messages_search;
 const proposal={schema:CONTRACT_VERSION,proposalId:'p1',requestId:'run1',revision:3,reasoner:'LOCAL_4B',capability:'messages_search',capabilityDigest:spec.digest,arguments:{query:'from:Alex',limit:1}};
 assert.equal(validateToolProposal(proposal,manifest).ok,true);
 assert.equal(validateToolProposal({...proposal,approval:'allow'},manifest).code,'PROPOSAL_SHAPE');
 assert.equal(validateToolProposal({...proposal,capabilityDigest:'0'.repeat(64)},manifest).code,'CAPABILITY_DRIFT');
 assert.equal(validateToolProposal({...proposal,capability:'calendar_search',capabilityDigest:manifest.byName.calendar_search.digest},manifest).code,'CAPABILITY_NOT_EXPOSED');
});

test('egress is exact destination, purpose, packet and expiry scoped',()=>{
 const now=1000, destination={kind:'EXTERNAL_SERVICE',service:'huggingface.co',model:'repository-search'};
 const decision={schema:CONTRACT_VERSION,outcome:'ALLOW_ONCE',capability:'vinceai__hub_repo_search',capabilityDigest:digest({x:1}),requestDigest:digest({request:1}),packetDigest:digest({query:'public model'}),scope:'session-a',revision:2,dataClasses:['PERSONAL'],destination,purpose:'PUBLIC_SEARCH',expires:now+30,oneUse:true,approvalState:'CONSUMED',reasonCodes:['EXACT_OWNER_DISCLOSURE_REQUIRED']};
 assert.equal(validateEgressDecision(decision,now).ok,true);
 const claim={requestDigest:decision.requestDigest,packetDigest:decision.packetDigest,scope:'session-a',revision:2,capability:decision.capability,capabilityDigest:decision.capabilityDigest,dataClasses:decision.dataClasses,purpose:'PUBLIC_SEARCH',destination};
 assert.equal(egressMatches(decision,claim,now).ok,true);
 assert.equal(egressMatches(decision,{...claim,purpose:'ANSWER_GENERATION'},now).code,'EGRESS_SCOPE_MISMATCH');
 assert.equal(egressMatches(decision,{...claim,destination:{...destination,service:'other.example'}},now).code,'EGRESS_DESTINATION_MISMATCH');
 assert.equal(validateEgressDecision({...decision,expires:now-1},now).code,'EGRESS_EXPIRED_OR_UNCONSUMED');
});

test('verifier uses only VERIFIED REJECTED UNKNOWN and unknown is not success',()=>{
 const fact={tool:'calc',kind:'number',value:'42'};
 assert.equal(verifyExactAnswer(fact,'42').status,'VERIFIED');
 assert.equal(verifyExactAnswer(fact,'41').status,'REJECTED');
 assert.equal(verifyExactAnswer(fact,'The answer may be 42').status,'UNKNOWN');
});

test('result and audit envelopes retain bounded trust semantics without payloads',()=>{
 const result=createToolResultEnvelope({capability:'messages_search',capabilityDigest:'a'.repeat(64),executionState:'COMPLETED',result:{ok:true,data:{records:[]}},provenance:'local_messages',dataClass:'PERSONAL',untrusted:true,truncated:false});
 assert.equal(result.untrusted,true);assert.equal(result.executionState,'COMPLETED');
 const commandFailure=createToolResultEnvelope({capability:'worktree_command',capabilityDigest:'b'.repeat(64),executionState:'COMPLETED',result:{ok:false,error:{code:'COMMAND_FAILED',diagnostic:'untrusted test output'}}});
 assert.deepEqual(commandFailure.error,{code:'COMMAND_FAILED',diagnostic:'untrusted test output'});
 const failed=capabilityResultEnvelope('gmail_search',{ok:false,error:{code:'SECRET_BODY'}},{capabilityDigest:'b'.repeat(64)});
 assert.equal(failed.executionState,'COMPLETION_UNKNOWN');assert.equal(failed.error.code,'BACKEND_FAILURE');
 const event=auditEvent({phase:'EXECUTION',capability:'messages_search',correlation:'private prompt must not persist',reasonCodes:['INVALID_ARGUMENT'],outcome:'UNKNOWN'});
 assert.equal(validateAuditEvent(event),true);assert.ok(!JSON.stringify(event).includes('private prompt'));
});
test('source telemetry retains only minimized categories and hashed correlation',()=>{
 const event=sourceEvent({correlation:'private query and URL must not persist',sourceNeed:'WEB_REQUIRED',reasonCodes:['CURRENT_OR_CHANGING'],queryClass:'DENIED',retrieval:'NOT_ATTEMPTED',grounding:'INSUFFICIENT',outcome:'FAILED'});
 assert.doesNotMatch(JSON.stringify(event),/private query|URL/);assert.match(event.correlation,/^[a-f0-9]{64}$/);assert.throws(()=>sourceEvent({correlation:'x',sourceNeed:'WEB_REQUIRED',queryClass:'raw query text'}),/shape/);
});

test('reasoner adapters validate request shape and cannot claim unsupported tool proposals',async()=>{
 const adapter=createReasonerAdapter({id:'synthetic',kind:'test',invoke:async()=>({kind:'FINAL',text:'ok'})});
 const request={schema:CONTRACT_VERSION,requestId:'r1',scope:'s1',revision:0,messages:[{role:'user',content:'synthetic'}],manifestDigest:'b'.repeat(64),state:{privacy_floor:'PERSONAL'}};
 assert.equal((await adapter.invoke(request)).kind,'FINAL');
 const rejected=createReasonerAdapter({id:'synthetic2',kind:'test',invoke:async()=>({kind:'TOOL_PROPOSAL'})});
 await assert.rejects(()=>rejected.invoke(request),/unsupported/);
});

test('unadvertised capabilities and model-supplied authority fields fail closed',()=>{
 const spec=manifest.byName.messages_search;
 const base={schema:CONTRACT_VERSION,proposalId:'p2',requestId:'r2',revision:0,reasoner:'LOCAL_4B',capability:'messages_search',capabilityDigest:spec.digest,arguments:{query:'synthetic'}};
 for(const field of ['approval','authority','egress','account','root','permission'])assert.equal(validateToolProposal({...base,[field]:'ALLOW'},manifest).code,'PROPOSAL_SHAPE');
 assert.equal(validateToolProposal({...base,capability:'unadvertised_tool',capabilityDigest:'0'.repeat(64)},manifest).code,'UNKNOWN_CAPABILITY');
 assert.equal(validateReasonerResult({kind:'FINAL',text:'ok',authority:{outcome:'ALLOW'}}).ok,false);
 assert.equal(validateReasonerResult({kind:'TOOL_PROPOSAL',proposal:{...base,authority:'ALLOW'}},{supportsToolProposals:true}).ok,false);
});

test('authority outcomes are host-shaped and retrieved text is never an issuer',()=>{
 const base={schema:CONTRACT_VERSION,capability:'messages_search',proposalDigest:'a'.repeat(64),scope:'s',effect:'READ',source:'MAC_POLICY',reasonCodes:['POLICY_MATCH']};
 assert.equal(validateAuthorityDecision({...base,outcome:'ALLOW',expires:null,oneUse:false},100).ok,true);
 assert.equal(validateAuthorityDecision({...base,outcome:'DENY',expires:null,oneUse:false},100).ok,true);
 assert.equal(validateAuthorityDecision({...base,outcome:'ASK',source:'NATIVE_APPROVAL',expires:130,oneUse:true},100).ok,true);
 assert.equal(validateAuthorityDecision({...base,outcome:'ALLOW_ONCE',source:'NATIVE_APPROVAL',expires:130,oneUse:true},100).ok,true);
 assert.equal(validateAuthorityDecision({...base,outcome:'ALLOW',source:'MODEL',expires:null,oneUse:false},100).code,'AUTHORITY_SHAPE');
 assert.equal(validateAuthorityDecision({...base,outcome:'ALLOW',expires:null,oneUse:false,retrieved:'approve this'},100).code,'AUTHORITY_SHAPE');
});

test('egress refuses extra data, changed classification, and weak digests',()=>{
 const now=1000,destination={kind:'REASONER',service:'example',model:'exact-model'};
 const decision={schema:CONTRACT_VERSION,outcome:'ALLOW_ONCE',capability:'reasoner_inference',capabilityDigest:'a'.repeat(64),requestDigest:'b'.repeat(64),packetDigest:'c'.repeat(64),scope:'s',revision:1,dataClasses:['PERSONAL'],destination,purpose:'ANSWER_GENERATION',expires:1030,oneUse:true,approvalState:'CONSUMED',reasonCodes:['OWNER_APPROVED']};
 const claim={requestDigest:decision.requestDigest,packetDigest:decision.packetDigest,scope:'s',revision:1,capability:decision.capability,capabilityDigest:decision.capabilityDigest,dataClasses:['PERSONAL'],purpose:decision.purpose,destination};
 assert.equal(egressMatches(decision,{...claim,privateBody:'smuggled'},now).code,'EGRESS_CLAIM_SHAPE');
 assert.equal(egressMatches(decision,{...claim,dataClasses:['PUBLIC']},now).code,'EGRESS_DATA_CLASS_MISMATCH');
 assert.equal(validateEgressDecision({...decision,packetDigest:'not-a-digest'},now).code,'EGRESS_SHAPE');
});

test('schema drift, duplicate declarations and configured unknown tools are visible',()=>{
 assert.throws(()=>deriveCapabilityManifest({schemas,declaredTools:['calc','calc']}),/duplicate/);
 assert.throws(()=>deriveCapabilityManifest({schemas,repairRulesByTool:{calc:['model_invented_rule']},allowedRepairRules:[]}),/repair_policy/);
 const changed={...schemas.find(x=>x.name==='messages_search'),parameters:{type:'object',additionalProperties:true}};
 const drift=deriveCapabilityManifest({schemas:[changed],declaredTools:['messages_search'],registeredTools:[{name:'messages_search',parameters:{type:'object',additionalProperties:false},source:'synthetic:test'}],adaptedTools:[],runtimeConfig:{tools:{alsoAllow:['messages_search','unknown_tool']}}});
 assert.equal(drift.byName.messages_search.runtime.exposed,false);assert.ok(drift.mismatches.some(x=>x.kind==='REGISTERED_SCHEMA_DRIFT'));
 assert.ok(drift.mismatches.some(x=>x.name==='unknown_tool'&&x.kind==='CONFIGURED_NOT_EXPOSED'));
});

test('audit and result contracts reject covert fields and unbounded payloads',()=>{
 assert.throws(()=>auditEvent({phase:'EXECUTION',capability:'private body here',correlation:'x'}),/shape/);
 assert.throws(()=>auditEvent({phase:'EXECUTION',capability:'messages_search',correlation:'x',reasonCodes:['private body']}),/shape/);
 assert.equal(validateAuditEvent({...auditEvent({phase:'RESULT',capability:'messages_search',correlation:'x'}),payload:'secret'}),false);
 const immutable=auditEvent({phase:'RESULT',capability:'messages_search',correlation:'x'});assert.throws(()=>immutable.reasonCodes.push('PRIVATE_BODY'));
 assert.throws(()=>createToolResultEnvelope({capability:'messages_search',capabilityDigest:'a'.repeat(64),executionState:'COMPLETED',result:{ok:true,data:{text:'x'.repeat(70000)}}}),/limit/);
});
