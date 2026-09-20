/* Manual, metadata-only observability. Telemetry is never an authority input. */
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

// Setup replaces this anchor in the private installed copy. Source tests use
// the repository package directly; no owner path is committed.
const dependencyAnchor='@SANCTUM_PACKAGE@';
const packagePath=dependencyAnchor.startsWith('@')?fileURLToPath(new URL('../../package.json',import.meta.url)):dependencyAnchor;
const require=createRequire(packagePath);
const {context,metrics,SpanStatusCode,trace}=require('@opentelemetry/api');
const {resourceFromAttributes}=require('@opentelemetry/resources');
const {start:splunkStart,stop:splunkStop}=require('@splunk/otel');
let packageVersion='unknown';
try{const selected=require(packagePath)?.version;if(typeof selected==='string')packageVersion=selected;}catch{}

const SPAN_NAMES=new Set(['sanctum.request','authority.decide','egress.decide','reasoner.route','source_need.classify','source_first.research','model.inference']);
const SPAN_ATTRIBUTES=new Set(['sanctum.component','sanctum.outcome','sanctum.request_class','sanctum.model_role','sanctum.model','sanctum.model_revision','sanctum.provider','sanctum.capability','sanctum.authority_outcome','sanctum.egress_outcome','sanctum.source_need','sanctum.verifier_outcome','sanctum.agent','sanctum.agent_role','sanctum.git_commit','sanctum.run_id','sanctum.task_id','sanctum.session_id','sanctum.workspace_id','sanctum.error_code']);
const RESOURCE_ATTRIBUTES=new Set(['deployment.environment','deployment.environment.name','host.name','service.version','sanctum.host_role','sanctum.git_commit']);
const SAFE_VALUE=/^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$/;
const OUTCOMES=new Set(['success','failure','unavailable','blocked','allowed','denied','needs_approval','unknown']);
const REQUEST_CLASSES=new Set(['classification','inference','owner_request','unknown']);
const SOURCE_NEEDS=new Set(['NONE','WEB_HELPFUL','WEB_REQUIRED','UNKNOWN']);
const DECISIONS=new Set(['allow','deny','ask','other']);
const DIRECTIONS=new Set(['input','output']);
const CONFLICTING_ENDPOINTS=['OTEL_CONFIG_FILE','OTEL_EXPERIMENTAL_CONFIG_FILE','OTEL_EXPORTER_OTLP_ENDPOINT','OTEL_EXPORTER_OTLP_TRACES_ENDPOINT','OTEL_EXPORTER_OTLP_METRICS_ENDPOINT'];
const SENSITIVE_VALUE=/(?:^sk-|authorization|bearer|cookie|credential|password|private.?key|secret|prompt|email.?body|file.?body|source.?excerpt)/i;
let preloadedObservability=null;

const safeString=value=>typeof value==='string'&&SAFE_VALUE.test(value)&&!SENSITIVE_VALUE.test(value)?value:null;
const elapsedMs=start=>Math.max(0,performance.now()-start);
const safeCall=fn=>{try{return fn();}catch{return undefined;}};

function safeAttributes(attributes={}){
 const result={};
 for(const [name,value] of Object.entries(attributes)){
  if(!SPAN_ATTRIBUTES.has(name))continue;
  if(typeof value==='boolean'||Number.isFinite(value))result[name]=value;
  else{const selected=safeString(value);if(selected!==null)result[name]=selected;}
 }
 return result;
}

function resourceAttributes({env,serviceVersion,gitCommit}){
 const selected={
  'deployment.environment':'development',
  'deployment.environment.name':'development',
  'host.name':'sanctum-authority-mac',
  'service.version':safeString(serviceVersion)??'unknown',
  'sanctum.host_role':'authority',
 };
 for(const pair of String(env.OTEL_RESOURCE_ATTRIBUTES??'').split(',')){
  const separator=pair.indexOf('=');if(separator<1)continue;
  const name=pair.slice(0,separator).trim(),value=safeString(pair.slice(separator+1).trim());
  if(RESOURCE_ATTRIBUTES.has(name)&&value!==null)selected[name]=value;
 }
 const commit=safeString(gitCommit);if(commit)selected['sanctum.git_commit']=commit;
 return selected;
}

