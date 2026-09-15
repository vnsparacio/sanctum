# Project 2A — Source-First evidence architecture design

## Status, authority, and inspected baseline

Project 2A source work is inspection and design only. It begins at merge commit `6ae2a93`, the current `origin/v1.1-dev` head containing Project 1 PR #2, on branch `v1.1/project-2-source-first`. The branch and remote integration head matched after fetch, the worktree was clean, stable `main` and tag `v1.0.0` remained at `83a1edf`, and no Project 3 work was started.

The accepted Project 1 implementation is present in source: the runtime-derived capability manifest; strict `ToolProposal`, `AuthorityDecision`, `EgressDecision`, result, reasoner, and audit contracts; exact schema validation; one bounded repair; approval/replay enforcement; tri-state deterministic verification; and provenance-preserving normalization. The existing dependency environment was inspected rather than recreated. All packaged tests and the publication audit passed, and private-prefix doctor passed while reporting the candidate gateway stopped.

Initial inspection found the documented private candidate still at its accepted Project 0 source generation: the pinned web runtime, `web_search`, `web_fetch`, and Browser Guard were enabled, but `gate/foundation` was absent. A subsequent explicit owner instruction authorized a narrow Project 1 runtime update. With the gateway stopped, GPU state offline, and zero leases, the five accepted Project 1 gate/foundation files were installed with an owner-only rollback transaction; installed files match `6ae2a93`, doctor passes, and the gateway remains stopped. No Project 2 implementation was deployed. The documented legacy tree was read only as historical evidence and was not modified or repinned.

The governing invariant remains: **reasoning is replaceable; authority stays on the Mac**. Project 2 adds one Mac-owned textual retrieval system. It does not give a reasoner authority, turn source text into policy, or create model-specific search implementations.

## Baseline that must be preserved

The accepted reasoning ladder is logical rather than a compulsory sequence:

| Profile | Current source implementation | Project 2 treatment |
| --- | --- | --- |
| `LOCAL_4B` | Qwen3-4B-Instruct-2507 through the authenticated loopback OpenClaw agent and its existing local tool loop | Receives a compact Source-First evidence view; local tool authority remains unchanged |
| `PRIVATE_80B` | Existing private Runpod lifecycle and Qwen3-Next 80B transport | Preserved as rollback/runtime compatibility; profile alias becomes future-compatible with `PRIVATE_LEAD` without deploying or qualifying 122B |
| `HOSTED_235B` | Hosted Qwen3 235B through the pinned provider path | Retained; receives richer evidence only after exact answer-destination egress approval |
| `MULTIMODAL` | Current canonical settings pin Qwen3-VL 30B, with separate deterministic image/video/document preparation and local/hosted transport | Retained and not redesigned; combined textual evidence is optional and explicitly bounded |
| `OPENAI_FRONTIER` | Selective strongest external escalation under exact disclosure and provider policy | Retained; receives evidence only under its own destination-bound answer approval |

The brief refers to a “Qwen 235B multimodal” path, while the canonical source, accepted baseline, and historical deployment evidence identify `MULTIMODAL` as Qwen3-VL 30B and `HOSTED_235B` as the separate text tier. Project 2B must preserve both logical tiers and must not silently repin either model. Any literal multimodal-model change needs a separate explicit, reviewed provider/model amendment. The Source-First contracts use profile IDs and capabilities, not literal model names, so that discrepancy does not block this design.

Project 3 owns replacing the private role with `PRIVATE_LEAD`, whose Phase 11 candidate is Qwen3.5-122B-A10B. Project 2 may introduce the neutral profile name in evidence-budget policy while keeping the currently executable `PRIVATE_80B` mapping and lifecycle intact. It must not deploy, benchmark, or qualify the 122B model.

## What already exists and must not be rebuilt

