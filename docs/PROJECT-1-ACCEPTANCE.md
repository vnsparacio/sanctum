# Project 1 independent acceptance

## Classification

Project 1 is accepted on `v1.1/project-1-foundation` for review into `v1.1-dev`. It began exactly at accepted integration commit `252e5ac15bd4a30218b33466957e6f23d5ffbda2`. Stable `main` and the peeled `v1.0.0` tag remain at `83a1edf02c097e75915bd1c4f233963fe26388b7`. The branch contains only the Project 1 design, shared foundation, compatibility wiring, tests and documentation. No Project 2 Source-First or Project 3 private-agent behavior is present.

## Independent findings and corrections

Project 1B's summary was not accepted as evidence. Direct inspection found four material defects: runtime registration was inferred from the schema validator set; the build-time manifest check was vacuous; egress matching omitted capability digest/data-class and accepted extra claim fields; and reasoner/audit records allowed undeclared fields or unsafe labels. The initial MCP Hugging Face guard also allowed schema-unknown fields to reach the approval boundary.

Project 1C corrected those defects. The build now loads each compiled Sanctum plugin, observes its registered definitions, compares them with generated declarations and captured schemas, and permits only six explicit existing mismatch records. Runtime exposure additionally requires an available implementation, a captured matching schema, supported Mac policy and current allowlisting. Reasoner results, decisions, egress claims and audit records use exact keys; egress compares request, packet, capability, capability digest, data classes, scope, revision, purpose and current destination. MCP search uses a strict local argument allowlist before approval.

## Falsification results

The review traced proposals through the Reliability hook, native approvals, gate tickets, signed worker authority, brokers and result normalization. Models and all retrieved/tool/repository content remain data: they may propose arguments but cannot introduce a decision field or a new capability. Tool authority and data egress remain distinct. Gate approvals remain one-use, revision/packet/expiry bound and now also fail if destination policy changes after ticket creation. Worker HMAC, durable nonce, provider identity, budget and private-80B lifecycle code is unchanged.

Safe repair remains a single pre-execution allowlisted pass, revalidated against the actual captured schema. It cannot add paths, roots, accounts, recipients, identifiers or permissions, and consequential tools remain non-repairable. Backend exceptions become bounded failures and are not replayed. Failed execution at the shared compatibility boundary defaults to `COMPLETION_UNKNOWN` unless a caller has stronger evidence.

Result normalization continues to preserve source, provenance, untrusted state, metadata/content distinctions, truncation and media separation. The only verifier outputs are `VERIFIED`, `REJECTED` and `UNKNOWN`; only deterministic calculator/unit/date evidence can produce verified or rejected, and unknown causes neither success recording nor fallback revision. No model confidence is used.

Fresh adversarial coverage rejects unadvertised capabilities, self-authored authority, retrieved-policy fields, approval reuse, changed destinations/purposes/data classes, weak digests, extra covert fields, malformed/duplicate/drifted schemas, unsafe repair, UNKNOWN-as-success, audit payloads, oversized envelopes, MCP argument smuggling and filesystem/symlink escape.

## Compatibility and overengineering review

The implementation adds no framework or dependency and makes no broad refactor. Existing names, broker protocols, native approvals, source normalization, 4B OpenClaw tool loop, Browser Guard, personal-source restrictions, File Steward/Markdown scope, curated MCP transport and GPU lifecycle remain in place. The authority record, typed result view and reasoner adapter are small future-facing seams not yet universal consumers; they are retained because Projects 2/3 and future local reasoners need one model-neutral contract. The local adapter has an equivalence test. Remote final-answer Python transports retain their existing strict validators and do not yet gain tools.

## Validation

The inspected dependency environment was healthy before supported recreation. `make deps`, `make build`, and all 173 packaged tests passed. `make audit` scanned 192 source/publication files with no issues; `git diff --check`, the Compose configuration check and the production-dependency audit passed. The private-candidate doctor reported source, runtime-pin and configuration integrity passing; that candidate was also confirmed to lack the Project 1 foundation directory, as expected for an undeployed source branch. The GitHub Actions workflow runs the same offline build/test/audit contract on push and pull requests without weakened checks.

## Known limits

- The existing private candidate is still the accepted Project 0 runtime. Its Project 1 foundation directory is absent. Doctor verifies current source, pinned dependencies and that candidate's own receipt; it does not claim Project 1 is deployed.
- `messages_contact_history` and `calendar_search` are registered but deliberately unconfigured and lack captured schemas. They remain non-exposed. Captured `read`, `session_status`, `memory_search` and `memory_get` are deliberately unsupported.
- Compiled owned-plugin schemas are observed at build time. Core browser/web/MCP schemas remain reviewed, pinned adapter captures rather than live private-runtime introspection.
- Shared exact egress is enforced for gate disclosure tickets and represented alongside native Hugging Face approval. Browser, configured web providers and read-only account brokers retain their existing native/configuration/broker boundaries; Project 1 does not silently impose a new per-call policy.
- Only the existing local 4B path has a shared reasoner compatibility adapter. Current remote transports remain final-answer-only and tool-free. Project 3 must add private reasoner tool proposals through these contracts, not around them.
- Project 0's documented development-only dependency advisory remains. Production dependencies have no known audit finding in this review.

## Rollback and next project

Rollback is a normal revert of the Project 1C review commit followed by the Project 1B implementation/design commits. There is no private-state migration, provider repin or data rollback. Preserve the external candidate and legacy rollback evidence.

After this branch is merged into `v1.1-dev`, start Project 2 only on a new `v1.1/project-2-*` branch from the updated integration head and only under a separate request. Project 2 may rely on exact proposal/decision/egress/result contracts, observed registration/schema drift checks, tri-state verification and existing native authority boundaries. It must not treat the manifest or source content as authority.
