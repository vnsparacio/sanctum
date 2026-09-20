# Roadmap

Sanctum V1.2.0 release scope is frozen. Release completion, review, promotion to `main`, immutable tagging and GitHub publication are administrative gates; they do not authorize new features, private-runtime migration or deployment changes.

After release, operate the bounded V1.2 agent-management system at implementation concurrency one and collect content-free evidence from actual failures. Preserve owner-only `Ready for Agent` plus `symphony` authorization, Human Review, merge and Done transitions. Any broader implementation concurrency, new management authority or automated merge path requires a separate reviewed design.

Continue the existing metadata-only Core event path and the gateway-only Splunk APM/custom-metric slice. Runpod/vLLM/GPU/host monitoring, collectors, dashboards, detectors, profiling, RUM, agent observability and an Observability Steward remain deferred. Observability may not become an authority, routing, egress, capability, evaluator, verifier or completion input.

Product work remains evidence-driven: improve local-model browser-target selection, factual-quality evaluation, retrieval, durable jobs, approval ergonomics and cold-start behavior only when concrete failures justify a bounded project. Evaluate a supported Vitest major deliberately rather than forcing an incompatible override.

Communication/calendar writes, batch filesystem authority, new MCP integrations, higher-memory local visual models, a home inference server and a separately designed remote-planner/local-executor protocol remain future possibilities. Generic shell, remote direct Mac control, automatic privacy declassification, broad deletion and standing approval are not roadmap shortcuts. A full history/undo migration importer, unattended production cutover and an all-container deployment also remain unsupported.