- `gate/PROMPT.txt`, `gate/src/schema.py`, and `gate/src/dispatch.py` already form one Gemini advisory audit followed by deterministic Mac composition. Extend this audit; do not add another remote classifier.
- `gate/plugin/core.mjs` already owns scope, revision, session state, exact disclosure tickets, one-use approval, destination revalidation, cancellation, background work, and tier selection. Retrieval must join this state machine instead of creating another approval store.
- `gate/foundation/contracts.mjs` already defines exact egress purposes including `PUBLIC_SEARCH` and `PUBLIC_FETCH`, and binds capability digest, request and packet digests, data classes, destination, purpose, scope, revision, expiry, and one-use state. Reuse it for every external query and fetch.
- `gate/foundation/manifest.mjs` already recognizes `web_search` and `web_fetch` as pinned, schema-captured, configuration-bound capabilities. A configured tool is not automatically authorized.
- The installed OpenClaw Parallel search and Firecrawl fetch adapters are the existing web path. `scripts/configure.py` enables them, pins their packages, and currently limits search to one result and fetch to 6,000 characters. Project 2 adapts these capabilities; it does not introduce a second HTTP/search stack.
- `reliability/index.mjs`, `runtime.mjs`, and `output.mjs` already validate capability proposals, enforce bounded execution/no replay, normalize results, retain URL/provenance/trust markers, and mark web output untrusted. The existing synthetic source-grounding corpus already proves that a search snippet is not fetched page content.
- `plugins/browser-guard` already isolates the managed browser profile, denies JavaScript evaluation, and applies native approval to interactions. Source-First retrieval uses lightweight `web_search`/`web_fetch`, not browser automation.
- `gate/src/media.py` already creates immutable, bounded, path-free attachment snapshots and samples video deterministically. It remains the multimodal evidence path.
- `gate/src/backends.py` already pins remote identity, forbids fallback/tool calls, enforces provider/cost limits, and tells answerers to use only supplied evidence and treat it as untrusted data. Extend its grounded-output shape; do not weaken its transport rules.
- `gate/src/lifecycle.py` and `runpod.py` own private compute. Retrieval neither allocates GPUs nor changes lifecycle authority.

## Source-First control flow

```text
latest user request
  -> existing exact Gemini audit disclosure and strict response validation
  -> advisory source_need + source reason codes
  -> deterministic Mac source policy
       NONE: continue to selected reasoner
       WEB_HELPFUL / WEB_REQUIRED:
         -> local QueryDraft construction and minimization
         -> exact EgressDecision for PUBLIC_SEARCH
         -> existing web_search capability
         -> local candidate validation and ranking
         -> exact EgressDecision per PUBLIC_FETCH packet
         -> existing web_fetch capability
         -> bounded EvidencePack
  -> existing reasoner selection
  -> profile-specific evidence presentation
  -> grounded answer contract and citation validation
  -> content-minimized events
```

Gemini remains advisory. Its output can recommend retrieval but cannot authorize a query, classify a disclosure as safe, select a destination, approve a fetch, or lower an authoritative Mac requirement. Search and fetched content are inputs to reasoning, never a continuation of the control plane.

## Exact Gemini extension point

Extend the single strict `SCHEMA` in `gate/src/schema.py` with:

```json
"source_need": {
  "classification": "NONE | WEB_HELPFUL | WEB_REQUIRED",
  "reason_codes": ["CURRENT_OR_CHANGING", "TECHNICAL_DOCUMENTATION", "PRODUCT_OR_MODEL_CAPABILITY", "PRICE_OR_AVAILABILITY", "LAW_OR_REGULATION", "CURRENT_ENTITY", "CURRENT_EVENT", "RECENT_RESEARCH", "TRAVEL", "CURRENT_RECOMMENDATION", "NICHE_OR_EXTERNALLY_VERIFIABLE", "SUPPLIED_EVIDENCE_ADEQUATE", "TRANSFORMATION_ONLY", "DETERMINISTIC_OR_SELF_CONTAINED"]
}
```

