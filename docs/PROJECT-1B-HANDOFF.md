# Project 1B implementation handoff

## Status

Project 1B implements the accepted Project 1A shared-capability design on `v1.1/project-1-foundation`. It is source-only, additive and not deployed, merged or independently reviewed. Implementation is commit `1e30a7baa09e5821c4808512dd9f3f5fd8c06582`; the source-freeze handoff commit follows this document update.

## Delivered contracts

`gate/foundation/contracts.mjs` defines strict, versioned, model-independent records for capability proposals, authority decisions, destination-bound egress decisions, normalized result envelopes and reasoner adapters. Proposal records deliberately contain no authority or egress grant. Egress binds data class, exact service/model destination, packet/request digests, purpose, capability, scope, revision, approval state, expiry and one-use state; it has no provider-wide form.

`gate/foundation/manifest.mjs` derives a capability projection from captured schemas, declared tools and runtime configuration. It records declaration, capture and exposure independently, reports declaration/schema mismatches and fails closed for any non-exposed capability. Its policy metadata conservatively classifies egress inputs as personal even when a remote response may be public.

Reliability retains its bounded repair and provenance behavior while adding proposal validation, normalized result-envelope compatibility and a tri-state verifier: `VERIFIED`, `REJECTED`, or `UNKNOWN`. Unknown never permits a success claim. The local agent exposes an additive final-answer-only reasoner adapter; no new remote tool loop was introduced.

The gate turns an exact disclosure ticket into a destination-bound egress record and validates that record before retaining the existing signed-worker/ticket launch path. The Hugging Face MCP guard similarly carries an exact, approval-bound egress representation while retaining its native approval enforcement. Audit events contain only bounded classifications, hashes and reason codes—never prompts, arguments, results, approval tokens or raw identifiers.

## Compatibility and limits

Existing gate ticket semantics, HMAC worker envelopes and durable nonce behavior are unchanged. Existing Reliability plugin outputs retain their former shape; the new result envelope is additive. No private prefix, owner configuration, cache, OAuth enrollment, account binding, session, receipt or live evidence was read or changed.

The derived review script reports known declared/schema mismatches without refreshing snapshots or enabling tools. In particular, `messages_contact_history` and `calendar_search` remain unconfigured and without captured schemas. This project does not repair or silently expose either one.

## Validation and rollback

The existing dependency environment was checked before its explicit supported recreation. Dependency installation and the build passed. The first complete test run correctly stopped at the source-drift guard, because this project had not yet updated the source manifest. After its reviewed update, the complete synthetic suite passed 166 checks and the source audit scanned 191 files with no issues. No live deployment, gateway amendment or private-prefix doctor run is needed because this project changes neither runtime configuration nor a supported installed candidate.

Rollback is a normal Git revert of this project commit on the feature branch. The change is self-contained in the shared foundation, compatibility wrappers, tests, build review script and documentation; it has no runtime migration or data rollback.

## Project 2 reliance

Project 2 may consume only the strict manifest/proposal/decision/result interfaces. It must derive current runtime facts, preserve the fail-closed mismatch behavior, create a new exact egress decision for each destination/purpose/packet, and must not treat a schema, a reasoner output, `UNKNOWN`, or this source handoff as owner authority.

## Final source freeze

- Branch: `v1.1/project-1-foundation`
- Implementation commit: `1e30a7baa09e5821c4808512dd9f3f5fd8c06582`
- Handoff/source-freeze commit: this handoff commit
- Validation: `make deps`, `make build`, `make test` (166 passing checks) and `make audit` (191 files, no issues) passed; `git diff --check` passed
