# Project 3 Qwen protocol repair — independent offline review

Date: 2026-09-16. Project 3 remains experimental and unaccepted.

The supported build and all 290 packaged tests pass. Independent counterexamples identify four bounded source-repair gaps below. Source acceptance is blocked pending those fixes; the readiness-inclusive inference budget and exact compiler/template verification are separate pre-live prerequisites. Nothing in this review authorizes installation, inference, provider spending, promotion, or Project 3 acceptance.

## Review target and authorization

Reviewed the existing canonical checkout on `v1.1/project-3-private-lead-workmode`, base HEAD `e168f864eb5ed74d3437102323cdf79804505f06`. This matches the repair report. The index had no staged changes. The target comprised 12 modified tracked files and eight new files, including the previously untracked Python helper, JavaScript modules, fixture and tests. No unrelated starting changes were found or excluded. The inventory and byte identities appear below; HEAD alone does not identify this repair.

Read AGENTS.md, the live baseline, and the repair report completely. Consulted the final historical handoff only to verify the limits of its 22-response claim. `ffe539f3d097ff2e652acc842438590a3ba117ea` remains a historical installed identity, not a currently verified runtime. No private prefix, personal source, credential store, live service, legacy tree, model, provider, or weight cache was inspected or invoked. No implementation, permanent test, settings, schema, manifest, or repair-report edit was made. This review report is the only added source file. No Git history/index operations were performed.

Offline validation used the existing pinned tools and temporary synthetic artifacts under `/tmp/sanctum-qwen-review.OFTOWm`. The supported suite additionally ran its existing local synthetic OCI tests using the available cached runner and Docker daemon; no daemon was started and no image build/pull was invoked. Those containment tests are not a live Work Mode trajectory or GPU qualification.

## Findings, ordered by impact

### R1 — P2: The model never receives the authoritative ESCALATION reason requirement

Evidence: `gate/foundation/work-intent.mjs:29,33–35`; `gate/foundation/vllm-structured-output.mjs:12`; `gate/plugin/work-mode.mjs:128,141,154`; `gate/src/backends.py:192–193`.

Generation intentionally projects the reason schema to `{type:"string"}`. The semantic schema exists only on the host; its digest does not communicate its contents. Captured first and correction requests, including the outer PRIVATE_LEAD profile system prompt, contain neither `^[A-Z][A-Z0-9_:-]{0,79}$` nor a textual explanation of uppercase first character, permitted continuation characters, and 80-character maximum. A correction reports `field:reason`, `keyword:pattern`, and `patternMatch:false`, but never supplies the pattern that must be satisfied. Thus generation-valid prose such as `{"kind":"ESCALATION","reason":"bad reason"}` gets two strict rejections without an actionable format correction.

This is an unaddressed requirement of this repair, not evidence that host validation was weakened or that these were the historical bad responses. Keep the generation omission and strict acceptance. Communicate the exact host-owned format in the initial request and correction, without echoing the rejected value or normalizing arbitrary reason text. Add captured-request regressions proving the rule survives the actual adapter/backend request construction and that a valid corrected reason clears the allowance. Do not change sampling, output limits, or the reasoner's role.

### R2 — P2: Numeric overflow escapes the strict JSON diagnostic and correction route

Evidence: `gate/src/protocol_stream.py:73–80`; `gate/src/common.py:22–29`; `gate/src/backends.py:209–210`; `gate/worker.py:99–105`.

A complete stop/DONE stream containing:

```json
{"kind":"TOOL_PROPOSAL","capability":"worktree_read","arguments":{"path":"index.js","max_chars":1e400}}
```

parses `1e400` as Python infinity. `parse_constant` rejects literal NaN/Infinity but does not reject overflow of a JSON number. `parse_result` returns the recognized proposal; subsequent canonical serialization raises an untyped `ValueError`. The actual worker emits only `UNAVAILABLE / operation_unavailable`; the adapter/coordinator stops `PRIVATE_LEAD_UNAVAILABLE`, with one attempted call, zero effects, no protocol diagnostic and no correction. The ordinary model-call metric is zero on this unavailable path; it must not be used as the future global attempt counter.

