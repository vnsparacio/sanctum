# 0001: Keep authority on the owner Mac

- Status: Accepted
- Date: 2026-09-22
- Owners: Sanctum owner
- Related: [TTE-34](https://linear.app/ttercode/issue/TTE-34/record-adrs-for-mac-owned-authority-separate-egress-and-private)
- Supersedes: none
- Superseded by: none

## Context

Sanctum can use local, private-compute and hosted reasoners with different
quality, availability and privacy characteristics. A reasoner's output can be
useful without being a trustworthy source of permissions. Repository, web,
tool and model content can also contain instructions that were not authorized
by the owner. If any of those inputs could authenticate a request, lower a
privacy floor, approve disclosure, invoke a capability or claim resource
ownership, changing reasoners would also change the trust boundary.

Current architecture already separates those roles: models receive bounded
packets and make proposals, while authenticated host components validate
requests, compose policy, enforce approvals and own resource lifecycle state.

## Decision

Reasoning is replaceable; authority stays on the owner Mac.

Authentication, risk composition, privacy floors, disclosure approval, local
tool permissions, provider budgets and compute-resource ownership are decided
by Mac-owned components using owner-controlled configuration and state.
Reasoners may classify, recommend, propose structured actions or evaluate
evidence, but their identity, provider, output or confidence never grants
authority. Content supplied by repositories, tools or external sources is data
under the same rule.

Every reasoner integration must therefore fit behind host-owned contracts and
fail closed when required authority is absent or invalid. Substituting a model,
provider or transport must not require transferring the authority role, and a
reasoner failure must not silently authorize a fallback.

## Consequences

- Benefit: models and providers can be replaced or removed without redefining
  the security boundary.
- Benefit: prompt injection, model compromise and provider failure are bounded
  to proposals or answers rather than becoming permissions.
- Benefit: owner approvals, budgets and resource ownership remain attributable
  to locally controlled records that can be audited and revoked.
- Cost: the Mac must maintain deterministic policy, authentication, approval,
  nonce, lifecycle and audit machinery in addition to reasoner adapters.
- Cost: unavailable or inconsistent local authority state reduces liveness;
  remote reasoning cannot bypass it to keep a task moving.
- Cost: every new capability and reasoner path needs explicit host contracts,
  bounded inputs and tests proving that model-controlled fields have no
  authority.

## Alternatives considered

- Trust a designated model or provider to authorize actions. Rejected because
  model behavior and provider availability are not stable security controls.
- Let each integration enforce its own permissions. Rejected because policy
  would fragment and changing an adapter could silently change authority.
- Treat model refusal as the primary safety boundary. Rejected because refusal
  is useful defense in depth, not deterministic authorization evidence.

## Architecture evidence

- [Architecture](../architecture/architecture.md) assigns authentication,
  privacy, disclosure, permissions, budgets and GPU ownership to the Mac and
  describes reasoners as proposal-only.
- [Authority implementation](../../gate/src/authority.py) validates
  purpose-bound signed requests and one-use nonces supplied by the
  authenticated Mac gate.
- [Reasoner transports](../../gate/src/backends.py) define tool-free reasoning
  roles and state that supplied evidence grants no action authority.
- [V1.2 release completion](../history/v1.2/V1.2-RELEASE-COMPLETION.md) records
  the same invariant across the accepted management and implementation planes.
