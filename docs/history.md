# Design history and decisions

The original plan centered on a Mac Qwen 4B agent, an AWS 30B private tier, later 235B and eventually a home server. The durable idea was local authority with replaceable inference.

Real model/tool work forced a smaller OpenClaw surface and conservative 16K context/cache choices. Personal integrations became narrow socket brokers and read-only wrappers. Browser Guard and File Steward enforced controls that prompting alone could not express safely.

Benchmarks weakened the case for a general text 30B middle tier. 80B became the structured private worker; 235B remained selective stronger reasoning. AWS capacity delayed the build and Runpod became the production private tier. AWS remains historical/optional rather than missing V1 infrastructure.

Learned router experiments generalized poorly on fresh grouped evaluation. The production design kept audit signals separate from deterministic authorization. A gate initially called bare MLX; the local-agent correction restored OpenClaw's tool loop. Source grounding then distinguished receipt/sent/modified metadata from content facts.

Phase 10 added automatic GPU leases/reconciliation, stronger hosted/visual/frontier paths and local snapshot disclosure. V1 packaging now separates machine-specific installation from distributable source. It intentionally preserves failed approaches and remaining limits instead of portraying a linear success story.
