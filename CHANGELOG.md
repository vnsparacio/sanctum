# Sanctum v1.3.0 (in development)

- Correct Source-First web retrieval to use the accepted OpenClaw core fetch path instead of an invalid Firecrawl provider pin, while retaining bounded Parallel discovery and per-candidate fetch failure handling.
- Give slow local evidence-grounded answers a four-minute model deadline within ordered 270/300/310-second worker, bridge and WebUI ceilings; no retry or model fallback is added.
- Report active Open WebUI function drift in doctor so a stale imported pipe cannot silently retain obsolete approval and timeout behavior after an on-disk upgrade.
- Add a resumable `./sanctum setup` runner for the isolated prefix, pinned MLX
  and Open WebUI runtimes, local model cache, optional reviewed configuration
  proposal, hidden-input web credential enrollment and read-only Google OAuth.
- Add one-command `start`, `status`, `logs` and `stop` lifecycle operations.
  The private supervisor starts components in dependency order, verifies model,
  broker and WebUI readiness, retains per-component logs, records exact process
  identities and refuses to adopt unknown listeners or a separately managed
  gateway.
- Keep macOS privacy grants, WebUI owner/function enrollment and optional hosted
  model authentication as explicit owner checkpoints; no secret is accepted on
  the command line or written to source.

# Sanctum v1.2.0

**COMPLETE WITH DOCUMENTED LIMITATIONS.** This backward-compatible release preserves the Mac-owned authority model while adding bounded agent management, stronger repository controls and an observational Splunk integration. It does not migrate or redeploy the private owner runtime.

- Add the bounded V1.2 agent-management system: Repo Steward, Product Scout, Triage, a Symphony implementation worker and an independent PR reviewer, with external private state, exact role/model policy and explicit wall-clock, turn, token, retry, stall, output and workload limits.
- Qualify the live Linear management path. Repo Steward and Product Scout created capped, replay-deduplicated findings; Triage moved only management work; four owner-configured schedules are active. Management agents still cannot set `Ready for Agent`, add `symphony`, edit source, merge, or move work to Done.
- Add feedback-aware Symphony Rework handling and expose the reviewed implementation wall-clock timeout. Implementation still requires both owner-set execution gates, uses one isolated workspace at a time, targets `v1.2-dev`, and stops at `Human Review`.
- Add a bounded, host-owned Git control plane for deterministic issue branches, transactional commits, normal pushes, reconciliation and unmerged pull-request handoff without exposing GitHub credentials or generic Git authority to workers. The controlled documentation smoke completed issue-to-PR handoff and stopped for human review.
- Add repository hygiene and source-integrity improvements: Dependabot coverage, pinned Black and Ruff checks, decomposed CI jobs, portable path enforcement, broader documentation-link checks and explicit source-manifest verification.
- Add the Sanctum logo and reorganize current, architectural, operator, development and historical documentation without rewriting retained V1/V1.1 evidence.
- Preserve the existing metadata-only operational-event path through the private spool, S3 and Splunk Enterprise. Add optional direct Splunk Observability Cloud manual APM and bounded custom metrics, with active `trace_id`/`span_id` correlation into `sanctum_ops` records.
- Accept the owner-verified live observability canary: all six expected real spans for trace `0f820de2e8e88ce7073f975c8a0cd0c7`, matching Core correlation, secondary trace `352d01f6c841cf0d54c7a17d855fc211`, and confirmed request, model, authority, egress, duration and token metrics.

The release retains human-only implementation authorization and merge authority, implementation concurrency of one, the documented V1/V1.1 product limitations and the development-only Vitest advisory. Observability remains gateway-only, metadata-only, optional and fail-open; it cannot affect authority, routing, egress, capability, evaluation, verification or completion. Runpod/vLLM/GPU/host monitoring, collectors, dashboards, detectors, profiling, RUM, agent observability and an Observability Steward remain deferred. One historical `sanctum_ops` JSONL batch remains merged because it was indexed before the sourcetype was corrected; future ingestion uses the documented line-breaking configuration.

