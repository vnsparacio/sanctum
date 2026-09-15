# Sanctum development

Reasoning is replaceable. Authority stays on the Mac.

- Work from this repository and the canonical remote documented in docs/V1.1-LIVE-BASELINE.md. Develop on v1.1-dev; preserve the V1 tag and history. Do not push without an explicit request.
- The legacy hybrid-ai tree is read-only reference and rollback evidence. Never modify or repin it during V1.1 work.
- Keep owner configuration, secrets, account/contact bindings, model caches, sessions, approvals, receipts and live evidence in an external private prefix. Use synthetic fixtures in source/tests.
- Read docs/architecture.md, docs/configuration.md, docs/migration.md and docs/V1.1-LIVE-BASELINE.md before deployment changes.
- Validate with make deps, make build, make test, make audit; run make doctor PREFIX=/absolute/private/prefix after setup or supported amendments. An existing dependency venv must be inspected before recreating it.
- Use scripts/configure.py for supported amendments while the candidate gateway is stopped. Never refresh hashes to hide drift. Intentional source changes require review, tests, an explanation and an explicit new source freeze; runtime pins remain separately reviewed.
- Reuse cached Qwen weights through cache-only startup. Do not run competing heavy model servers on a memory-constrained Mac.
- Keep GPU autostart off until the independent janitor and private resource references are validated. Confirm managed allocation/lease cleanup before stopping supervision; preserve persistent volumes.
- Stop at actual owner OAuth, UI enrollment or macOS permission checkpoints and provide the exact local action. Never request secrets in chat. Distinguish historical qualification, automated contracts and newly observed live behavior.
- Project 0B is not complete until the pending acceptance gates in the baseline document pass. Do not begin Project 1.