Reject nonfinite parsed numbers recursively at the parsing boundary, with a fixed `JSON_PARSE/nonfinite` diagnostic and `private_lead_result_schema`, before canonicalization. Do not coerce the number or accept the proposal. Required regressions: positive/negative exponent overflow, nested arrays/objects, literal NaN/Infinity, a following valid correction, and overflow after another invalid class exhausting the same allowance. Check nonfinite SSE metadata separately without leaking its values. Existing literal-nonfinite tests are insufficient.

### R3 — P2: An interrupted stream loses its first-boundary diagnostic

Evidence: `gate/src/protocol_stream.py:39–70`; `gate/src/backends.py:198–203`.

An iterator raising `OSError("ADVERSARIAL_ERROR_MARKER")` while reading the response bypasses the parser's typed rejection factory. The backend replaces it with `Refused('transport_unavailable')` without diagnostics. The actual worker forwards only that reason. Natural EOF without DONE has a STREAM/completion diagnostic, so two forms of incomplete transport have inconsistent observability.

The stop policy is correct: this is uncertain transport and must not receive another inference attempt or replay an effect. Preserve that policy, but attach a fixed STREAM/incomplete-completion diagnostic at the stream boundary for read interruption/timeouts, without exception strings or provider bodies. Keep deliberate cancellation semantics and HTTP 400/422 handling distinct. Regressions should traverse worker, adapter, coordinator and ledger and prove one attempt, zero effects, zero correction, fixed facts, and no adversarial marker leakage.

### R4 — P2: Reviewer failures discard the new diagnostic before the ledger

Evidence: `gate/plugin/work-command.mjs:120–127`; `gate/plugin/work-mode.mjs:94–98`; contrast proposal-path forwarding at `gate/plugin/work-mode.mjs:132`.

Using the actual `createWorkCommand` caller with synthetic workspace/evaluator/remote responses, an eligible proposal FINAL reaches the reviewer. Returning reviewer `{"kind":"FINAL","text":""}` creates the correct GENERIC_RESULT/text/minLength diagnostic in the PRIVATE_LEAD adapter. The reviewer exception escapes `work-command`, and `assessCandidate` catches it without inspecting the error. The task stops `REVIEWER_UNAVAILABLE` and its real ledger has no PROTOCOL_DIAGNOSTIC event. The valid reviewer control captures exactly the preflight FINAL-only schema and completes.

Forward sanitized diagnostics with the **reviewer's** generation/semantic identities at the reviewer request boundary before rethrowing/stopping. Preserve the existing one-reviewer behavior and REVISE semantics; this finding requests observability, not an additional reviewer call or stronger verdict policy. Add valid, malformed JSON, generic-invalid, and incomplete reviewer-response cases through the actual caller, plus marker-redaction and ledger-chain assertions. The separate FINAL.text verdict/findings parser remains an additional existing policy boundary.

## Independently confirmed behavior and limits

### Shared surfaces and authority

The builder selects in manifest order. Production selection still defaults to four; `allEligible` explicitly selects five only for coverage. Runtime ordinary and research requests were captured in both eligible and ineligible states, and post-patch test-only requests were captured after a synthetic successful patch. Their complete request schemas, branch ordering and both digests equal preflight. The actual reviewer caller emits FINAL only, with no capability branch. `probe_work_intent.py:11–16` consumes the preflight artifact; it does not independently reconstruct a schema. Its standalone transport CLI is not a complete semantic validator or an authorized live harness and was not run.

Hidden/missing capabilities are excluded; invisible FINAL, injected `task_id`, and altered captured manifest identity are denied before effects. Production manifests are frozen. Existing freshness checks, one-use binding, canonical capability digest/exposure/argument validation, authority and exact result egress remain in place. Preflight's synthetic all-registered manifest is not proof of an installed gateway's actual registered capabilities; those must be checked against the installation later. An entirely empty usable capability set still stops REQUIRED_CAPABILITY_UNAVAILABLE before inference; the inability probe instead uses a normal task surface lacking the requested instrument capability.

All seven reported generation/semantic digest pairs were independently recomputed and matched the repair report:

| Surface | Ordered capabilities | Generation SHA-256 | Semantic SHA-256 |
| --- | --- | --- | --- |
| allEligible | source_first_research, worktree_command, worktree_list, worktree_patch, worktree_read | `1b9500698d4cbc3d06b6ed5b5edd899a1db8ca1ae738189bc342ade3a192abde` | `d5f49f9065d87f48ee6dc5f484c4fcbece53b8e054751a4b1764888f2ae26e1f` |
| ordinaryIneligible | worktree_command, worktree_list, worktree_patch, worktree_read | `765dbcdf0942bb330a66dfd34cbfc1271a290caf9ed2f0d39eac63f8f73d2787` | `16f87595681c155cae7c1a9f0690eaa675b471034caef90cae8a5e8d068c5249` |
| ordinaryEligible | worktree_command, worktree_list, worktree_patch, worktree_read | `a8c1fabb092975639ba0cf9b86090a64ecc7ae75537ce10c4543a4e0aa19f125` | `e78c1de040c84c63d676d96f35bb59c494becd47088fb70cc7255e236b6d9ad2` |
| researchIneligible | source_first_research, worktree_command, worktree_list, worktree_read | `f709f64220b6018158d01f86b0485ed8a913422333bdb1a74258b6a7159743fc` | `ae2d5e326de4b996b07b82e3cc898559ea431e27e748db5e210243818b24ca25` |
| researchEligible | source_first_research, worktree_command, worktree_list, worktree_read | `58c0d6ba79cc6f1b4d0dced4676cdd812c9b10d82b6b95d1b297b1cd8fec9f16` | `995e81aa91b8152100ed696ed1b11dab6ade8f3b88131caec68f185b092ba911` |
| testOnlyIneligible | worktree_command | `cc49f8cd2b3d0cde6bb74f5824794d5e31953a190dfb70734730a0b872851d50` | `483dcd8cd9bc33d8810677d7e960461da492e460a801545b6936593cb3a9ad5c` |
| reviewer | none | `38fbf1c7c40b5ca81c55f478cf953f1af538a72b6586a2cc259fd5d9e90d9a29` | `38fbf1c7c40b5ca81c55f478cf953f1af538a72b6586a2cc259fd5d9e90d9a29` |

### Stream, validation and diagnostics

Traced signed executor → worker authorization/dispatch → lifecycle substitution → actual streaming backend/parser → PRIVATE_LEAD adapter → generic validator → Work Intent validator → freshness/context consumption → canonical binding/validation → authority/effect/egress. Supported signed fixtures exercise real HMAC/nonce authorization and `worker.execute`, but replace the worker entry point and lifecycle, and script endpoint bytes. They do not prove installed release verification, readiness, provider state, APFS workspaces, or actual effects.

An additional temporary rendered package exercised the **actual worker entry point**, synthetic settings and source freeze verification, real signatures/nonce database, actual exception forwarding and diagnostic re-allowlisting. Only lifecycle and endpoint delivery were substituted. Five cases (valid, malformed JSON, overflow, interrupted read, injected diagnostic attributes) and five exact signed replay attempts confirmed the stated behavior. Replay is denied through generic operation_unavailable; no new replay behavior was introduced.

Valid streams with role metadata, empty deltas, reasoning-only deltas, usage-only final events, split JSON escapes and multibyte UTF-8 pass. UTF-8 was split at the underlying byte-reader level and reassembled by the buffered line transport used by the parser; arbitrary iterator chunks are not the urllib line contract. Reasoning text is absent from results. Oversize individual lines, aggregate wire data above 2 MiB, aggregate result text above 65536 characters, malformed/duplicate-key event JSON, extra choices/nonzero choice index, mixed native tool/function calls, refusals, content after finish, duplicate finishes, missing stop, non-stop finish, DONE before finish and EOF without DONE reject before effects. These synthetic controls do not establish pinned endpoint compatibility. R2 and R3 are the uncovered cases.

Signed malformed JSON, generic-invalid reasons and semantic-invalid argument types each retain their first failing stage through the adapter, coordinator and real hash-chained ledger. Unknown keys, arbitrary values, enum markers, reasoning and injected exception attributes do not survive diagnostic allowlisting. Every ledger chain link in these signed runs was recomputed. Ordinary mixed parse/generic/semantic invalidities share one correction and stop after a second invalid result; a valid tool result clears the stale correction before the next request. Incomplete transport stops without retry. Recognition of ESCALATION alone is not terminal acceptance. R4 identifies the reviewer exception to the claimed end-to-end observability.

