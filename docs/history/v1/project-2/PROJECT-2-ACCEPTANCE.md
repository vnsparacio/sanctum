# Project 2 independent acceptance

## Classification and scope

Project 2 is accepted on `v1.1/project-2-source-first` for review into `v1.1-dev`. It begins at accepted Project 1 integration commit `6ae2a93`. Stable `main` and the peeled `v1.0.0` tag remain at `83a1edf`. The branch adds the bounded Source-First text-evidence path and its tests, design, deployment transaction, and review corrections. It does not implement Work Mode, deploy or qualify 122B, introduce Colibrì or Apple Foundation Models, add a crawler/cache/RAG system, or change the reasoning ladder.

`LOCAL_4B`, the current private 80B rollback path/future `PRIVATE_LEAD` evidence profile, `HOSTED_235B`, `MULTIMODAL`, and `OPENAI_FRONTIER` remain distinct. Canonical source continues to pin hosted Qwen 235B as the text tier and Qwen3-VL 30B as the multimodal tier. The review did not silently repin either model merely to match the brief's “Qwen 235B multimodal” wording.

## Independent findings and corrections

Project 2B's handoff was not treated as evidence. Direct source and candidate inspection found material defects and corrected them before acceptance:

- OpenClaw creates separate plugin API objects, so assigning the runtime capability manifest to one plugin API did not make it visible to the gate. A process-local, symbol-keyed bridge now publishes one validated manifest, and the gate reads it lazily after plugin registration.
- The gate-scoped local model could independently call `web_search` or `web_fetch`. Those capabilities are now denied to gate-local sessions and reserved to the distinct Mac source-coordinator session.
- Evidence profiles and grounded-answer validation existed but were not applied to the real answer path. Every tier now receives only its host-rendered evidence view; the Mac validates the strict grounded envelope, delivered source IDs, exact URLs, and required citations before showing answer text.
- The former reasoner view included search titles, snippets, and metadata. Reasoners now receive only fetched content, structured direct facts, or deterministic computed results. Search discovery fields remain host-side for ranking and provenance.
- Truncated successful fetches were represented inconsistently and could not be cited. `TRUNCATED` now requires a fetched-content fragment and explicit truncation, stays bounded, and is citable only when that content was delivered to the selected profile.
- Query egress was implicit. Search now produces an exact Project 1 `EgressDecision`; public generalized queries are `ALLOW`, private exact-query cases are `ASK`, and denied cases are `DENY`. `ASK` and `DENY` never execute. Every fetch retains exact request, packet, capability, destination, purpose, data-class, scope, and revision matching.
- Private-source markers and query generalization were too permissive. Gmail, Messages, Calendar, files, attachments, tool output, and private-context language now trigger conservative minimization; proper names, codenames, identifiers, and unsupported terms cannot enter automatic public queries.
- URL and fetch handling now rejects loopback, link-local, private, carrier-grade NAT, benchmark, `.local`, `.internal`, and local IPv6 destinations; removes fragments before deduplication; distinguishes unsafe redirect, empty extraction, and ordinary fetch failure; and preserves provider-envelope truncation.
- Remote/private/multimodal adapters now request the same strict `GROUNDED_FINAL` schema whenever evidence is supplied. Evidence-bearing private inference cannot reuse the prompt-only session grant, and hosted evidence disclosure is bound to a fresh exact answer ticket.
- The candidate upgrade transaction now includes the manifest bridge and backend schema changes, so installed source can match the reviewed source instead of leaving decisive files behind.

## Falsification results

Fresh tests show that `NONE` performs no retrieval; Mac policy upgrades current/changing questions even when Gemini does not; `WEB_REQUIRED` blocks before answering when adequate fetched evidence is absent; and `WEB_HELPFUL` can continue only with an explicit partial-grounding result. Gemini's `source_need` remains advisory and cannot create egress, authority, or a query.

Search snippets, titles, and metadata remain distinct discovery records and are excluded from every reasoner view. Fetch status is honest for successful, truncated, redirected, empty, failed, and candidate-only records. Deterministic ranking rejects unsafe destinations, deduplicates fragment variants, favors authoritative/official signals, and retains up to six candidates. Retrieval performs one search and at most three fetches, with 4,000 characters per source and 12,000 fetched characters total. Conflicting fetched source text survives the bounded presentation rather than being silently reconciled.

Citations resolve only to fetched or explicitly truncated content present in the exact selected evidence view. A reasoner cannot cite an undisclosed third source from the host pack, a snippet-only candidate, a failed source, a changed URL, or an invented source ID. `WEB_REQUIRED` additionally requires `ADEQUATE`, `GROUNDED`, and at least one real citation. Invalid grounded output is blocked without delivering its answer text.

Adversarial snippets, pages, metadata, and redirect targets attempted to grant permissions, change routes, invoke tools, expand retrieval, approve disclosure, access local files/credentials, and redefine the task. They remained bounded untrusted data. Strict schemas reject added authority fields; fixed host loops cap calls; runtime policy prevents the gate-local reasoner from launching web tools; and retrieved content never reaches ticket, egress, route, or capability decisions.