function metricAttributes(values,allowed){
 const result={};
 for(const [name,value] of Object.entries(values??{})){
  if(!allowed.has(name))continue;
  const selected=safeString(value);if(selected!==null)result[name]=selected;
 }
 return result;
}

const disabledHandle=()=>({run:fn=>fn(),setOutcome:()=>{},end:()=>{},ids:()=>({traceId:null,spanId:null})});

export function createObservability({enabled=true,tracer=trace.getTracer('sanctum-gateway'),meter=metrics.getMeter('sanctum-gateway'),shutdown=async()=>{}}={}){
 if(!enabled)return {enabled:false,startSpan:disabledHandle,withSpan:async(_name,_attributes,fn)=>fn(),currentIds:()=>({traceId:null,spanId:null}),recordRequest:()=>{},recordModel:()=>{},recordAuthority:()=>{},recordEgress:()=>{},shutdown:async()=>{}};
 const instruments={
  requestCount:safeCall(()=>meter.createCounter('sanctum.request.count')),
  requestDuration:safeCall(()=>meter.createHistogram('sanctum.request.duration',{unit:'ms'})),
  modelCount:safeCall(()=>meter.createCounter('sanctum.model.call.count')),
  modelDuration:safeCall(()=>meter.createHistogram('sanctum.model.duration',{unit:'ms'})),
  modelTokens:safeCall(()=>meter.createCounter('sanctum.model.tokens',{unit:'{token}'})),
  authorityCount:safeCall(()=>meter.createCounter('sanctum.authority.decision.count')),
  egressCount:safeCall(()=>meter.createCounter('sanctum.egress.decision.count')),
 };
 function currentIds(){
  try{const value=trace.getSpan(context.active())?.spanContext();return value&&trace.isSpanContextValid(value)?{traceId:value.traceId,spanId:value.spanId}:{traceId:null,spanId:null};}catch{return {traceId:null,spanId:null};}
 }
 function startSpan(name,attributes={}){
  if(!SPAN_NAMES.has(name))return disabledHandle();
  let span,activeContext,start=performance.now(),ended=false;
  try{span=tracer.startSpan(name,{attributes:safeAttributes(attributes)});activeContext=trace.setSpan(context.active(),span);}catch{return disabledHandle();}
  const handle={
   run(fn){let invoked=false;try{return context.with(activeContext,()=>{invoked=true;return fn();});}catch(error){if(invoked)throw error;return fn();}},
   setOutcome(outcome,errorCode=null){
    const selected=OUTCOMES.has(outcome)?outcome:'unknown';safeCall(()=>span.setAttribute('sanctum.outcome',selected));
    const code=safeString(errorCode);if(code)safeCall(()=>span.setAttribute('sanctum.error_code',code));
    if(selected==='failure'||selected==='unavailable')safeCall(()=>span.setStatus({code:SpanStatusCode.ERROR}));
   },
   end(outcome='success',errorCode=null){if(ended)return;ended=true;handle.setOutcome(outcome,errorCode);safeCall(()=>span.end());},
   ids(){try{const value=span.spanContext();return trace.isSpanContextValid(value)?{traceId:value.traceId,spanId:value.spanId}:{traceId:null,spanId:null};}catch{return {traceId:null,spanId:null};}},
   durationMs(){return elapsedMs(start);},
  };
  return handle;
 }
 async function withSpan(name,attributes,fn){
  const handle=startSpan(name,attributes);let outcome='success',errorCode=null;
  try{return await handle.run(fn);}catch(error){outcome='failure';errorCode=safeString(error?.code)??'OPERATION_FAILED';throw error;}finally{handle.end(outcome,errorCode);}
 }
 function recordRequest({outcome='unknown',requestClass='unknown',durationMs=0}={}){
  const attrs={outcome:OUTCOMES.has(outcome)?outcome:'unknown',request_class:REQUEST_CLASSES.has(requestClass)?requestClass:'unknown'};
  safeCall(()=>instruments.requestCount?.add(1,attrs));safeCall(()=>instruments.requestDuration?.record(Math.max(0,durationMs),attrs));
 }
 function recordModel({modelRole='unknown',provider='unknown',outcome='unknown',durationMs=0,inputTokens=null,outputTokens=null}={}){
  const attrs=metricAttributes({model_role:modelRole,provider,outcome:OUTCOMES.has(outcome)?outcome:'unknown'},new Set(['model_role','provider','outcome']));
  safeCall(()=>instruments.modelCount?.add(1,attrs));safeCall(()=>instruments.modelDuration?.record(Math.max(0,durationMs),attrs));
  for(const [direction,value] of [['input',inputTokens],['output',outputTokens]])if(Number.isSafeInteger(value)&&value>=0){const tokenAttrs={...attrs,direction};if(DIRECTIONS.has(direction))safeCall(()=>instruments.modelTokens?.add(value,tokenAttrs));}
 }
 function recordAuthority(decision){const selected=DECISIONS.has(decision)?decision:'other';safeCall(()=>instruments.authorityCount?.add(1,{decision:selected}));}
 function recordEgress(decision){const selected=DECISIONS.has(decision)?decision:'other';safeCall(()=>instruments.egressCount?.add(1,{decision:selected}));}
 return {enabled:true,startSpan,withSpan,currentIds,recordRequest,recordModel,recordAuthority,recordEgress,shutdown};
}

