# Sanctum documentation

Current contributor and operator material is organized by purpose:

- [`architecture/`](architecture/) defines the current authority, privacy, capability, container and compatibility boundaries.
- [`adr/`](adr/) records durable architectural decisions, their rationale and supersession history. Start with the [ADR guide](adr/README.md) and [template](adr/TEMPLATE.md).
- [`guides/`](guides/) starts with the [end-to-end quickstart](guides/quickstart.md), then covers detailed installation/upgrades, configuration, operations, troubleshooting, release and migration procedures. The [interactive Qwen Code guide](guides/qwen-code.md) describes direct Mac coding with demand-started private Runpod inference. The [local 4B prompting guide](guides/local-4b-grounded-prompts.md) explains how to ask checkable public questions and interpret grounding failures. The [Linear agent integration guide](guides/linear-agent-integration.md) reproduces the current V1.3 metadata and bounded management-agent setup.
- [`development/`](development/) covers testing, dependency review, publication scope and the [secret-detection controls](development/secret-scanning.md). Start with the [testing guide](development/testing.md).
- [`observability/`](observability/) documents the bounded Splunk application tracing/custom-metrics slice, the restricted content contract, and the reviewable Splunk Core content app/runbook.
- [`current/`](current/) records V1.3 source limitations, the roadmap and the accepted agent-management system.
- [`history/`](history/) retains design history, lessons, benchmarks and versioned project evidence.

The [V1.3 release-completion record](history/v1.3/V1.3-RELEASE-COMPLETION.md)
tracks the source candidate and owner promotion gates. The preceding immutable
release record is [V1.2.0](history/v1.2/V1.2-RELEASE-COMPLETION.md). V1.3 began
with the [development bootstrap](current/agent-system/V1.3-DEVELOPMENT-BOOTSTRAP.md);
the [Qwen lifecycle qualification](current/agent-system/V1.3-QWEN-LIFECYCLE-QUALIFICATION.md)
records one owner-gated non-Sanctum Work Mode implementation, and the
[Codex AO correlation guide](current/agent-system/V1.3-CODEX-AO-CORRELATION.md)
records the local development telemetry lane. The
[workflow reliability guide](current/agent-system/V1.3-WORKFLOW-RELIABILITY.md)
explains host dependency preflight and bounded agent execution. Accepted V1.2
component evidence remains in the [agent-system handoff](current/agent-system/V1.2-AGENT-SYSTEM-HANDOFF.md),
[Linear live qualification](current/agent-system/V1.2-LINEAR-LIVE-QUALIFICATION.md),
[Git control plane](current/agent-system/V1.2-GIT-CONTROL-PLANE.md) and
[Splunk Observability guide](observability/SPLUNK-O11Y-CLOUD.md).

The [guided MoodLog POC milestone](history/v1.3/WORK-MODE-MOODLOG-MILESTONE.md)
records browser-functional partial acceptance and its limits; the
[completion runbook](development/WORK-MODE-MOODLOG-ACCEPTANCE.md) defines the next
protected persistence and browser checks.

Historical reports intentionally preserve failed qualifications, intermediate repairs and superseded handoffs. They are evidence, not current operating instructions. For V1.1 status, the [V1.1 release completion](history/v1.1/V1.1-RELEASE-COMPLETION.md) and the final [Project 3 structured-editing acceptance](history/v1.1/project-3/PROJECT-3-STRUCTURED-EDITING.md) supersede earlier Project 3 status reports.