### Retained contract differences and context

AJV generation/semantic checks and both host validators reproduced the published differential matrix. Additional boundary cases confirmed reasons ending in LF, CR, CRLF, U+2028 or U+2029 are generation-valid and host-invalid, including an 80-character reason followed by LF. Reason lengths 1, 79 and 80 pass; 81 fails host acceptance. Lowercase, spaces, non-ASCII and NUL remain rejected. No normalization occurs.

FINAL NUL remains generation/semantic-schema/Work-Intent valid but generic-invalid. ASCII FINAL lengths 32767 and 32768 pass; 32769 fails. 16384 astral characters occupy exactly 32768 JavaScript code units and pass; adding one ASCII character passes both JSON Schemas but fails generic and Work Intent validation. These are retained differences, not newly expanded acceptance.

The isolated `^` check really does remove every anchored pattern (`vllm-structured-output.mjs:12`). Neither that source check nor AJV establishes full-schema support in any actual decoder. R1 is the missing communication of the retained reason requirement, not a recommendation to remove host validation or assume compiler compatibility.

Independent coordinator tests calibrated **63999, 64000 and 64001** serialized user-message characters using six accumulated observations. The first two preserve the task, legal-choice instruction and MAC_CAPABILITY provenance and reach inference; the last stops MODEL_CONTEXT_LIMIT before another call. A second boundary series included an active correction plus accumulated observations and obtained the same threshold. The packaged oversized-context regression also passes. The repair is a stop, not compaction: individual oversize observation envelopes still use their existing omission marker, but the essential whole task request is no longer replaced by one. The 4000-character task contract, 64000-character assembled-message guard, transport byte limits and tokenizer limits are distinct.

Actual backend request construction retains nested task/observation/correction JSON and the exact selected generation schema. Model/revision, context profile (32768 window, 4096 reserved output), 1024-token proposals, temperature zero and thinking disabled remain unchanged. No tokenizer or rendered chat-template token counts were run, and permitted character counts do not prove token fit.

### Microprobe validity

`runProtocolMicroprobes` invokes the real coordinator. The signed fixture additionally covers real signing, Python authorization/nonce handling, dispatch, stream parsing, adapter, generic/semantic validation, canonical binding and host authority. Workspace snapshots, effects, evaluator outcomes, endpoint output and lifecycle are synthetic. The patch seed is a host-inserted coordinator turn with zero model dispatches; it does not establish model editing or test success. No hosted planner or alternative reasoner was added.

Valid but irrelevant worktree_list and wrong-file worktree_read fail semantic grading. Later post-patch/inability repeated-invalid responses stop at that failed probe; no subsequent probe runs. The missing-instrument control reaches valid MODEL_ESCALATION with no effect, and repeated-invalid blocking fails grading. The visible tasks explicitly state their diagnostic goals; expected-output objects live in the host test fixture, not as hidden answer fields in model requests. The valid signed run needs three proposal calls. None of this is real task completion or the unchanged 11-case qualification.

The runner allows at most two reasoner dispatches per probe and six total and has a 180-second abort signal. Its counter is not a readiness-inclusive budget. A callable reasoner that ignores cancellation is not forcibly contained by a JavaScript timer alone; the future supervisor must bound child processes and allocation lifetime.

### Packaging and source scope

AST inspection found all 38 amendment files and the new Python/JavaScript helpers. Independently materialized the base HEAD's existing non-test gate package in a temporary directory, overlaid those 38 files and applied synthetic rendering substitutions, without importing or invoking amendment execution. Verified 43 relative JavaScript import edges, 45 local Python import edges, required prompt/settings/profile/release/runner assets, Python worker/helper import resolution inside that package, JavaScript reviewer/microprobe imports and all seven preflight artifacts. The initial existing package supplies unchanged dependencies; the amendment list is an overlay, not a standalone installer. No missing dependency was reproduced. Source-checkout references to pinned Python/Node/OpenClaw are intentional rendering substitutions, not proof of an installed private state.

The normal amendment still verifies source/install receipts, stopped gateway, no unresolved ownership/leases and a loaded janitor, then builds/pulls a runner, backs up/copies files, updates private receipt/freeze and supports rollback. That command was inspected and **not invoked**. This review does not certify its actual current installation inputs or a live rollback.

