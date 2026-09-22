import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import Ajv from 'ajv';

export const CONTENT_TELEMETRY_SCHEMA_VERSION='sanctum.ai-interaction/v1';
export const CONTENT_TELEMETRY_MAX_RECORD_BYTES=65536;
export const CONTENT_TELEMETRY_DEFAULTS=Object.freeze({
 enabled:false,
 retention_days:null,
 access_policy:'owner_only',
});

const schemaPath=fileURLToPath(new URL('../../config/schemas/content-telemetry-v1.schema.json',import.meta.url));
export const contentTelemetrySchema=Object.freeze(JSON.parse(readFileSync(schemaPath,'utf8')));
const validateSchema=new Ajv({allErrors:true,strict:true}).compile(contentTelemetrySchema);

const PRIVATE_KEY=/-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----/g;
const AUTHORIZATION=/\b(authorization\s*:\s*(?:bearer|basic)\s+)[^\s,;]+/gi;
const PREFIXED_CREDENTIAL=/\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})\b/g;
const JWT=/\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g;
const NAMED_CREDENTIAL=/\b(api[_-]?key|access[_-]?token|client[_-]?secret|password|secret)\b(\s*[:=]\s*)(["']?)[^\s,"';]+\3/gi;

export function redactContentText(value){
 if(typeof value!=='string')throw new TypeError('content must be a string');
 return value
  .replace(PRIVATE_KEY,'[REDACTED:PRIVATE_KEY]')
  .replace(AUTHORIZATION,'$1[REDACTED:CREDENTIAL]')
  .replace(PREFIXED_CREDENTIAL,'[REDACTED:CREDENTIAL]')
  .replace(JWT,'[REDACTED:CREDENTIAL]')
  .replace(NAMED_CREDENTIAL,'$1$2[REDACTED:CREDENTIAL]');
}

function byteLength(value){return Buffer.byteLength(JSON.stringify(value),'utf8');}
function validationError(){
 const keywords=[...new Set((validateSchema.errors??[]).map(error=>error.keyword))].sort();
 return Object.assign(new TypeError('invalid content telemetry record'),{code:'CONTENT_TELEMETRY_SCHEMA',keywords});
}

export function prepareContentTelemetryRecord(record){
 if(!record||typeof record!=='object'||Array.isArray(record))throw Object.assign(new TypeError('invalid content telemetry record'),{code:'CONTENT_TELEMETRY_SCHEMA',keywords:['type']});
 const prepared=structuredClone(record);
 if(typeof prepared.user_query==='string')prepared.user_query=redactContentText(prepared.user_query);
 if(typeof prepared.delivered_response==='string')prepared.delivered_response=redactContentText(prepared.delivered_response);
 if(!validateSchema(prepared))throw validationError();
 if(byteLength(prepared)>CONTENT_TELEMETRY_MAX_RECORD_BYTES)throw Object.assign(new RangeError('content telemetry record exceeds byte limit'),{code:'CONTENT_TELEMETRY_SIZE'});
 return Object.freeze(prepared);
}

export function validateContentTelemetryConfig(config){
 if(!config||typeof config!=='object'||Array.isArray(config))return false;
 if(Object.keys(config).some(key=>!['enabled','retention_days','access_policy'].includes(key)))return false;
 if(typeof config.enabled!=='boolean')return false;
 if(config.retention_days!==null&&(!Number.isSafeInteger(config.retention_days)||config.retention_days<1||config.retention_days>3650))return false;
 return ['owner_only','owner_authorized_reviewers'].includes(config.access_policy);
}
