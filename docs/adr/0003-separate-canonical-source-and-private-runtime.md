# 0003: Separate canonical source from the owner-private runtime

- Status: Accepted
- Date: 2026-09-22
- Owners: Sanctum owner
- Related: [TTE-34](https://linear.app/ttercode/issue/TTE-34/record-adrs-for-mac-owned-authority-separate-egress-and-private)
- Supersedes: none
- Superseded by: none

## Context

Sanctum needs a reviewable, reproducible canonical repository, while an owner's
deployment necessarily contains secrets, bindings, mutable sessions, approvals
and live operational evidence. Keeping both lifecycles in one tree would risk
publishing private material, make source revisions depend on mutable local
state and turn ordinary source rollback into an unsafe runtime rollback.

The existing deployment model uses the checked-out repository as canonical
source and an external private prefix as the owner runtime. Setup renders
reviewed templates into deployment-specific files and records source-linked
integrity separately from private amendments and rollback transactions.

## Decision

The canonical Git repository contains reviewed generic source, documentation,
templates and synthetic fixtures. Owner configuration, secrets, credentials,
account/contact bindings, model caches, sessions, approvals, receipts, private
workspaces and live evidence remain in an external owner-private prefix or an
equivalent Mac-owned secret/state facility; they are never canonical source.

Source and private runtime have related identities but independent lifecycles.
A source build, release, checkout, rollback or branch change does not migrate,
overwrite, delete, reseal or repin private runtime state. Private setup,
amendment, migration, backup and rollback are explicit owner operations that
verify the matching reviewed source and preserve their own transactions and
evidence. Runtime state may record source or manifest identities for drift
detection, but those references do not make runtime contents part of Git.

Source tests use synthetic fixtures. Production values and live evidence must
not be copied into tracked files, source fixtures or diagnostics, and the
repository must not rely on symlinks into the private prefix.

## Consequences

- Benefit: the source tree can be reviewed, tested, archived and published
  without carrying owner secrets or mutable deployment history.
- Benefit: source rollback and private-state recovery remain distinct, so an
  application revision does not silently discard sessions, receipts or
  resource-ownership evidence.
- Benefit: multiple isolated deployments can use the same source while keeping
  their identities, credentials and state separate.
- Cost: operators must manage two inventories, backups and integrity chains and
  must keep their compatible identities visible during upgrades and rollback.
- Cost: deployment requires explicit setup, enrollment, amendment and migration
  steps; cloning the repository alone cannot reproduce a live owner runtime.
- Cost: partial rollback can produce source/runtime drift, so supported tooling
  must refuse mismatches and preserve private evidence for reconciliation.

## Alternatives considered

- Store encrypted or ignored runtime state inside the repository. Rejected
  because Git history, ignore mistakes, key handling and repository copies
  would still couple private and source lifecycles.
- Externalize only credentials but track configuration, receipts or live
  evidence. Rejected because those records can expose owner bindings and make
  mutable deployment state canonical.
- Automatically migrate private state on source checkout or release. Rejected
  because source operations are not owner authorization for a deployment
  mutation and may not have a safe rollback window.

## Architecture evidence

- [Configuration and secrets](../guides/configuration.md) distinguishes the
  reviewed settings template from deployment-specific rendered configuration,
  local authority material and private rollback transactions.
- [Migration and rollback](../guides/migration.md) requires a separately
  approved migration window, preserves old source and private state, and does
  not import historical sessions or approvals automatically.
- [V1.1 live baseline](../history/v1.1/V1.1-LIVE-BASELINE.md) identifies the
  canonical repository, external private prefix and legacy rollback reference,
  and records a separation scan with private configuration and receipts outside
  Git.
- [V1.2 release completion](../history/v1.2/V1.2-RELEASE-COMPLETION.md) confirms
  that owner configuration, credentials, caches, workspaces and live evidence
  remain outside the released source.