SOURCE-MANIFEST has exactly 11 changed existing entries and eight additions, all matching the reviewed bytes; no prior entry was removed or unexplained unchanged hash altered. Runtime pins, lockfile, model/profile/settings, qualification fixtures and expectations are unchanged. Existing tests confirm the passing-test → fresh-evaluator → bounded-review path, strict result egress, Source-First and authority boundaries. No source diff changes nonce/replay/freshness rules, APFS/OCI containment, MUTABLE_WORKTREE_V1, valid inability, known diff/status fingerprint limitations or one-reviewer REVISE semantics. The old 22 response contents and why Qwen chose escalation remain unknown.

## Offline validation record

Commands below ran from the source checkout. Tool logs and temporary counterexamples are retained in `/tmp/sanctum-qwen-review.OFTOWm`; no temporary script is a source change.

| Command/check | Result |
| --- | --- |
| `cat .venv/pyvenv.cfg`; `.venv/bin/python --version`; `uv pip list --python .venv/bin/python` | Existing environment inspected: Python 3.12.14, Pillow 12.3.0, pypdf 6.18.0, imageio-ffmpeg 0.6.0. |
| `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps` | PASS. Existing pinned Python packages checked; 383 npm packages installed from cache with scripts disabled. No download or pin update. |
| `make build` | PASS, six plugin builds and manifests/runtime pins. |
| `umask 022` then `make test` | PASS, 290 tests; 91 gate Node, 120 gate Python, 31 reliability Node, 11 reliability Python, 8 MCP, 18 release/setup, 11 plugin. Zero failures/skips. Includes 10 protocol Node and 10 protocol Python tests, not additional counts. |
| `.venv/bin/python -B /tmp/sanctum-qwen-review.OFTOWm/independent_python.py` | 10 independent tests: 8 PASS, 2 FAIL (R2 numeric overflow and R3 interrupted diagnostic). |
| `node --test /tmp/sanctum-qwen-review.OFTOWm/independent_node.mjs` (initial version) | 10 tests: 6 PASS, 4 FAIL. Three product failures: R1, signed-path R2, R4. One temporary harness calibration error: baseline observations already exceeded 64000. |
| `node --test --test-name-pattern='context at' /tmp/sanctum-qwen-review.OFTOWm/independent_node.mjs` | After changing only temporary harness sizing: 1 PASS, exact 63999/64000/64001 boundary cases. No implementation correction. |
| `node --test --test-name-pattern='accumulated correction\|microprobe stops later' /tmp/sanctum-qwen-review.OFTOWm/independent_node.mjs` | 2 additional PASS: active-correction boundaries and later microprobe failures. |
| `.venv/bin/python -B /tmp/sanctum-qwen-review.OFTOWm/packaging_identity.py` | PASS, manifest/pins/38-file overlay and import/data/schema checks described above. Two initial temporary harness failures were `/tmp` versus resolved `/private/tmp` path assumptions, corrected only in the temporary script. |
| `.venv/bin/python -B /tmp/sanctum-qwen-review.OFTOWm/actual_worker.py` | PASS as characterization: five actual entry-point cases plus five exact signed replay denials; confirms R2/R3, not that they are fixed. Initial temporary harness expected a named replay error; source actually returns operation_unavailable for nonce uniqueness failure. Corrected expectation and used fresh synthetic nonces. |
| `.venv/bin/python -B -c 'from scripts.release_operator import verify; verify()'` | PASS against source freeze and cached runtime pins. |
| `git diff --check` | PASS. |
| `make audit` | PASS after adding this report: 256 files, zero issues. |

Across the final independent Python/Node cases: **22 distinct tests, 17 passing and five failing assertions representing four findings** (R2 is checked at both Python and signed Node boundaries). The complete packaged suite was not rerun after success. Only newly added checks or temporary harness corrections were run thereafter. Early failed harness assumptions are not source findings or hidden successful runs.

Skipped/not authorized: supported private amendment, private doctor/readiness, credentials/OAuth, live provider inventory/price/deletion verification, allocation, model loading/inference, tokenizer/template inspection from private caches, exact compiler execution, live microprobes, real Qwen patch/test trajectory and 11-case live qualification. Local module-presence inspection found no vllm, outlines, outlines_core, xgrammar, transformers or tokenizers in the repository environment. No packages were downloaded to close that gap.