The object and arrays retain exact keys, bounded length, unique enum members, and `additionalProperties: false`. `gate/PROMPT.txt` gains the `NONE`, `WEB_HELPFUL`, and `WEB_REQUIRED` definitions and examples. It explicitly says source classification is advice and never disclosure permission. `Remote.classify` continues using the one current strict Gemini request and response schema; no query text is requested from Gemini.

Schema invariants include:

- `NONE` requires at least one adequate/self-contained reason code and cannot carry a web-required code;
- `WEB_REQUIRED` requires at least one current, external, niche, or verifiability reason;
- transformation, supplied-text summarization, brainstorming, deterministic calculation, and adequately supplied evidence ordinarily classify `NONE`;
- malformed, contradictory, missing, or overlong source fields fail the existing audit validation and preserve fail-closed behavior.

## Exact Mac policy point

Add a pure, dependency-free `gate/src/source_policy.py`, called by `dispatch.assess` immediately after strict audit validation and before a reasoner route is returned. It accepts only the current packet, trusted session/revision state, the validated advisory source signal, and locally derived provenance facts. It returns an exact `SourceDecision` with no executable authority:

```text
schema, need, reason_codes, query_mode, adequacy_requirement,
request_digest, scope, revision, authority = MAC_POLICY
```

`query_mode` is `NONE`, `PUBLIC_GENERALIZED`, `EXACT_APPROVAL_REQUIRED`, or `DENY`. `adequacy_requirement` is `OPTIONAL` for `WEB_HELPFUL` and `REQUIRED` for `WEB_REQUIRED`.

Mac policy may upgrade `NONE` or `WEB_HELPFUL` to `WEB_REQUIRED` for deterministic high-confidence classes such as explicit “current/latest/today,” prices, regulations, schedules, current product/model behavior, or an explicit request for sources. It must not downgrade Gemini `WEB_REQUIRED` merely because retrieval is inconvenient. Supplied, bounded evidence with adequate provenance may satisfy the need without web access. A model claim that evidence is adequate does not.

The current gate sends only the latest prompt, semantic risk state, and attachment counts to the first audit; raw history, attachment contents, tool results, and private runtime state are absent. Source query construction must happen from that same latest-request boundary. Selected history, attachments, account data, file contents, tool results, or earlier replies are never automatically copied into a query.

## Query construction and privacy

Add a local `QueryDraft` stage in `source_policy.py` with strict limits and deterministic provenance. The draft contains the minimized query, sensitivity class, generalization reason codes, and a digest; raw input is not persisted.

The minimizer:

1. starts only from the latest user request and explicit public terms;
2. strips control syntax, credentials, email addresses, phone numbers, local paths, opaque identifiers, quoted personal narrative, precise personal dates/locations, and attachment/history references;
3. retains public product, standard, organization, error-code, API, statute, place, and technical-topic terms only when they can stand alone as a useful public query;
4. replaces personal narrative with a general topic when a bounded rule is reliable, such as “persistent unilateral calf swelling causes” rather than a named person’s message;
5. refuses to guess when removal changes the task materially or leaves an ambiguous/empty query.

This stage is conservative, not an NLP de-identification claim. It must not use a remote model. A future local query-proposal model may suggest text only through a strict non-authoritative contract, but is not needed for Project 2B.

`PUBLIC_GENERALIZED` can receive a Mac-issued `ALLOW` egress decision for the exact query packet. `EXACT_APPROVAL_REQUIRED` pauses at the existing gate approval UI and describes the exact search purpose and destination; approval resolves only that query once. `DENY` returns a bounded explanation. There is no provider-wide or session-wide search approval.

## Egress and capability integration

Every search and every fetch gets a separate Project 1 `EgressDecision` and claim:

