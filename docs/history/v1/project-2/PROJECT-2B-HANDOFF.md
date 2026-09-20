# Project 2B implementation handoff

Project 2B implements the accepted Source-First evidence path on `v1.1/project-2-source-first`. It does not merge or change `main`, begin Project 3, add Apple Foundation Models or Colibrì, or add a second search/fetch transport.

## Implemented boundary

`gate/src/schema.py` requires Gemini's `source_need` audit declaration. The declaration is one of `NONE`, `WEB_HELPFUL`, or `WEB_REQUIRED`, with closed reason-code classes. `gate/src/source_policy.py` is deterministic Mac policy: it can upgrade a non-required model assessment for current, time-sensitive, price, schedule, regulatory, product-behavior, or explicitly sourced questions; it cannot downgrade a web requirement. It minimizes queries and refuses automatic external search when a public generalization is unavailable.

`gate/plugin/source-retrieval.mjs` is the sole coordinator. It uses the already configured `web_search` and `web_fetch` capabilities only through the authenticated loopback tool path and Project 1 proposal/egress validation. A capability name, request digest, revision, scope, destination, purpose, and public data class are fixed before each call. Search output is discovery metadata only. Unsafe URLs are rejected, candidates are deterministically ranked, and at most six candidates, three fetches, 4,000 characters per source, and 12,000 fetched characters total are admitted.

`gate/foundation/evidence.mjs` creates a bounded, versioned EvidencePack. Fetched content, snippets, locators, metadata, timestamps, provenance, truncation, failure state, and untrusted status remain distinct. Grounded citations can name fetched source IDs only; snippet-only or inadequate evidence cannot claim a grounded answer.

The existing tier ladder remains unchanged: `LOCAL_4B`, private 80B, hosted 235B, multimodal, then frontier. Evidence is rendered for the local agent and carried as bounded untrusted data to remote reasoners. No reasoner receives source authority or a general tool channel. Retrieval failure is explicit; `WEB_REQUIRED` prevents an unqualified answer, while optional retrieval degrades safely.

## Privacy, approvals, and telemetry

Private prompts do not automatically become external queries. The local minimizer produces only a public generalized query or marks the request `EXACT_APPROVAL_REQUIRED` / denied. The current implementation fails closed for that latter path: no query, fetch, or answer disclosure is sent. It never treats a broad answer approval as source-search authority.

`sourceEvent` in the Project 1 audit foundation records only bounded policy/status categories and hash correlation. It excludes query text, source text, URL payloads, credentials, and owner content. Evidence and tool/model output are always untrusted data, never instruction or authority.

## Candidate evidence

The stopped external private candidate was amended only after its gateway was confirmed stopped and GPU ownership was `OFFLINE`, with no allocation uncertainty. The private owner-only rollback records are:

- the Source-First gate amendment for the curated files and installed freeze/receipt.
- the supported `web_retrieval.max_results: 6` configuration amendment.

The required `make doctor PREFIX=/absolute/private/prefix` check passed after each amendment. The candidate remains stopped, and optional provider credentials were not probed. This is deployment/configuration evidence, not newly observed live provider behavior.

## Verification performed

- Isolated candidate setup, reversible Source-First application, and doctor check.
- Full repository `make build`, `make test`, and `make audit` regression.
- Source audit and manifest verification.
- New synthetic tests cover source-need policy, private query minimization, strict schema rejection, URL ranking, bounded search/fetch EvidencePacks, snippet-versus-fetched distinction, citation refusal, inadequate-evidence refusal, and injection-as-data behavior.

The next phase should review the branch diff and commits, run the prescribed acceptance/review process, and only perform live public-provider validation after the owner deliberately starts the candidate and has verified the configured local provider enrollment. Do not use private prompts or source material for that validation.

PROJECT 2B IMPLEMENTATION COMPLETE — SWITCH TO GPT-5.6 SOL HIGH AND RUN PROJECT 2C
