import test from 'node:test';
import assert from 'node:assert/strict';
import {configureAiTransportHost,getAiTransportHost} from '@openclaw/ai';
import {buildOpenAICompletionsParams} from '@openclaw/ai/transports';

test('local catalog leaves a final-answer budget after tool-heavy context',()=>{
  const previousHost=getAiTransportHost();
  configureAiTransportHost({
    resolveProviderRequestCapabilities:()=>({
      endpointClass:'custom',knownProviderFamily:'',usesExplicitProxyLikeEndpoint:true,
      supportsNativeStreamingUsageCompat:false,
      supportsOpenAICompletionsStreamingUsageCompat:false,allowsAnthropicServiceTier:false,
    }),
  });
  try{
    const model=contextWindow=>({
      id:'synthetic-local4b',name:'Synthetic local model',provider:'mlx-local',
      api:'openai-completions',baseUrl:'http://127.0.0.1:28080/v1',
      input:['text'],reasoning:false,contextWindow,maxTokens:4096,
    });
    const context={
      systemPrompt:'s'.repeat(51000),
      messages:[{role:'user',content:[{type:'text',text:'Find a synthetic message.'}]}],
      tools:[{name:'synthetic_search',description:'x'.repeat(6000),
        parameters:{type:'object',properties:{query:{type:'string'}}}}],
    };
    const outputLimit=window=>{
      const params=buildOpenAICompletionsParams(model(window),context,{});
      return params.max_completion_tokens??params.max_tokens;
    };
    assert.equal(outputLimit(16384),1);
    assert.equal(outputLimit(24576),4096);
  }finally{configureAiTransportHost(previousHost);}
});