- capability and current capability digest from the runtime manifest;
- request and exact packet digests;
- trusted scope and revision;
- data class (`PUBLIC` only after successful minimization, otherwise `PERSONAL` and `ASK`/`DENY`);
- destination identifying the configured search or fetch service without embedding a literal reasoner model;
- purpose `PUBLIC_SEARCH` or `PUBLIC_FETCH`;
- expiry/one-use/approval state and safe reason codes.

Add `gate/plugin/source-retrieval.mjs` as the single coordinator. `gate/plugin/index.mjs` gives it only the loopback gateway configuration, current manifest projection, and an injected clock/fetch for testing. It validates `egressMatches` immediately before invoking the existing OpenClaw `/tools/invoke` path for exactly `web_search` or `web_fetch`. The loopback call remains authenticated, hits the Project 1 reliability hooks, and returns the existing normalized result envelope. No generic tool name, arbitrary RPC method, provider credential, or remote URL transport is accepted from model/source data.

The coordinator issues a strict host-authored `ToolProposal` for each call with reasoner identity `MAC_SOURCE_COORDINATOR`. It validates the current manifest and arguments. A missing/unexposed capability, schema drift, egress mismatch, changed configuration, or unavailable provider fails before external disclosure. Tool and egress decisions stay separate even though both are reads.

The existing pending-ticket store in `core.mjs` is generalized by purpose, not duplicated. A retrieval ticket and an answer ticket cannot coexist; replacement, cancellation, revision change, exclusion change, expiry, cross-session use, and replay invalidate either. Approval text says whether it authorizes search or answer generation and names the exact destination. Search approval never approves the later reasoner disclosure.

## Search, candidate validation, ranking, and fetch

`web_search` returns discovery records. Its title, snippet/description, publication field, and URL are recorded as `LOCATOR`, `METADATA`, or `SNIPPET`; none is labeled fetched content.

The local ranker in `source-retrieval.mjs` is deterministic and bounded. Before ranking it rejects non-HTTP(S) URLs, embedded credentials, overlong URLs, malformed hosts, loopback/private/link-local targets, unsupported redirects, duplicate canonical URLs, and records that exceed schema/size limits. It does not follow instructions in titles or snippets.

Ranking uses a small explainable score and stable tie-breakers:

1. official/primary source signals;
2. authoritative institution signals;
3. reputable secondary-source signals;
4. community relevance when lived experience is materially requested;
5. lexical relevance to the minimized query;
6. publication/update freshness when the reason code needs it;
7. cross-source diversity and corroboration;
8. successful fetch status over snippet-only status.

There is no global domain allowlist and no source is trusted merely because of its domain. “Official” is a ranking classification, not an authority classification. Consequential or ambiguous claims should use two independent fetched sources where practical.

Fetch the best candidates rather than treating snippets as evidence when an underlying page can reasonably be retrieved. Each fetch has its own exact `PUBLIC_FETCH` decision. Redirects are manual/validated; a changed final host is either independently allowed under policy or recorded as redirect failure. There is no browser fallback, JavaScript execution, credentialed browsing, or autonomous link traversal.

## EvidencePack contract

Add strict, model-independent evidence contracts in `gate/foundation/evidence.mjs` (kept separate from generic capability records). An `EvidencePack` contains:

- schema version, request digest, trusted scope/revision, source need, source reason codes, retrieval status, creation timestamp, and pack digest;
- the applied budget profile and actual candidate/fetch/character counts;
- safe failure codes and an adequacy result (`ADEQUATE`, `PARTIAL`, `INADEQUATE`, `NOT_REQUIRED`);
- an ordered list of `EvidenceItem` records.

Each `EvidenceItem` contains only bounded fields:

