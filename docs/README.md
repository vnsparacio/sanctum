# Sanctum documentation

Current contributor and operator material is organized by purpose:

- [`architecture/`](architecture/) defines the current authority, privacy, capability, container and compatibility boundaries.
- [`adr/`](adr/) records durable architectural decisions, their rationale and supersession history. Start with the [ADR guide](adr/README.md) and [template](adr/TEMPLATE.md).
- [`guides/`](guides/) contains setup, configuration, operations, troubleshooting, release and migration procedures. The [Linear agent integration guide](guides/linear-agent-integration.md) reproduces the current V1.3 metadata and bounded management-agent setup.
- [`development/`](development/) covers testing, dependency review, publication scope and the [secret-detection controls](development/secret-scanning.md). Start with the [testing guide](development/testing.md).
- [`observability/`](observability/) documents the bounded Splunk application tracing and custom-metrics slice.
- [`current/`](current/) records stable V1.2 limitations, the V1.3 roadmap and the accepted agent-management system.
- [`history/`](history/) retains design history, lessons, benchmarks and versioned project evidence.

The stable release record is [Sanctum V1.2.0 release completion](history/v1.2/V1.2-RELEASE-COMPLETION.md). V1.3 begins with the [development bootstrap](current/agent-system/V1.3-DEVELOPMENT-BOOTSTRAP.md). Accepted V1.2 component evidence remains in the [agent-system handoff](current/agent-system/V1.2-AGENT-SYSTEM-HANDOFF.md), [Linear live qualification](current/agent-system/V1.2-LINEAR-LIVE-QUALIFICATION.md), [Git control plane](current/agent-system/V1.2-GIT-CONTROL-PLANE.md) and [Splunk Observability guide](observability/SPLUNK-O11Y-CLOUD.md).

Historical reports intentionally preserve failed qualifications, intermediate repairs and superseded handoffs. They are evidence, not current operating instructions. For V1.1 status, the [V1.1 release completion](history/v1.1/V1.1-RELEASE-COMPLETION.md) and the final [Project 3 structured-editing acceptance](history/v1.1/project-3/PROJECT-3-STRUCTURED-EDITING.md) supersede earlier Project 3 status reports.
