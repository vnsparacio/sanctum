# 0002: Separate action authorization from result egress

- Status: Accepted
- Date: 2026-09-22
- Owners: Sanctum owner
- Related: [TTE-34](https://linear.app/ttercode/issue/TTE-34/record-adrs-for-mac-owned-authority-separate-egress-and-private)
- Supersedes: none
- Superseded by: none

## Context

Permission to perform an action and permission to disclose what that action
returns answer different questions. A read may be safe to execute locally yet
produce personal or restricted data that must not be sent to the requesting
reasoner. A mutation may complete while its result is withheld, truncated or
uncertain. Collapsing the two decisions would let action permission imply
disclosure, or let a disclosure failure erase the actual execution outcome.

Sanctum's capability foundation already models proposals, authority decisions,
result envelopes and egress decisions as distinct records. Work Mode evaluates
authority before invocation and result egress after the execution outcome has
been normalized.

## Decision

Action authorization and result egress are separate Mac-owned decisions and
must remain independently enforceable.

Action authorization binds the exact proposal and relevant capability, policy,
scope, revision, arguments and effect. It determines whether execution may
start. Result egress is evaluated separately after execution against the exact
result packet or envelope and its digest, data classes, destination/model,
purpose, scope, revision, expiry and one-use state. An action authorization is
never an egress grant, and an egress decision can never authorize an action.

Before a result becomes an observation for another reasoner turn or is sent to
any destination, the matching egress decision must allow that exact transfer.
A denied or unavailable egress decision withholds the result but preserves the
truth of the recorded execution state, including completion uncertainty.

## Consequences

- Benefit: least-privilege execution does not become accidental disclosure.
- Benefit: the same capability can use destination- and purpose-specific
  disclosure policy without changing its execution authority.
- Benefit: audit records can distinguish what was allowed to run, what
  actually happened and what was allowed to leave the local boundary.
- Cost: each action needs two policy checkpoints, additional bindings and
  replay/expiry handling, increasing implementation and test complexity.
- Cost: a useful result may be withheld even after an action consumes time,
  money or mutates state; operators must reconcile the real action outcome
  without treating missing disclosure as non-execution.
- Cost: pipelines must retain normalized results and execution certainty long
  enough to make and audit egress decisions without leaking the payload.

## Alternatives considered

- Let action approval implicitly approve its result. Rejected because result
  sensitivity and destination may be unknown until after execution.
- Decide action and egress in one compound model response. Rejected because it
  gives untrusted reasoning control over both boundaries and obscures partial
  outcomes.
- Treat egress denial as action failure. Rejected because it falsifies mutation
  and completion state and can cause unsafe retries.

## Architecture evidence

- [Architecture](../architecture/architecture.md) defines capability proposals
  with no authority or egress grant and separate exact Mac-owned records for
  authority and egress.
- [Foundation contracts](../../gate/foundation/contracts.mjs) validate
  authority and egress with different schemas and match egress decisions to an
  exact claim.
- [Work Mode coordinator](../../gate/plugin/work-mode.mjs) authorizes before
  invocation, normalizes execution results and then makes a distinct result
  egress decision before returning observations to the reasoner.
- [Configuration guide](../guides/configuration.md) records that even a bounded
  audit session grant leaves each message subject to an exact egress decision.
