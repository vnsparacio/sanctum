# Sanctum V1.0.0 publication qualification

**READY WITH DOCUMENTED EXCEPTIONS** remains the functional V1 disposition. The [canonical project report](SANCTUM-V1-PROJECT-REPORT.md) is included unchanged and linked from the README. It records the original 174-file, 151-test qualification snapshot; the renamed distribution contains 178 allowlisted source files.

## Rename scope

Public text, package metadata and artifacts use Sanctum. New generated janitor labels use `org.sanctum`; build/test temporary directories also use the new name. No production service was replaced. Qualified runtime environment variables, plugin/tool identities, privacy scopes, worker ownership/model/cache references and legacy credential locations remain unchanged for the [documented compatibility reasons](naming-compatibility.md). Historical citations and captured before-schema fixtures remain truthful.

The rename changes two reviewed runtime source/build outputs and the matching schema-description snapshot. Their new integrity hashes were reviewed explicitly; other canonical outputs and the pinned OpenClaw runtime remain unchanged. No model, provider or unrelated dependency version was upgraded.

## Checks

The original 151-test baseline is retained. One publication scanner regression now rejects Finder metadata already excluded by Git/Docker ignores, yielding **152 tests**: gate 93, reliability 29, MCP 8, packaging 11, plugins 11. Candidate dependency installation, six canonical builds, tests, audit, fresh private setup/doctor and Compose validation passed. A fresh source-only copy passed all nine stages, including the same 152 tests, all six canonical builds, setup/doctor and Compose validation. The 178-file source/contextual scan found zero issues; all 125 original inputs and production plugin links remain unchanged. No new paid provider or personal-source test is implied by the rename.

An initial `make deps` repeat refused an existing test venv. The disposable candidate test venv was explicitly recreated with `UV_VENV_CLEAR=1`; production and host inference/UI environments were not modified. An initial integrity-review script expected only two changed entries and correctly stopped when it also found the matching schema-description snapshot; that exact description-only change was reviewed before hashes were sealed. Failed attempts remain private evidence.

## Retained exceptions

- Local 4B autonomous browser-target selection failed in one conversational test; explicit native isolated-browser navigation and approvals passed.
- The final Messages answer had a structured unsent draft but omitted a requested literal DRAFT label inside its prose. The formatting failure is retained.
- Vitest/mocker 3.2.7 retains a reviewed moderate development-only advisory; the vulnerable dev-server/browser path is unused by prescribed tests. No broad major-version upgrade was made.

The original live checks are in [acceptance](acceptance.md) and [qualification](qualification.md). They do not claim universal factual accuracy, full Linux product parity, a physically fresh Mac, a repeated model-weight download, a real logout/reboot test or an interactive WebUI private-GPU conversation.

## Public source and operations

The public destination is [vnsparacio/sanctum](https://github.com/vnsparacio/sanctum), tag `v1.0.0`. Release artifacts contain only allowlisted source, with checksums. No private logs, state, credentials, approval tokens, account bindings, personal payloads, dependencies or model caches are distributed. The source-only initial history does not import the original development workspace.

Security reporting uses GitHub Private Vulnerability Reporting/Security Advisories. Source uses Apache-2.0; upstream licenses remain separate. Publication is not deployment: follow the separately approved [migration and rollback procedure](migration.md).
