# Testing and evidence

Default tests are synthetic and credential-free. `make test` covers the gate's Python/Node policy and lifecycle contracts, signed worker replay, media preparation, installer rollback boundaries, reliability validation/utilities/source semantics, capability contracts/manifest/egress/verifier semantics, MCP policy, plugin fixtures and new isolated setup boundaries.

Historical installer tests now use synthetic prior-function bodies in temporary databases. They exercise compare-before-write and rollback semantics without requiring an earlier installed release. The historical upgrade adapter is disabled as a public command; new setup does not invoke it.

`make build` uses temporary OpenClaw state. Tool plugins run the canonical build/validate chain. Hook plugins compile and validate the registration export. Expected OpenClaw artifact hashes remain pinned to the verified version. Generated candidate plugin hashes reflect reviewed path/contact changes.

`make audit` scans source for selected credential/private-artifact patterns and broken documentation links without printing matched secret values. It complements manual review; it is not proof that arbitrary private data can never appear. `docker compose config --quiet` checks the optional container definition.

Public CI uses no secrets and no live Gmail/Messages/Calendar/provider calls. Linux workflow configuration is supplied, but a hosted CI run is not implied until actually executed. Fresh-copy tests must exclude node_modules, venvs, state and the owner's config; see acceptance for exactly what was exercised.

Keep live UI, MLX inference, optional source semantics, provider-policy checks, GPU cleanup and answer-quality evaluation separate from unit tests. A passing suite does not establish a safe provider retention contract or universal correctness.

## Release qualification

The Project 0 accepted suite contains 160 tests. Project 1B adds six capability-foundation contracts: runtime projection/mismatch detection, proposal authority exclusion, exact egress scope, tri-state verification, result/audit envelopes and reasoner-adapter boundaries. Final executed counts and live evidence are recorded in [acceptance](acceptance.md). The [dependency exception](dependency-review.md) concerns Node test tooling only. Keep private test credentials, approval IDs, raw account data and runtime state out of source and CI.
