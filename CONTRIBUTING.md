# Contributing

Read the architecture and security documents before changing capability boundaries. V1 packaging must not become a feature or dependency-upgrade project.

Use a fresh checkout and run `make deps format-check lint build test audit verify-source`. EditorConfig-aware editors use [`.editorconfig`](.editorconfig) for baseline text-file conventions; Black and Ruff remain authoritative for Python formatting and linting. Use `make format` to apply Black. The individual test commands and their matching CI checks are listed in [the testing guide](docs/development/testing.md). Build uses temporary OpenClaw state. Tool plugins use OpenClaw's generated metadata process; hook plugins compile with TypeScript and validate their exported registration entry. Do not run a hook plugin through the tool-only metadata generator.

Keep tests credential-free. Use fake providers for allocation ambiguity, cleanup, budget and approval tests. Put real service tests behind explicit operator setup; never read a contributor's personal sources from CI.

Use synthetic names/accounts/documents. Preserve failed tests and distinguish software contracts, hosted-provider availability, UI transport and answer quality.

Every pull request must contain exactly one `## Documentation impact` section. Use `Updated: <summary>` when the PR changes `README.md` or a file beneath `docs/`. Behavior or configuration changes must include those documentation changes unless the section instead contains `None: <specific justification>` explaining why user-visible behavior, setup, operation and configuration are unchanged. Placeholder answers such as `N/A` fail CI. Keep feature guides current when behavior lands; update the release-facing README when a public workflow, capability or limitation changes.

`SOURCE-MANIFEST.json` and runtime pins are reviewed release artifacts. Intentional source changes require review, tests, a recorded explanation and an explicit new freeze. Setup/build must never refresh trust automatically. Do not commit generated dependencies, compiled output, `.local`, auth stores, model weights or private evidence.

Sanctum source uses Apache-2.0. Use GitHub private vulnerability reporting/Security Advisories as described in SECURITY.md. External dependency licenses remain separate.
