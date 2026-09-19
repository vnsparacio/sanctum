# Testing and engineering checks

All default checks are synthetic, offline and credential-free. Install the pinned runtime and development dependencies with:

```sh
make deps
```

Black is the authoritative Python formatter and Ruff is the linter:

```sh
make format        # apply Black
make format-check  # verify formatting without changes
make lint          # Ruff checks
```

The complete regression suite remains `make test`. Its 562 baseline tests are preserved in seven independently runnable groups:

| Local command | Surface | Baseline tests |
| --- | --- | ---: |
| `make test-gate-js` | Gate authority, Source-First, Work Mode and protocol contracts in Node | 126 |
| `make test-gate-python` | Gate policy, lifecycle, protected-test, provider and workspace contracts in Python | 295 |
| `make test-reliability` | Capability, egress, verifier, utility and source-grounding contracts | 42 |
| `make test-mcp` | MCP containment and approval guard | 8 |
| `make test-plugins` | Owned TypeScript plugin contracts | 11 |
| `make test-release` | Setup, amendment, rollback and Linux/macOS portability | 28 |
| `make test-agents` | V1.2 management, budgets, supervision and execution gates | 52 |

`make test-gate` combines the two gate groups. No test was removed when the runner was decomposed; the old workflow's duplicate second execution of `tests.test_agent_system` was removed.

GitHub Actions exposes independent `Python format`, `Python lint`, `Plugin build and manifests`, each contract group, and `Publication, source integrity, and compose` checks. Pull requests run without secrets. Push checks run only on integration/release branches so an open pull request is not validated twice for the same feature-branch push. Dependency caches are keyed by the committed npm and Python requirement files.

`make build` compiles and validates owned plugins, checks the reviewed OpenClaw runtime pins, and verifies the capability manifest. Test groups and source verification that consume those generated outputs rebuild them only when they are missing or drifted. CI builds them once and passes the validated artifact to dependent jobs. `make audit` scans source for selected credential/private-artifact patterns and validates repository Markdown links without printing matched values. `make verify-source` validates the explicit `SOURCE-MANIFEST.json` freeze and runtime pins. `docker compose config --quiet` checks the optional container definition.

Dependabot checks the committed root and optional-web npm lockfiles, root/runtime/host pip requirements, and GitHub Actions each week. Updates target `v1.2-dev`; compatible non-major updates are grouped only where that keeps review diagnostic, and automatic merge is not enabled.

Live UI enrollment, MLX inference, personal-source semantics, provider policy, GPU cleanup and answer-quality qualification remain manual/macOS/private-runtime checks. Passing offline CI does not establish live-provider acceptance or grant authority.
