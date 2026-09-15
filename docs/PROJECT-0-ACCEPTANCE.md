# Project 0 independent acceptance

Project 0 establishes Sanctum as the V1.1 development source and proves that its clean source package can instantiate the owner's isolated private VinceAI candidate. Project 0C reviewed every change from qualified V1, attacked the migration claims, repeated the source pipeline, checked live bounded evidence, normalized the branches and left merge authority with the reviewer.

## Change classification

| File | Classification | Review conclusion |
|---|---|---|
| `AGENTS.md` | `VALID_PROJECT_0_DOCUMENTATION` | Defines source, authority, privacy, validation and branch workflow. |
| `SOURCE-MANIFEST.json` | `VALID_PROJECT_0_FIX` | Freezes reviewed source additions and changes; no runtime pin was silently changed. |
| `docs/V1.1-LIVE-BASELINE.md` | `VALID_PROJECT_0_DOCUMENTATION` | Records qualified baseline, bounded acceptance, limitations, workflow and rollback. |
| `docs/PROJECT-0-ACCEPTANCE.md` | `VALID_PROJECT_0_DOCUMENTATION` | Preserves this independent classification and PR review summary. |
| `docs/configuration.md` | `VALID_PROJECT_0_DOCUMENTATION` | Documents supported private notes, web and MCP setup. |
| `gate/src/backends.py` | `VALID_PROJECT_0_FIX` | Makes private-80B inference use the validated configured tunnel port. |
| `gate/src/runpod.py` | `VALID_PROJECT_0_FIX` | Makes the SSH tunnel use the same validated port and rejects invalid ports. |
| `gate/tests/test_runtime.py` | `VALID_PROJECT_0_FIX` | Regresses backend/tunnel alignment and invalid-port refusal. |
| `host/web-runtime/package.json` | `VALID_PROJECT_0_MIGRATION_TOOLING` | Declares only the intended pinned optional web dependencies. |
| `host/web-runtime/package-lock.json` | `VALID_PROJECT_0_MIGRATION_TOOLING` | Locks package versions and archive integrity for reproducible bootstrap. |
| `scripts/audit.py` | `VALID_PROJECT_0_FIX` | Tightens the example-home pattern and narrowly permits requested public location declarations. |
| `scripts/bootstrap.py` | `VALID_PROJECT_0_MIGRATION_TOOLING` | Installs the isolated optional web runtime without duplicating the core OpenClaw tree. |
| `scripts/component.py` | `VALID_PROJECT_0_MIGRATION_TOOLING` | Honors a validated private notes destination while retaining the safe default. |
| `scripts/configure.py` | `VALID_PROJECT_0_MIGRATION_TOOLING` | Adds rollback-protected notes, web, MCP and GPU-port amendments with bounded schemas. |
| `scripts/mcp_gateway.py` | `VALID_PROJECT_0_MIGRATION_TOOLING` | Verifies a unique three-tool MCP profile and applies resource/network restrictions. |
| `scripts/operator.py` | `VALID_PROJECT_0_FIX` | Gives the independent GPU janitor the explicit local identity needed for Keychain access. |
| `tests/test_release.py` | `VALID_PROJECT_0_FIX` | Tests publication exceptions, private amendments, refusal paths, rollback and MCP authority drift. |

No change was classified `OUT_OF_SCOPE`, `PRIVATE_DATA_RISK`, or `UNKNOWN_REQUIRES_REVIEW`. The diff does not implement Source-First Web Answering, general private-80B tool parity, Work Mode, learned semantic routing, SkyPilot or a broad refactor.

## Independent evidence

- Git ancestry is a straight three-commit Project 0 sequence from qualified V1 commit `83a1edf02c097e75915bd1c4f233963fe26388b7`. Before normalization the remote had only `main` at that V1 commit; all Project 0 commits were local and reachable, with no unrelated commit at risk.
- A fresh `git archive` contained no Git metadata or private runtime. From that archive, dependency bootstrap, canonical build, all 158 packaged tests, source audit, fresh setup and doctor passed. The dependency review still reports two documented moderate development advisories; no upgrade was used to hide them.
- The audit scanned 183 pre-review source files with zero issues. A second scan compared actual candidate tokens, authority material, account/contact/root/resource bindings and provider credentials against all tracked source without exposing their values; it found no matches.
- The private candidate passes doctor, local Qwen and WebUI health. All five read-only/local brokers answer their health endpoint. Existing receipts cover the actual calculator path, owner saved-chat gate, replay refusal, bounded public web, Browser Guard, personal read-only sources, File Steward, Markdown, MCP and hosted adapters without retaining personal payloads in source evidence.
- Provider authentication was independently exercised. The provider reported zero Pods; the configured persistent volume exists in the expected datacenter and retains the required size. GPU autostart is false. The accepted single private-80B receipt records invalid-signature rejection, the expected answer, managed close, provider-confirmed zero compute and preserved storage. Expensive inference was not repeated.
- The private prefix contains no model-weight copy. Temporary MCP containers and the GPU tunnel/test browser were absent at the Project 0B handoff. Legacy source/configuration was not copied wholesale; the legacy runtime remains available. Its retained cleanup process continues to write only its two offline lifecycle state files, which is documented rather than represented as an immutable tree.

## Bounded live result and limitations

The candidate reproduces the intended V1 paths within the tested boundary. Direct 4B and explicit calculator work passed, while two unassisted gateway arithmetic probes were wrong. The frontier adapter had one unexplained provider answer failure followed by a successful bounded diagnostic; provider permissions and fallback behavior remain unchanged. Model, WebUI and personal brokers still need manual supervision, Messages depends on the owner-authorized Terminal, logout/reboot cutover is unqualified, and existing browser-target/draft-format limitations remain.

The native approval runtime and native MCP clients exercised their actual guards, but acceptance does not claim a full model-driven conversation through every integration or an interactive WebUI private-80B turn. Public fetch used the normal readability path; the paid Firecrawl fallback was not forced solely for proof.

## Rollback and merge boundary

The private-80B lifecycle must be stopped through managed cleanup with provider-side zero ownership confirmed; persistent storage and receipts are retained. Stop only identity-verified candidate processes. Configuration rollback uses the matching private amendment transaction with the gateway stopped. Legacy source, configuration and services remain the rollback path.

The Project 0 feature branch targets `v1.1-dev`. Reviewers may merge the pull request after normal review; this task does not merge it. Stable `main` remains untouched. Project 1 must begin only after this PR is merged and from the resulting updated `v1.1-dev`.
