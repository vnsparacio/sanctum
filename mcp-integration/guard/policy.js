import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {CONTRACT_VERSION,digest,validateEgressDecision} from '../../gate/foundation/contracts.mjs';

export const INPUT = path.resolve(process.env.VINCEAI_MCP_INPUT_DIR ?? path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../test-data'));
export const PREFIX = 'vinceai__';
export const TOOLS = Object.freeze([
  'get_current_time', 'hub_repo_search', 'convert_to_markdown',
]);
const deny = reason => ({block: true, blockReason: `Sanctum MCP: ${reason}`});
// Native OpenClaw approval remains the enforcement point. This content-free
// record gives that exact one-call disclosure a stable, destination-bound form.
export function huggingFaceEgress({capability='vinceai__hub_repo_search',args,scope='mcp',revision=0,now=Date.now()/1000}={}) {
  const packetDigest=digest(args);
  const decision={schema:CONTRACT_VERSION,outcome:'ASK',capability,capabilityDigest:digest({capability,policy:'mcp-huggingface-v1'}),requestDigest:digest({scope,revision,capability}),packetDigest,scope,revision,dataClasses:['PERSONAL'],destination:{kind:'EXTERNAL_SERVICE',service:'huggingface.co',model:'repository-search'},purpose:'PUBLIC_SEARCH',expires:now+120,oneUse:true,approvalState:'PENDING',reasonCodes:['EXACT_OWNER_DISCLOSURE_REQUIRED']};
  if(!validateEgressDecision(decision,now).ok)throw Error('egress_contract');
  return decision;
}
function zone(value) {
  if (typeof value !== 'string' || value.length > 80 || !/^[A-Za-z0-9_+./-]+$/.test(value)) return false;
  try { new Intl.DateTimeFormat('en-US', {timeZone: value}); return true; } catch { return false; }
}

export function decide(event) {
  if (!event.toolName.startsWith(PREFIX)) return;
  const name = event.toolName.slice(PREFIX.length);
  if (!TOOLS.includes(name)) return deny('this tool is not operator-approved.');
  const p = event.params;
  if (!p || typeof p !== 'object' || Array.isArray(p)) return deny('invalid arguments.');
  try {
    if (name === 'get_current_time') {
      if (Object.keys(p).some(k => k !== 'timezone') || !zone(p.timezone)) return deny('provide one valid IANA timezone.');
      return;
    }
    if (name === 'convert_to_markdown') {
      if (Object.keys(p).some(k => k !== 'uri') || typeof p.uri !== 'string') return deny('provide a file URI in the approved input directory.');
      const u = new URL(p.uri);
      if (u.protocol !== 'file:' || u.host || u.search || u.hash) return deny('document conversion is offline and accepts only scoped local files.');
      const requested = fileURLToPath(u);
      const host = requested.startsWith('/mcp-input/') ? path.join(INPUT, requested.slice('/mcp-input/'.length)) : requested;
      const real = fs.realpathSync(host);
      const relative = path.relative(fs.realpathSync(INPUT), real);
      if (!relative || relative.startsWith('..') || path.isAbsolute(relative) || real !== path.resolve(host)) return deny('file is outside the input directory or uses a symlink.');
      const st = fs.statSync(real);
      if (!st.isFile() || st.size > 256 * 1024) return deny('input must be a regular file of at most 256 KiB.');
      return {params: {uri: 'file:///mcp-input/' + relative.split(path.sep).map(encodeURIComponent).join('/')}};
    }
    if (name !== 'hub_repo_search') return deny('no external-data policy exists for this tool.');
    const encoded = JSON.stringify(p);
    if (encoded.length > 2000) return deny('external arguments exceed the bounded request size.');
    const adjusted = {...p, limit: 1};
    const egress=huggingFaceEgress({args:adjusted});
    return {
      params: adjusted,
      requireApproval: {
        title: 'Send request to Hugging Face',
        description: `This call sends the selected tool arguments to Hugging Face. Review the exact arguments in the approval details. Local/private content must not be sent without your consent. This approval covers only this call.`,
        severity: 'warning', allowedDecisions: ['allow-once','deny'], timeoutMs: 120000,
        metadata: {egress:{capability:egress.capability,packetDigest:egress.packetDigest,destination:egress.destination,purpose:egress.purpose,expires:egress.expires}},
      },
    };
  } catch { return deny('arguments or local file could not be verified.'); }
}