## Separate pre-live gates and one bounded follow-on package

**Global inference budget: NOT IMPLEMENTED.** `PrivateLeadLifecycle.propose` inherits the lease/readiness path at `gate/src/lifecycle.py:237–252`; `ready_locked` can invoke `health_check(smoke=True)` at lines 147 and 160, including repeated attempts inside its readiness loop. `PrivateLeadBackend.health_check` dispatches a 16-token completion at `gate/src/backends.py:173–175`; proposals dispatch 1024 tokens at lines 193–200. None shares the microprobe runner's counter. Each signed executor call spawns another Python worker, so an in-memory JavaScript or worker-local count is inadequate. No nonexistent global budget logic was tested.

After R1–R4, the bounded follow-on is a separately reviewed **diagnostic harness and compiler-preparation package**, with these acceptance checks:

1. Add an explicit experiment-scoped, Mac-owned persistent attempt ledger and atomic dispatch guard shared across readiness/proposals and worker/process transitions. Consume an attempt immediately before each actual completion dispatch, including failure/uncertain dispatch; never refund it. Reject missing/stale experiment ownership, exhausted count, excess output allocation or expired deadline before transmission. At most six total attempts: at most one 16-token smoke and five 1024-token proposals. Three first decisions plus two corrections fit; a third correction must end incomplete. A failed smoke terminates the experiment; no uncounted warmup, characterization, retry or preflight inference. Preserve the one-correction-per-proposal sequence and stop on context limit/valid refusal without using either as permission for extra calls. Budget records must survive worker failure/restart and concurrent dispatch races. Do not casually alter ordinary lifecycle retry policy; make this explicit diagnostic mode and independently test its boundary and crash behavior offline.
2. Prepare exact full-schema compiler/template verification. Locally available now: source pins/launch flags, generated bytes/order/digests, rendering and host contracts. The launch source names vLLM 0.20.1, the pinned Qwen revision and qwen3/qwen3_coder parsers, but no explicit structured-output backend; preparation pins vLLM without a resolved transitive compiler lock. In a separately authorized compatible environment, record the resolved backend, compiler/transitive versions, tokenizer and chat-template byte identities; compile each full production schema and establish representative branch reachability, then measure actual rendered input tokens. A CPU-capable exact compiler environment can supply preparation evidence without model inference. Runtime backend selection/endpoint compatibility may require an explicitly authorized bounded allocation and must be verified before proposal dispatch within that allocation's budget/deadline. Do not demand prior live GPU evidence as a circular prerequisite to ever authorizing a GPU; distinguish preparation from post-allocation identity gates. Mocks/AJV are not compiler proof.
3. Prepare, but do not execute, the coherent stopped-gateway installation and supervised one-allocation runbook. Verify installed source/schema identities, read-only doctor/authenticated readiness, independent janitor and absence of pre-existing managed ownership before allocation. Propagate one absolute experiment deadline through executor, worker, readiness, HTTP calls and cleanup; preserve a cleanup reserve (proposed 600 seconds readiness/preparation + 180 probes + 120 cleanup within 900 seconds). Use an independent supervisor, not just an aborted caller or expired local timer. End on the first readiness/contract/semantic/budget/deadline/cancellation failure. Record failures, uncertainty and unused attempts, without sampling until success.

The proposed one-allocation / 900-second / USD 0.75 compute ceiling at no more than USD 3/hour is **unapproved**, not a billing guarantee. Its arithmetic assumes prorated compute billing (`3 × 900 / 3600 = 0.75`); separately verify current quotes, billing minimums, startup/deletion billing, storage and other charges before requesting authorization. No quote/provider billing evidence was gathered here. Cleanup must be provider-confirmed deletion plus reconciled zero active requests/leases and preserved persistent volumes. Unknown deletion retains ownership records and independent janitor supervision, even after a local deadline; never infer that billing stopped from a timer. This follow-on package prepares reviewable controls; it does not itself authorize a run.

## Durable counterexamples

These snippets run from the checkout using existing offline dependencies. They print the observed defects; they do not patch source or invoke a model. The larger temporary scripts provide the captured-command, signed-worker and ledger assertions described above.

