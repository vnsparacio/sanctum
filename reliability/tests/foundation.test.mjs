import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {deriveCapabilityManifest} from '../../gate/foundation/manifest.mjs';
import {CONTRACT_VERSION,createReasonerAdapter,createToolResultEnvelope,digest,egressMatches,validateEgressDecision,validateToolProposal} from '../../gate/foundation/contracts.mjs';
import {auditEvent,validateAuditEvent} from '../../gate/foundation/audit.mjs';
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
const manifest=deriveCapabilityManifest({schemas,declaredTools:declared,runtimeConfig});

test('runtime capability projection distinguishes declaration, capture and exposure',()=>{
 const messagesContact=manifest.byName.get('messages_contact_history');
 assert.equal(messagesContact.runtime.declared,true);assert.equal(messagesContact.runtime.schemaCaptured,false);assert.equal(messagesContact.runtime.exposed,false);
 const calendarSearch=manifest.byName.get('calendar_search');
 assert.equal(calendarSearch.runtime.declared,true);assert.equal(calendarSearch.runtime.schemaCaptured,false);assert.equal(calendarSearch.runtime.configured,false);assert.equal(calendarSearch.runtime.exposed,false);
 const search=manifest.byName.get('messages_search');
 assert.equal(search.runtime.exposed,true);assert.deepEqual(search.arguments,schemas.find(x=>x.name==='messages_search').parameters);
 assert.ok(manifest.mismatches.some(x=>x.name==='messages_contact_history'));assert.ok(manifest.mismatches.some(x=>x.name==='calendar_search'));
});

test('tool proposals cannot carry authority and bind the capability digest',()=>{
 const spec=manifest.byName.get('messages_search');
 const proposal={schema:CONTRACT_VERSION,proposalId:'p1',requestId:'run1',revision:3,reasoner:'LOCAL_4B',capability:'messages_search',capabilityDigest:spec.digest,arguments:{query:'from:Alex',limit:1}};
 assert.equal(validateToolProposal(proposal,manifest).ok,true);
 assert.equal(validateToolProposal({...proposal,approval:'allow'},manifest).code,'PROPOSAL_SHAPE');
 assert.equal(validateToolProposal({...proposal,capabilityDigest:'0'.repeat(64)},manifest).code,'CAPABILITY_DRIFT');
 assert.equal(validateToolProposal({...proposal,capability:'calendar_search',capabilityDigest:manifest.byName.get('calendar_search').digest},manifest).code,'CAPABILITY_NOT_EXPOSED');
});

test('egress is exact destination, purpose, packet and expiry scoped',()=>{
 const now=1000, destination={kind:'EXTERNAL_SERVICE',service:'huggingface.co',model:'repository-search'};
 const decision={schema:CONTRACT_VERSION,outcome:'ALLOW_ONCE',capability:'vinceai__hub_repo_search',capabilityDigest:digest({x:1}),requestDigest:digest({request:1}),packetDigest:digest({query:'public model'}),scope:'session-a',revision:2,dataClasses:['PERSONAL'],destination,purpose:'PUBLIC_SEARCH',expires:now+30,oneUse:true,approvalState:'CONSUMED',reasonCodes:['EXACT_OWNER_DISCLOSURE_REQUIRED']};
 assert.equal(validateEgressDecision(decision,now).ok,true);
 const claim={requestDigest:decision.requestDigest,packetDigest:decision.packetDigest,scope:'session-a',revision:2,capability:decision.capability,purpose:'PUBLIC_SEARCH',destination};
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
 const failed=capabilityResultEnvelope('gmail_search',{ok:false,error:{code:'SECRET_BODY'}});
 assert.equal(failed.executionState,'NOT_STARTED');assert.equal(failed.error.code,'BACKEND_FAILURE');
 const event=auditEvent({phase:'EXECUTION',capability:'messages_search',correlation:'private prompt must not persist',reasonCodes:['INVALID_ARGUMENT'],outcome:'UNKNOWN'});
 assert.equal(validateAuditEvent(event),true);assert.ok(!JSON.stringify(event).includes('private prompt'));
});

test('reasoner adapters validate request shape and cannot claim unsupported tool proposals',async()=>{
 const adapter=createReasonerAdapter({id:'synthetic',kind:'test',invoke:async()=>({kind:'FINAL',text:'ok'})});
 const request={schema:CONTRACT_VERSION,requestId:'r1',scope:'s1',revision:0,messages:[{role:'user',content:'synthetic'}],manifestDigest:'b'.repeat(64)};
 assert.equal((await adapter.invoke(request)).kind,'FINAL');
 const rejected=createReasonerAdapter({id:'synthetic2',kind:'test',invoke:async()=>({kind:'TOOL_PROPOSAL'})});
 await assert.rejects(()=>rejected.invoke(request),/unsupported/);
});
