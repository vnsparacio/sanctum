/* Shared pure credential-pattern redaction; no schema or delivery dependencies. */
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