R2/R3 through the actual production backend construction with synthetic transport:

```sh
.venv/bin/python -B - <<'PY'
import sys,io,json,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path('gate/src').resolve()))
from backends import PrivateLeadBackend
from common import canonical
schema={'type':'object'}
intent={'version':'sanctum-work-intent/v1','dialect':'vllm-0.20.1-outlines',
        'schema':schema,'schemaDigest':hashlib.sha256(canonical(schema).encode()).hexdigest(),
        'semanticSchemaDigest':'a'*64}
request={'system':'synthetic','request':{'state':{'workIntent':intent}}}
text='{"kind":"TOOL_PROPOSAL","capability":"worktree_read","arguments":{"path":"index.js","max_chars":1e400}}'
raw=('data: '+json.dumps({'choices':[{'delta':{'content':text},'finish_reason':'stop'}]})+
     '\n\ndata: [DONE]\n\n').encode()
class Broken(io.BytesIO):
    def __next__(self):raise OSError('ADVERSARIAL_ERROR_MARKER')
for response in [io.BytesIO(raw),Broken()]:
    backend=PrivateLeadBackend(json.loads(Path('gate/SETTINGS.json').read_text()))
    with patch.object(backend,'health_check'),patch('backends.urllib.request.build_opener') as opener:
        opener.return_value.open.return_value=response
        try:backend.propose(request)
        except Exception as error:
            print(type(error).__name__,getattr(error,'diagnostic',None))
# Observed: ValueError None; Refused None.
PY
```

R1/R4 at the production coordinator/adapter boundary, with synthetic effects/evaluation:

```sh
node --input-type=module <<'JS'
import {readFileSync} from 'node:fs';
import {deriveCapabilityManifest} from './gate/foundation/manifest.mjs';
import {workModeTools} from './gate/plugin/workspace-tools.mjs';
import {createPrivateLeadReasoner} from './gate/plugin/private-lead.mjs';
import {createWorkMode,MUTABLE_WORKTREE_COMPLETION_POLICY,WORKSPACE_EVIDENCE_VERSION} from './gate/plugin/work-mode.mjs';
import {CONTRACT_VERSION} from './gate/foundation/contracts.mjs';
const names=workModeTools.map(x=>x.name);
const manifest=deriveCapabilityManifest({schemas:workModeTools.map(x=>({name:x.name,description:x.description,parameters:x.parameters})),declaredTools:names,registeredTools:names,adaptedTools:[],runtimeConfig:{tools:{alsoAllow:names}}});
const profile=JSON.parse(readFileSync('gate/runtime/private-lead-interface-profile.json'));
const requests=[];
const reasoner=createPrivateLeadReasoner({profile,
 execute:async()=>({status:'OK',result:{kind:'ESCALATION',reason:'bad reason'}}),
 body:(_o,_t,p)=>{requests.push(p.request);return {};}});
const cfg={manifest,completionPolicy:MUTABLE_WORKTREE_COMPLETION_POLICY,
 workspaceState:async({scope,workspace,turn})=>({schema:WORKSPACE_EVIDENCE_VERSION,scope,workspace,turn,
 diff:{ok:true,executionState:'COMPLETED',bytes:1,digest:'b'.repeat(64)},
 status:{ok:true,executionState:'COMPLETED',bytes:1,digest:'c'.repeat(64)}}),
 invoke:async()=>({ok:true}),egress:()=>({}),evaluate:async()=>({passed:true})};
const run=r=>createWorkMode({...cfg,...r}).run({task:'synthetic',scope:'a'.repeat(32),capabilities:names});
console.log((await run({reasoner})).reason);
console.log(requests.map(r=>JSON.stringify(r).includes('^[A-Z][A-Z0-9_:-]{0,79}$')));
// REPEATED_INVALID_PROPOSAL, [false,false]; inspect requests to see no equivalent prose rule.
const badReview=createPrivateLeadReasoner({profile,execute:async()=>({status:'OK',result:{kind:'FINAL',text:''}}),body:()=>({})});
const events=[];
const result=await run({reasoner:{invoke:async()=>({kind:'FINAL',text:'synthetic'})},
 reviewer:async()=>badReview.invoke({schema:CONTRACT_VERSION,requestId:'r',scope:'s',revision:0,
 messages:[{role:'user',content:'synthetic'}],manifestDigest:manifest.digest,state:{}}),
 onEvent:(kind,value)=>events.push({kind,value})});
console.log(result.reason,events.filter(x=>x.kind==='PROTOCOL_DIAGNOSTIC').length);
// REVIEWER_UNAVAILABLE, 0. The larger independent test also reproduced this through createWorkCommand and its real ledger.
JS
```

