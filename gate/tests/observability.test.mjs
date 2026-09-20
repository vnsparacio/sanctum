import test,{after,before} from 'node:test';
import assert from 'node:assert/strict';
import {context,metrics,trace} from '@opentelemetry/api';
import {AsyncLocalStorageContextManager} from '@opentelemetry/context-async-hooks';
import {InMemoryMetricExporter,MeterProvider,PeriodicExportingMetricReader} from '@opentelemetry/sdk-metrics';
import {BasicTracerProvider,InMemorySpanExporter,SimpleSpanProcessor} from '@opentelemetry/sdk-trace-base';
import {createGate} from '../plugin/core.mjs';
import {boundedShutdown,createObservability,initializeObservability} from '../plugin/observability.mjs';
import {createOperationalEmitter} from '../plugin/telemetry-client.mjs';

let spanExporter,traceProvider,metricExporter,meterProvider,observability;
before(()=>{
 spanExporter=new InMemorySpanExporter();traceProvider=new BasicTracerProvider({spanProcessors:[new SimpleSpanProcessor(spanExporter)]});
 context.setGlobalContextManager(new AsyncLocalStorageContextManager().enable());trace.setGlobalTracerProvider(traceProvider);
 metricExporter=new InMemoryMetricExporter();const reader=new PeriodicExportingMetricReader({exporter:metricExporter,exportIntervalMillis:60000});meterProvider=new MeterProvider({readers:[reader]});metrics.setGlobalMeterProvider(meterProvider);
 observability=createObservability({tracer:traceProvider.getTracer('test'),meter:meterProvider.getMeter('test')});
});
after(async()=>{await traceProvider.shutdown();await meterProvider.shutdown();context.disable();trace.disable();metrics.disable();});

const audit=()=>({context_need:{classification:{attachments:'NONE',prior_context:'NONE'},answer:{attachments:'NONE',prior_context:'NONE'}}});
async function representativeGate({failure=false}={}){
 const emitted=[];const settings={settingsFileHash:'a'.repeat(64),approval_expiry_seconds:300,max_context_bytes:32768,max_messages:16,max_request_usd:1,mode:'active',multimodal:{transport:'local'},frontier_transport:'openai'};
 const gate=createGate({settings,key:Buffer.alloc(32,1),observability,emit:event=>emitted.push({...event,ids:observability.currentIds()}),execute:async body=>{
  if(failure&&body.operation==='classify')throw Object.assign(Error('FAKE_SECRET_DO_NOT_EXPORT'),{code:'SYNTHETIC_FAILURE'});
  if(body.operation==='classify')return {status:'OK',state:{...body.state,revision:body.packet.revision},route:'LOCAL_4B',handling:'NORMAL',urgency:'ABSENT',audit:audit(),source_decision:{need:'NONE'}};
  if(body.operation==='answer_local')return {status:'OK',text:'synthetic answer'};
  return {status:'OK',gpu:{phase:'OFFLINE',leases:0}};
 }});
 const ctx={isAuthorizedSender:true,gatewayClientScopes:['operator.admin'],sessionKey:'observability-test'};
 await gate({...ctx,args:'new'});const ticket=await gate({...ctx,args:'ask synthetic request'});const token=ticket.text.match(/\/gate approve ([a-f0-9]{32})/)[1];const job=await gate({...ctx,args:`approve ${token}`});const id=job.text.match(/job:([a-f0-9]{32})/)[1];
 for(let attempt=0;attempt<30;attempt++){await new Promise(resolve=>setImmediate(resolve));const result=await gate({...ctx,args:`result ${id}`});if(!result.text.includes('[Mac gate job:'))break;}
 await traceProvider.forceFlush();return emitted;
}

test('disabled and incomplete configuration are no-op and never require an exporter',async()=>{
 let starts=0;const start=()=>{starts++;throw Error('must not start');};
 for(const env of [{SANCTUM_O11Y_ENABLED:'0'},{SANCTUM_O11Y_ENABLED:'1',SPLUNK_REALM:'us0'},{SANCTUM_O11Y_ENABLED:'1',SPLUNK_REALM:'invalid realm',SPLUNK_ACCESS_TOKEN:'private'}]){
  const value=initializeObservability({env,start});assert.equal(value.enabled,false);assert.equal(await value.withSpan('sanctum.request',{},async()=>42),42);
 }
 assert.equal(starts,0);
});

test('representative owner request exports the real parent-child hierarchy and closes failures',async()=>{
 spanExporter.reset();const emitted=await representativeGate();const spans=spanExporter.getFinishedSpans();
 const root=spans.find(span=>span.name==='sanctum.request');assert.ok(root);const children=spans.filter(span=>span.parentSpanContext?.spanId===root.spanContext().spanId);
 for(const name of ['authority.decide','model.inference','reasoner.route','source_need.classify'])assert.ok(spans.some(span=>span.name===name),name);
 assert.ok(children.some(span=>span.name==='authority.decide'));assert.equal(root.attributes['sanctum.outcome'],'success');
 const correlated=emitted.filter(event=>event.ids.traceId===root.spanContext().traceId);assert.ok(correlated.some(event=>event.eventType==='approval_consumed'));assert.ok(correlated.some(event=>event.eventType==='model_request_completed'));
 spanExporter.reset();await representativeGate({failure:true});const failed=spanExporter.getFinishedSpans();assert.equal(failed.find(span=>span.name==='sanctum.request')?.attributes['sanctum.outcome'],'failure');assert.ok(failed.some(span=>span.name==='model.inference'));
});