- `sourceId`, original URL, validated final URL when present, and title;
- source class: `OFFICIAL_PRIMARY`, `AUTHORITATIVE_INSTITUTION`, `REPUTABLE_SECONDARY`, `COMMUNITY`, or `UNCLASSIFIED`;
- publication/update date when the source supplies one, retrieval timestamp, and freshness classification;
- fetch status: `CANDIDATE`, `FETCHED`, `FETCH_FAILED`, `REDIRECT_FAILED`, `TRUNCATED`, `REJECTED_UNSAFE`, or `EXTRACTION_FAILED`;
- evidence fragments typed as `LOCATOR`, `METADATA`, `SNIPPET`, `FETCHED_CONTENT`, `STRUCTURED_DIRECT_FACT`, or `DETERMINISTIC_COMPUTED_RESULT`;
- the relevant bounded excerpt, truncation flag, untrusted-data flag (always true for web material), and Project 1 result/provenance digest.

The pack cannot contain policy, approval, tool-call, system-message, credential, arbitrary metadata, or executable-action fields. Source IDs are host-generated and stable only within the pack. A page’s claimed date is source metadata, not trusted current time. Structured facts and deterministic computed results must name the capability/provenance that produced them and cannot be relabeled fetched prose.

## Retrieval bounds

Project 2B should make these reviewed defaults configurable only within hard source constants:

| Bound | Hard default |
| --- | --- |
| Search queries | 1 primary plus at most 1 follow-up when required evidence is inadequate |
| Candidates per query | 6 |
| Fetch attempts | 3 total; at most 2 per host |
| Per-source extracted content | 4,000 characters after normalization |
| Total evidence content | 12,000 characters; 16,000 including metadata |
| Search timeout | 20 seconds |
| Fetch timeout | 20 seconds each; 45 seconds retrieval wall clock |
| Redirects | 3, with final destination revalidation |
| Evidence items | 6 candidate records, 3 fetched records |

The installed one-result search setting is insufficient for ranking/corroboration. Project 2B may raise `maxResults` to six and retain Firecrawl’s 6,000-character provider cap, while the coordinator applies the stricter 4,000-character evidence excerpt and total-pack caps. Bounds are enforced locally even if provider configuration is looser. Budget exhaustion is explicit and never triggers autonomous deep research.

## Reasoner-aware presentation without reasoner-owned policy

Add `EvidenceProfile` records keyed by logical reasoner capability, not model name. They may reduce source count, excerpt length, description richness, and total presentation size. They cannot change privacy eligibility, source trust, capability exposure, approval, destination, or retrieval results.

- `LOCAL_COMPACT` (`LOCAL_4B`): up to two fetched sources and 6,000 evidence characters, concise source labels and excerpts.
- `PRIVATE_RICH` (current private rollback mapping and future `PRIVATE_LEAD`): up to three fetched sources and the full 12,000-character content budget. Project 3 may change context limits after qualification.
- `HOSTED_RICH` (`HOSTED_235B`): the same rich view only if the answer-generation egress decision covers the exact rendered evidence packet and destination.
- `FRONTIER_RICH`: the same rule under the frontier’s separate exact destination policy.
- `MULTIMODAL_COMBINED`: the existing media snapshot plus at most the profile-appropriate textual pack, only for an explicitly supported combined request. Text evidence never enters `media.py`; media bytes never enter the text pack.

For `LOCAL_4B`, `local-agent.mjs` receives a host-rendered evidence block with immutable delimiters and source IDs. Project 2B must prevent the gate-scoped local session from independently invoking `web_search` or `web_fetch`; those capabilities are reserved to `MAC_SOURCE_COORDINATOR` for this flow. Other existing local tools keep their current policy. Ordinary non-gate OpenClaw use is not redesigned.

For private/hosted/frontier backends, `worker.py` expands only signed, digest-bound pack references or validates inline bounded packs before inference. Evidence is included in the existing answer packet and exact answer-disclosure digest. A prior search/fetch approval does not authorize sending the pack to a reasoner.

## Grounding and citations

Add a strict `GROUNDED_FINAL` branch to the reasoner-result contract, or an equivalently strict `GroundedAnswerEnvelope`, containing:

- answer text;
- grounding status: `GROUNDED`, `PARTIAL`, `INSUFFICIENT`, or `NOT_APPLICABLE`;
- bounded citations with `sourceId` and exact URL from the pack;
- bounded inference notes identifying claims derived rather than directly stated;
- conflicting/missing evidence reason codes;
- advisory escalation using the existing allowed profile identifiers.

Adapters normalize their provider-specific structured output into this one contract. Citation validation is deterministic: every cited source ID and URL must match the delivered pack; unfetched snippets cannot be presented as fetched evidence; citations to rejected/failed sources are invalid; and extra fields fail closed. This validates citation integrity, not truth of arbitrary prose.

The answer instruction requires externally factual claims to use the pack, separate retrieved statements from inference, disclose conflicts/staleness/truncation, and avoid silently filling evidence gaps from model memory. `WEB_REQUIRED` plus `INADEQUATE` cannot produce an unqualified factual answer. `WEB_HELPFUL` may produce a clearly labeled unsourced/limited answer if retrieval fails. Existing exact deterministic verification remains separate and retains only `VERIFIED`, `REJECTED`, and `UNKNOWN`.

## Failure semantics

| Condition | `WEB_REQUIRED` | `WEB_HELPFUL` |
| --- | --- | --- |
| Search failure/timeout/zero results | Stop or return explicit evidence insufficiency | Degrade with explicit “retrieval unavailable”; no fake citations |
| Fetch failure/extraction failure | Try the next ranked candidate within bounds; otherwise qualify/fail | Snippet may remain labeled discovery-only; qualify |
| Redirect failure/unsafe URL/malformed page | Reject that candidate and record safe code | Same |
| Only low-quality or stale sources | `INADEQUATE` unless the answer is narrowly supportable and clearly bounded | `PARTIAL`, with limitation |
| Conflicting sources | Present conflict with multiple citations; do not choose silently | Same, or decline if not useful |
| Oversize/truncated source | Keep explicit truncation; never imply full-page review | Same |
| Egress `ASK` | Pause at exact-purpose approval | Pause only when the requested helpful search is still worthwhile; cancellation permits qualified local continuation |
| Egress `DENY` | Fail/qualify; do not use parametric memory as current fact | Continue locally with explicit source limitation |
| Evidence budget exhausted | No further automatic retrieval; assess current pack | Same |
| Injection-shaped content | Treat as data; reject malformed structure, not merely suspicious prose | Same |

No failure silently retries a provider call, broadens a query, changes providers, falls back to Browser Guard, escalates a reasoner, or relaxes disclosure policy. Retrieval status and possible completion uncertainty remain explicit.

## Prompt-injection and Browser Guard boundary

Search results and pages are always `untrusted: true`. Their text cannot create an egress or authority decision, alter source need, select a reasoner, increase budgets, request another URL, invoke a tool, open a browser, access a file/credential, add a system message, or redefine the user’s task. Only the local coordinator chooses from validated search candidates under its fixed fetch budget.

Browser Guard is not the Source-First fetch engine. Its managed profile remains available for explicit interactive/browser tasks under current approvals. A web-fetch failure never causes automatic browser navigation. Browser-derived private/session content cannot enter a search query or EvidencePack without a separately designed, owner-approved combined workflow; that is outside Project 2B.

## Content-minimized observability

Extend `gate/foundation/audit.mjs` or add an adjacent strict evidence event with only allowlisted enums/counts/buckets:

- source need and source reason codes;
- retrieval attempted and configured provider class;
- query class (`PUBLIC_GENERALIZED`, `EXACT_APPROVED`, `DENIED`) and generalization reason codes;
- candidate/fetched/source-type count buckets;
- search, fetch, and total latency buckets;
- evidence-size/truncation buckets;
- success/failure/adequacy reason codes;
- selected logical reasoner profile and grounding status.