export function currentTraceContext(){
 try{const value=trace.getSpan(context.active())?.spanContext();return value&&trace.isSpanContextValid(value)?{traceId:value.traceId,spanId:value.spanId}:{traceId:null,spanId:null};}catch{return {traceId:null,spanId:null};}
}

export function initializeObservability({env=process.env,serviceVersion=packageVersion,gitCommit=null,start=splunkStart,stop:splunkStop}={}){
 if(env.SANCTUM_O11Y_ENABLED!=='1')return createObservability({enabled:false});
 const realm=safeString(env.SPLUNK_REALM),token=typeof env.SPLUNK_ACCESS_TOKEN==='string'&&env.SPLUNK_ACCESS_TOKEN.trim()?env.SPLUNK_ACCESS_TOKEN:null;
 const serviceName=safeString(env.OTEL_SERVICE_NAME)??'sanctum-gateway';
 if(!realm||!token||CONFLICTING_ENDPOINTS.some(name=>env[name]))return createObservability({enabled:false});
 try{
  start({realm,accessToken:token,serviceName,logLevel:'none',resource:()=>resourceFromAttributes(resourceAttributes({env,serviceVersion,gitCommit})),tracing:{instrumentations:[],serverTimingEnabled:false},metrics:{runtimeMetricsEnabled:false,debugMetricsEnabled:false},profiling:false,logging:false,opamp:false,secureapp:false});
  return createObservability({enabled:true,shutdown:()=>stop()});
 }catch{safeCall(()=>{void Promise.resolve(stop()).catch(()=>{});});return createObservability({enabled:false});}
}

export function preloadObservability(options={}){
 if(preloadedObservability===null)preloadedObservability=initializeObservability(options);
 return preloadedObservability;
}

export function gatewayObservability(options={}){
 return preloadedObservability??initializeObservability(options);
}

export async function boundedShutdown(observability,timeoutMs=2000){
 try{let timer;await Promise.race([Promise.resolve(observability?.shutdown?.()).catch(()=>{}),new Promise(resolve=>{timer=setTimeout(resolve,timeoutMs);timer.unref?.();})]);clearTimeout(timer);}catch{}
}

export const observabilityPolicy={spanNames:SPAN_NAMES,spanAttributes:SPAN_ATTRIBUTES,resourceAttributes:RESOURCE_ATTRIBUTES,sourceNeeds:SOURCE_NEEDS};