## Reviewed byte identities

SHA-256 of every modified/new starting file follows. These identities exclude this new review report and include SOURCE-MANIFEST itself. No hash was refreshed during review.

| Path | SHA-256 |
| --- | --- |
| `SOURCE-MANIFEST.json` | `3619497550dfdbeafc319c9c44497bdad574c88823a51bba7aeebb045fdcd07a` |
| `gate/foundation/contracts.mjs` | `b81f311dacbbba9d046c6c4a6ef5e0af03159af8845f98ef9b140eef5894f6d4` |
| `gate/plugin/private-lead.mjs` | `955b2d15c70fd1a4af134e6348382e3ac346a2805a08b27b7a390f76e878197f` |
| `gate/plugin/work-command.mjs` | `97b02cc05f5fc771fcdb1743c35edb223d25f15eb7d28be245461f30f52c7d63` |
| `gate/plugin/work-ledger.mjs` | `5e82d0632d29ab7b4cbae3dee18421e4b4ed61f980f80034e8826c6d12424597` |
| `gate/plugin/work-mode.mjs` | `1ddfa456b8de30111fcb81cd4bc2e311ad1a65c476a31e95c7569e9ab57494fa` |
| `gate/preflight-work-intent.mjs` | `29733fd5200f86da66bb3c3d02e83e6c40c187bf5c4fbd07d69af7a1e76f8fcf` |
| `gate/src/backends.py` | `f43f132dc523fdbe953804fafdbef68e61563273d8df09d3dc516cd14e597256` |
| `gate/tests/work-mode.test.mjs` | `7520ad3aab2b8f8c7e385f173c3228aaff51246b6238827d9af3cdcc95584de0` |
| `gate/worker.py` | `9e2cc2aa43b234985f61d325b110f1ac83d7e12c056aba572933a8d7cf21ca96` |
| `scripts/test.py` | `851e12cdc8e8a1481896196c92e8f5a7c1fe1b1c753cbab8a262030df387bc6a` |
| `scripts/upgrade_work_mode.py` | `ae106128ba4363814b4520045bc4bd6245e18d9201e4c6db8322555507fe9cf8` |
| `docs/PROJECT-3-QWEN-PROTOCOL-REPAIR.md` | `245c1018c22e9d49e8379b1fc26cb0dcd82cf5f4d132ea56623bc1db9a1977a7` |
| `gate/foundation/decision-surface.mjs` | `0a86eed10700e268013306a5274b602833016f9ca27617f1d8cd5c2868e5494c` |
| `gate/foundation/protocol-diagnostics.mjs` | `4838c8beb8275ee127f886551dd63f604f804af1573cacdad09255d24ef3f8e3` |
| `gate/protocol-microprobe.mjs` | `77dc6ec08319d7a77650557708fe8f65f087e23301a4fb28a124a8dc4be7f2f1` |
| `gate/src/protocol_stream.py` | `b262c1705b18dfa33726c73255a96d15fb84a6a2e37980e2f478ca545d0453bb` |
| `gate/tests/fixtures/protocol_worker.py` | `d52a11ad7da9933317cdac7304ccbf9a7ed4b476a037f9855265b221e7bebbc8` |
| `gate/tests/protocol-repair.test.mjs` | `84c01c40661f2c567de5bd893a145f138d819b43cd65e3bba08b90e04ee67963` |
| `gate/tests/test_protocol_repair.py` | `a4619b926bff0f6f455df45f727ed69116d8ec661080d83b7fad11b7f5bb4a00` |

## Final status

OFFLINE REVIEW BLOCKED — TARGETED REPAIR REQUIRED — NO LIVE RUN AUTHORIZED

This neither accepts Project 3 nor authorizes installation/spending, and establishes no improvement in Qwen task performance.