Correlation remains hashed. Do not record raw queries, URLs containing private tokens, snippets, excerpts, page text, prompt/history, source contents, personal identifiers, approval IDs, credentials, provider bodies, or private paths. Existing network accounting and private receipts remain purpose-specific stores.

## Project 2B source map

Expected changes are deliberately small and concentrated:

- `gate/PROMPT.txt`, `gate/src/schema.py`, `gate/src/dispatch.py`: extend the existing audit and compose authoritative source policy.
- new `gate/src/source_policy.py`: pure source decision, query minimization, adequacy rules, safe reason codes.
- new `gate/foundation/evidence.mjs`: strict QueryDraft/EvidencePack/grounded-answer/profile contracts and validators.
- new `gate/plugin/source-retrieval.mjs`: one search/rank/fetch coordinator over existing OpenClaw tools and Project 1 decisions.
- `gate/plugin/index.mjs`, `core.mjs`, `local-agent.mjs`: integrate retrieval into the existing session/ticket flow, deliver evidence, and block gate-local model-initiated web calls.
- `gate/src/authority.py`, `worker.py`, `backends.py`: add signed retrieval/evidence operations or references, strict grounded answer output, and profile-aware presentation without weakening identity/budget checks.
- `gate/foundation/contracts.mjs`, `audit.mjs`, `manifest.mjs`: only additive evidence/result/event fields and the coordinator mapping needed to reuse current capability digests.
- `reliability/index.mjs`, `output.mjs`, `telemetry.mjs`: preserve normalized web distinctions and enforce the gate-session/coordinator web boundary.
- `scripts/configure.py` and the rendered configuration path: reviewed multi-candidate provider bound and transactional candidate amendment support.
- tests under `gate/tests`, `reliability/tests`, and new synthetic evidence fixtures; accepted architecture/privacy/configuration/testing docs after implementation.
- `SOURCE-MANIFEST.json` only after intentional files are reviewed.

Do not refactor brokers, media parsing, GPU lifecycle, Runpod transport, MCP profile, unrelated plugins, or the historical router to fit the feature.

## Test and falsification plan

Project 2B adds credential-free tests for:

- every valid/invalid `source_need` combination and Mac upgrades that Gemini cannot lower;
- query minimization of private names, contacts, messages, paths, quoted narrative, tokens, and identifiers; empty/ambiguous drafts become `ASK` or `DENY`;
- no history, attachment, tool result, account data, runtime state, or prior reply enters a query;
- exact `PUBLIC_SEARCH`/`PUBLIC_FETCH` destination, capability digest, packet digest, scope, revision, data class, expiry, one-use, and replay/cross-purpose refusal;
- unconfigured, unexposed, or schema-drifted web capabilities fail before network use;
- search snippets remain snippets, candidates are deduplicated, unsafe URLs/redirects are rejected, and ranking is stable and source-diverse;
- fetch-next behavior stays inside count/time/character/host bounds with no provider/action replay;
- EvidencePack exact keys, digest, provenance, source-kind distinctions, truncation, total bounds, and injected policy/tool fields rejected;
- compact/rich/multimodal-combined presentations differ only in presentation bounds;
- gate-local reasoners cannot launch their own web retrieval while non-web local tools retain accepted behavior;
- answer citations must resolve to delivered sources and fetched claims cannot cite snippet-only/failed sources;
- `WEB_REQUIRED` inadequate evidence cannot yield unqualified certainty, while `WEB_HELPFUL` degradation is explicit;
- page instructions cannot change policy, destination, budgets, task, reasoner, tool access, or approval;
- telemetry contains only enums, counts, buckets, and hashed correlation—never raw query/content/URL secrets;
- all existing Project 1 proposal/decision/result/verifier, native approval, media, model identity, provider no-fallback, and lifecycle tests remain green.