Private prompts mentioning Gmail, Messages, Calendar appointments, files, attachments, tool output, private context, names, codenames, dates, and identifiers do not become raw external queries. Unsafe cases produce exact `ASK` or `DENY`, with no provider invocation. Search and fetch purposes and destinations are separate and exact; cross-purpose, changed-destination, expired, replayed, or cross-session decisions fail closed. Source telemetry contains bounded categories, counts, and hashed correlation only—never raw query, URL, prompt, page, secret, or private path payloads.

## Compatibility and overengineering review

There is one text retrieval coordinator over the existing `web_search` and `web_fetch` capabilities. Reasoner profiles change source count and character presentation only; they do not change privacy, authority, trust, tools, routing, or approval. `LOCAL_4B` keeps its existing non-web local tool boundary. Private, hosted 235B, multimodal, and frontier adapters remain reasoning-only and no-fallback. Existing attachment preparation and multimodal disclosure controls are unchanged.

No crawler, persistent web cache, vector store, embeddings, duplicate ranking engine, model-specific retrieval fork, deep-research orchestrator, or new dependency was added. The evidence/profile and grounded-envelope seams are retained because Project 3 may substitute `PRIVATE_LEAD` without changing Mac source authority.

## Validation and candidate evidence

The existing dependency environment was inspected and reused through the supported `uv --allow-existing` path. `make deps`, `make build`, and all 196 packaged tests passed. The suites cover gate routing/authority, source policy, query privacy, ranking, search/fetch, evidence profiles, conflicts, truncation/failures, grounding/citations, injection, local/private/hosted/multimodal/frontier adapters, Project 1 contracts/verifier, reliability normalization, MCP boundaries, browser guard, and personal-source brokers. `make audit` scanned 201 files with no issues, and `git diff --check` passed.

The external private candidate was upgraded only while its gateway was stopped and GPU state was `OFFLINE`, with no pod, lease, or allocation uncertainty. The final reviewed source files exactly match their installed counterparts. The latest owner-only rollback record is `<private-prefix>/state/amendments/source-first-1789511726673898000`; its directory is mode `0700` and transaction/receipt files are mode `0600`. Candidate doctor reports source, runtime-pin, and configuration integrity passing; the candidate remains stopped.

During bounded public synthetic live validation, the candidate loaded OpenClaw `2026.8.1` and the expected 12 plugins, listened only on its authenticated loopback gateway, returned Parallel search results as wrapped untrusted data, and fetched an official OpenAI documentation page with a validated final host and explicit truncation. It was stopped after validation. No private prompt, personal source, hosted answer, frontier answer, private GPU allocation, or model repin was used for that check.

## Known limits

- Citation validation establishes provenance and delivery binding, not semantic truth or claim-level entailment. The reasoner must surface conflicts and inference notes; the host does not decide which conflicting prose is true.
- Private exact-query `ASK` is represented and fails closed, but Project 2 does not add a new owner UI/replay flow for consuming that query approval. The owner must reformulate to a safe public query or use a future reviewed workflow.
- Retrieval is intentionally shallow: one search, six candidates, three fetches, and 12,000 fetched characters. There is no autonomous follow-up, crawling, browser fallback, credentialed fetch, cache, or deep research.
- Live validation established Parallel search and the existing core `web_fetch` path. The installed runtime warned that configured `firecrawl` is not a valid auto-detected fetch provider and completed the synthetic fetch through core `cf-markdown`; dedicated Firecrawl selection is therefore not claimed as newly observed live behavior.
- The current doctor output labels optional integrations “unconfigured” without probing credentials even when web settings are present. Source/runtime/configuration integrity and the separate live public checks are the stronger evidence for this review.
- Hosted 235B, multimodal, frontier, and private-80B evidence paths are covered by strict automated transport/identity/grounding contracts in this acceptance. They were not re-run against paid or private providers merely to create acceptance evidence.
- Two existing moderate development-dependency npm advisories remain. No breaking automatic dependency upgrade was mixed into Project 2.

## Rollback and next project

Source rollback is an ordered revert of the Project 2 acceptance/hardening commit followed by the implementation and design commits, leaving accepted Project 1 intact. Candidate rollback uses the matching owner-only transaction while the gateway is stopped; it restores prior generic installed files, freeze, and receipt while preserving private state, credentials, sessions, model caches, and persistent volumes.

After this branch is reviewed and merged into `v1.1-dev`, Project 3 may start only from that updated integration head under a separate request. It may rely on the accepted source-need, minimization, exact egress, EvidencePack, evidence-profile, grounding, failure, and provenance contracts. Project 3 owns replacing `PRIVATE_80B` with `PRIVATE_LEAD`, qualifying Qwen3.5-122B-A10B, characterizing its capabilities, integrating its tools under Mac authority, and Work Mode. Project 2 does none of those tasks.