See [the V1.2 release-completion record](docs/history/v1.2/V1.2-RELEASE-COMPLETION.md), [agent-system handoff](docs/current/agent-system/V1.2-AGENT-SYSTEM-HANDOFF.md), [Git control plane](docs/current/agent-system/V1.2-GIT-CONTROL-PLANE.md), [Linear qualification](docs/current/agent-system/V1.2-LINEAR-LIVE-QUALIFICATION.md), [Splunk Observability guide](docs/observability/SPLUNK-O11Y-CLOUD.md) and [release limitations](docs/current/limitations.md).

# Sanctum v1.1.0

**COMPLETE WITH DOCUMENTED LIMITATIONS.** This release line is ready to tag after its release-completion pull request is merged into `v1.1-dev` and promoted under the repository's normal release process. It does not alter the immutable `v1.0.0` tag.

- Add the accepted shared-capability foundation: versioned proposal, authority, egress and result-envelope contracts with Mac-owned enforcement.
- Add bounded Source-First evidence retrieval and host-verified citations without granting remote reasoners local action authority.
- Add private Qwen Work Mode with isolated candidate workspaces, protected original-test proof, evaluator/reviewer gates, supervised private compute cleanup and an unchanged 11-case qualification.
- Replace model-authored raw Git patches with observed `worktree_edit(path, old_text, new_text)` exact replacements. The host verifies delivery-backed observations, digest freshness, unique exact matching, mutable/protected scope, canonical Git-diff correspondence and post-write state.
- Preserve no fuzzy matching, host-authored source, helper-model correction, batch editing, whole-file fallback or raw patch requirement in the normal Qwen surface.
- Record independent offline review, 10/10 applied canary-plus-suite edits, nine genuine qualification completions, two expected safety stops, and the retained operational limits in the Project 3 structured-editing report.
- Make the macOS-only amendment fixtures portable to Linux CI while retaining production refusal on non-macOS hosts; all 510 packaged tests and both GitHub Ubuntu checks passed.

See [the V1.1 release-completion record](docs/history/v1.1/V1.1-RELEASE-COMPLETION.md) and [structured editing report](docs/history/v1.1/project-3/PROJECT-3-STRUCTURED-EDITING.md) for evidence, limits and rollback requirements.

# Sanctum v1.0.0

**READY WITH DOCUMENTED EXCEPTIONS.** The feature set remains frozen. Public rename and publication are separate from production migration.

- Package the existing Mac authority boundary as sanitized source with pinned dependencies and isolated configuration/state.
- Add explicit prefix-owned MLX and Open WebUI installation; remove accidental PATH adoption of production runtimes.
- Preserve narrow local tools, exact disclosure approval, tool-free remote reasoning, budgets and fail-closed errors.
- Accommodate cold gateway startup and confirm clean shutdown.
- Disable fresh WebUI external connections, updates, search, memory, arena and automation defaults.
- Apply Apache-2.0 to Sanctum source and document external licenses and GitHub private vulnerability reporting.
- Record fresh local/hosted/WebUI application acceptance and the retained development-only Vitest advisory.

- Prevent Open WebUI browser sessions from injecting implicit built-in tools into gate requests; retain explicit-tool rejection.
- Validate actual WebUI sign-in/local arithmetic and Browser Guard navigation/approval decisions.
- Align MCP document validation with the configured private input mount, with a regression test.
- Validate isolated janitor restart and the owner-approved private GPU lifecycle through verified deletion.
- Record fresh Calendar/Gmail, synthetic file/Markdown and existing MCP acceptance.

Bounded personal-source read/generation and candidate Messages broker checks passed; autonomous browser-target selection and broad personal factual accuracy remain limited. No production migration or GitHub publication occurred. See [qualification](docs/history/v1/qualification.md).

- Publish the framework as Sanctum while preserving historical VinceAI provenance and qualified compatibility identifiers.
- Include the canonical project report and a per-occurrence rename audit.
- Reject generated Finder metadata in the publication scanner; retain the original 151-test baseline and add one scanner regression.