Validation remains `make deps`, `make build`, `make test`, `make audit`, `git diff --check`, and the existing production-dependency checks. Live web/provider behavior is separate evidence and must use public synthetic queries/pages. No personal source contents belong in fixtures or logs.

## Candidate deployment decision and plan

Project 2B does need a private-candidate deployment validation because the decisive path crosses the real OpenClaw tool-invocation boundary, optional Parallel/Firecrawl providers, gate approval UI, and installed runtime projection. Unit tests alone cannot establish that integration. It must not deploy during early implementation and must not overwrite the current candidate ad hoc.

The current setup command intentionally refuses to update an existing prefix, and `configure.py` changes only supported owner bindings. The narrow owner-authorized Project 1 transaction does not become a general upgrade interface. Project 2B must therefore add or document a supported transactional source-upgrade operation before deploying Project 2 files into the documented private candidate:

1. complete source review, full offline validation, and an explicit new source freeze;
2. confirm the candidate gateway is stopped, no active gate job/approval is being consumed, and managed GPU ownership/leases/allocation intent are empty while independent cleanup remains active;
3. verify the existing receipt and installed hashes; never continue across unexplained drift;
4. write an owner-only rollback transaction containing only the prior generic installed gate/plugin files, reviewed configuration deltas, and receipt—not secrets, auth stores, conversations, approvals, provider keys, personal data, or live evidence;
5. stage Project 1 plus Project 2 generic files, regenerate the installed gate freeze from reviewed source, and amend the web candidate limit through the supported configuration mechanism;
6. preserve current private accounts, contacts, ports, browser identity, model cache, state databases, provider credentials, persistent volume, and GPU bindings;
7. run doctor, source/runtime projection checks, then start the gateway for synthetic public live checks only;
8. verify public generalized search, exact `ASK`/deny/replay, candidate ranking, real fetch, failed fetch, bounded pack, local/hosted grounded output, and Browser Guard non-fallback; stop at any actual OAuth, UI enrollment, Keychain, or macOS permission checkpoint;
9. keep GPU autostart off and do not start/qualify the 122B candidate.

If a safe transactional upgrade cannot be implemented and reviewed, use a separate new external private prefix for integration testing and leave the accepted candidate untouched. Do not copy the entire old private prefix or auth/state databases. The owner must choose any new prefix and enrollment actions locally.

## Rollback

Project 2A rollback is deletion/revert of this design artifact and its manifest entry; it changes no runtime.

Project 2B source rollback is an ordered revert of Project 2 implementation commits, leaving accepted Project 1 intact. Candidate rollback uses only the matching owner-only upgrade transaction while the gateway is stopped, restoring the prior generic installed files, configuration, freeze, and receipt. It preserves all private state and does not replace databases.

Before runtime rollback, close Source-First jobs and confirm no approval is mid-consumption. If any private compute state is nonempty or uncertain, keep cleanup running and reconcile it before stopping supervision. Never refresh hashes to hide drift, clear approvals/nonces, delete volumes/caches, kill unverified processes, repin, or modify the documented legacy tree.

## Explicit non-goals

No RAG, vector store, embeddings, personal indexing, persistent web corpus, giant cache, autonomous deep research, learned/semantic router, multi-agent architecture, Work Mode, ToolHive migration, LiteLLM, LangGraph, RouteLLM, SkyPilot, Colibrì, Apple Foundation Models, private 122B deployment, model training, general truth verifier, broad browser automation, provider-wide disclosure approval, or new personal-data collection is included.

Project 2 does not remove or redesign `LOCAL_4B`, the current private rollback path, `HOSTED_235B`, `MULTIMODAL`, or frontier escalation. It does not change literal model/provider pins merely to match planning prose. It does not grant remote reasoners tools or let evidence budgets alter authority, privacy, trust, or approval.

PROJECT 2A DESIGN COMPLETE — SWITCH TO GPT-5.6 TERRA MEDIUM AND RUN PROJECT 2B
