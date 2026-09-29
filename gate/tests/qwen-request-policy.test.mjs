import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareQwenRequest} from '../runtime/qwen-request-policy.mjs';

const model='local-private-model';
const summarySystem='You are the component that summarizes a conversation when its context window is about to overflow. First, wrap your reasoning in an <analysis> block. Draft in private. Then produce the final summary as the EXACT XML structure below. <state_snapshot><next_step></next_step></state_snapshot>';
const tools=[{type:'function',function:{name:'read_file'}}];

test('ordinary Qwen coding requests retain tools and the coding output cap',()=>{
 const original={model,messages:[{role:'system',content:'You are Qwen Code.'},{role:'user',content:summarySystem}],tools,tool_choice:'auto'};
 const request=prepareQwenRequest(original,model);
 assert.equal(request.max_tokens,4096);
 assert.deepEqual(request.tools,tools);
 assert.equal(request.tool_choice,'auto');
 assert.equal(original.max_tokens,undefined);
});

test('only the built-in summarizer request receives a text-only XML contract and summary headroom',()=>{
 const original={model,messages:[{role:'system',content:summarySystem},{role:'user',content:'synthetic history'}],tools,tool_choice:'auto',parallel_tool_calls:true};
 const request=prepareQwenRequest(original,model);
 assert.equal(request.max_tokens,6144);
 assert.equal('tools' in request,false);
 assert.equal(request.tool_choice,'none');
 assert.equal('parallel_tool_calls' in request,false);
 assert.deepEqual(original.tools,tools);
 assert.equal(request.chat_template_kwargs.enable_thinking,false);
 assert.equal(request.temperature,0.2);
 assert.match(request.messages[0].content,/Produce only the final <state_snapshot> XML/);
 assert.doesNotMatch(request.messages[0].content,/First, wrap your reasoning/);
 assert.match(request.messages[0].content,/<next_step>/);
});

test('the relay refuses another model or malformed message list',()=>{
 assert.throws(()=>prepareQwenRequest({model:'other',messages:[]},model));
 assert.throws(()=>prepareQwenRequest({model,messages:null},model));
 assert.throws(()=>prepareQwenRequest({model,messages:[{role:'system',content:'You are the component that summarizes a conversation when its context window is about to overflow.'}]},model));
});
