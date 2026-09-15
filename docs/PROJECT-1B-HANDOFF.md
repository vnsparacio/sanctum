# Project 1B implementation handoff

## Status

Project 1B implements the accepted Project 1A shared-capability design on `v1.1/project-1-foundation`. It is source-only, additive and not deployed, merged or independently reviewed. Implementation is commit `1e30a7baa09e5821c4808512dd9f3f5fd8c06582`; the source-freeze handoff commit follows this document update.

## Delivered contracts

`gate/foundation/contracts.mjs` defines strict, versioned, model-independent records for capability proposals, authority decisions, destination-bound egress decisions, normalized result envelopes and reasoner adapters. Proposal records deliberately contain no authority or egress grant. Egress binds data class, exact service/model destination, packet/request digests, purpose, capability, scope, revision, approval state, expiry and one-use state; it has no provider-wide form.

`gate/foundation/manifest.mjs` derives a capability projection from observed owned-plugin registration, pinned adapter availability, captured schemas and runtime configuration. It records registration, declaration, schema equality, implementation source, configuration and exposure independently, reports mismatches and fails closed for any unsupported or non-exposed capability. Its policy metadata conservatively classifies egress inputs as personal even when a remote response may be public.

Reliability retains its bounded repair and provenance behavior while adding proposal validation, normalized result-envelope compatibility and a tri-state verifier: `VERIFIED`, `REJECTED`, or `UNKNOWN`. Unknown never permits a success claim. The local agent exposes an additive final-answer-only reasoner adapter; no new remote tool loop was introduced.

The gate turns an exact disclosure ticket into a destination-bound egress record and validates every bound field against current policy before retaining the existing signed-worker/ticket launch path. The Hugging Face MCP guard similarly carries an exact, approval-bound egress representation while retaining its native approval enforcement. Audit events contain only allowlisted classifications, hashes and reason codes—never prompts, arguments, results, approval tokens or raw identifiers.

## Compatibility and limits

Existing gate ticket semantics, HMAC worker envelopes and durable nonce behavior are unchanged. Existing Reliability plugin outputs retain their former shape; the new result envelope is additive. No private prefix, owner configuration, cache, OAuth enrollment, account binding, session, receipt or live evidence was read or changed.

Project 1C replaced the initial synthetic registration inference and vacuous build check with observed compiled-plugin registration and strict mismatch review. It also closed extra-field/covert-data paths in reasoner, egress, audit and MCP contracts, bound gate approval to the current destination policy, and made unknown failed execution default to `COMPLETION_UNKNOWN`. The derived review script reports only the reviewed mismatches without refreshing snapshots or enabling tools. In particular, `messages_contact_history` and `calendar_search` remain registered but unconfigured and without captured schemas; four captured, disabled core tools remain unsupported. This project does not repair or silently expose any of them.

## Validation and rollback

Project 1C reruns dependency installation, build, the complete packaged tests, source/publication audit and private-candidate doctor after the reviewed source freeze. The private candidate remains a Project 0 runtime and does not contain the Project 1 foundation; its doctor result is integrity evidence, not Project 1 deployment evidence.

Rollback is a normal Git revert of this project commit on the feature branch. The change is self-contained in the shared foundation, compatibility wrappers, tests, build review script and documentation; it has no runtime migration or data rollback.

## Project 2 reliance

Project 2 may consume only the strict manifest/proposal/decision/result interfaces. It must derive current runtime facts, preserve the fail-closed mismatch behavior, create a new exact egress decision for each destination/purpose/packet, and must not treat a schema, a reasoner output, `UNKNOWN`, or this source handoff as owner authority.

## Final source freeze

- Branch: `v1.1/project-1-foundation`
- Implementation commit: `1e30a7baa09e5821c4808512dd9f3f5fd8c06582`
- Project 1C review/source-freeze commit: this review commit
- Validation: recorded in [Project 1 acceptance](PROJECT-1-ACCEPTANCE.md)