test('Core events read the active canonical context and leave outside events uncorrelated',async()=>{
 const calls=[],emit=createOperationalEmitter({env:{PATH:'/usr/bin:/bin',SANCTUM_TELEMETRY_COMMAND:'/synthetic/writer',SANCTUM_TELEMETRY_ROOT:'/synthetic/root'},spawn:(_command,args)=>{calls.push(args);return {status:0};}});
 const root=observability.startSpan('sanctum.request',{'sanctum.component':'gateway'});let expected;
 await root.run(async()=>observability.withSpan('egress.decide',{'sanctum.component':'egress-policy'},async()=>{expected=observability.currentIds();assert.equal(emit({eventType:'approval_consumed',component:'mac-authority',outcome:'completed',taskId:'a'.repeat(32)}),true);}));root.end();
 emit({eventType:'outside',component:'gateway',outcome:'completed',taskId:'digest-not-overwritten'});
 const inside=calls[0],outside=calls[1];assert.equal(inside[inside.indexOf('--trace-id')+1],expected.traceId);assert.equal(inside[inside.indexOf('--span-id')+1],expected.spanId);assert.equal(inside[inside.indexOf('--task-id')+1],'a'.repeat(32));assert.equal(outside.includes('--trace-id'),false);assert.equal(outside[outside.indexOf('--task-id')+1],'digest-not-overwritten');
});

test('metrics have only approved bounded dimensions and exported data remains metadata-only',async()=>{
 metricExporter.reset();const privateValues=['FAKE_SECRET_DO_NOT_EXPORT','sk-fake-super-secret','Authorization: Bearer fake','fake email body','fake prompt','fake file body','fake source excerpt'];
 for(const value of privateValues){const span=observability.startSpan('model.inference',{'sanctum.component':value,'sanctum.model':value,'sanctum.task_id':value,[value]:value});span.end();observability.recordModel({modelRole:value,provider:value,outcome:'success',durationMs:1,inputTokens:2,outputTokens:3});}
 observability.recordRequest({outcome:'success',requestClass:'classification',durationMs:4,run_id:'a'.repeat(32)});observability.recordModel({modelRole:'local-4b',provider:'mlx-local',outcome:'success',durationMs:5,inputTokens:6,outputTokens:7,trace_id:'b'.repeat(32)});observability.recordAuthority('allow');observability.recordEgress('ask');
 await meterProvider.forceFlush();await traceProvider.forceFlush();const exported=metricExporter.getMetrics();const metricPoints=exported.flatMap(resource=>resource.scopeMetrics).flatMap(scope=>scope.metrics).flatMap(metric=>metric.dataPoints);
 const allowed=new Set(['outcome','request_class','model_role','provider','direction','decision']);for(const point of metricPoints)for(const key of Object.keys(point.attributes))assert.ok(allowed.has(key),key);
 const all=JSON.stringify({spans:spanExporter.getFinishedSpans().map(span=>({name:span.name,attributes:span.attributes,events:span.events})),metrics:exported});for(const value of privateValues)assert.equal(all.includes(value),false,value);
 for(const forbidden of ['run_id','task_id','session_id','workspace_id','trace_id','span_id'])assert.equal(all.includes(`"${forbidden}"`),false);
});

test('startup, exporter, and bounded flush failures never change application results',async()=>{
 const bad=createObservability({tracer:{startSpan(){throw Error('endpoint unavailable');}},meter:{createCounter(){throw Error('exporter failed');},createHistogram(){throw Error('exporter failed');}}});
 assert.equal(await bad.withSpan('sanctum.request',{},async()=> 'ordinary-result'),'ordinary-result');bad.recordRequest({outcome:'success'});bad.recordAuthority('allow');
 const configured=initializeObservability({env:{SANCTUM_O11Y_ENABLED:'1',SPLUNK_REALM:'us0',SPLUNK_ACCESS_TOKEN:'private',OTEL_EXPORTER_OTLP_ENDPOINT:'https://invalid.example'},start:()=>{throw Error('must not be called');}});assert.equal(configured.enabled,false);
 const started=performance.now();await boundedShutdown({shutdown:()=>new Promise(()=>{})},20);assert.ok(performance.now()-started<500);
});

test('supported Splunk startup receives only manual signals and safe resources',async()=>{
 let options;const env={SANCTUM_O11Y_ENABLED:'1',SPLUNK_REALM:'us0',SPLUNK_ACCESS_TOKEN:'private-value',OTEL_SERVICE_NAME:'sanctum-gateway',OTEL_RESOURCE_ATTRIBUTES:'deployment.environment.name=development,host.name=sanctum-authority-mac,unapproved=FAKE_SECRET_DO_NOT_EXPORT'};
 const value=initializeObservability({env,serviceVersion:'1.1.0',gitCommit:'a'.repeat(40),start:selected=>{options=selected;},stop:async()=>{}});assert.equal(value.enabled,true);assert.equal(options.serviceName,'sanctum-gateway');assert.deepEqual(options.tracing.instrumentations,[]);assert.equal(options.profiling,false);assert.equal(options.logging,false);assert.equal(options.metrics.runtimeMetricsEnabled,false);
 const attributes=options.resource().attributes;assert.equal(attributes['host.name'],'sanctum-authority-mac');assert.equal(attributes['deployment.environment'],'development');assert.equal(attributes['deployment.environment.name'],'development');assert.equal(attributes['service.version'],'1.1.0');assert.equal(attributes.unapproved,undefined);assert.equal(JSON.stringify(attributes).includes('FAKE_SECRET_DO_NOT_EXPORT'),false);
});

test('default service version comes from the dependency package anchor',()=>{
 let options;const env={SANCTUM_O11Y_ENABLED:'1',SPLUNK_REALM:'us0',SPLUNK_ACCESS_TOKEN:'private-value'};
 const value=initializeObservability({env,start:selected=>{options=selected;},stop:async()=>{}});
 assert.equal(value.enabled,true);assert.equal(options.resource().attributes['service.version'],'1.1.0');
});
