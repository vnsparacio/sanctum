# Sanctum naming and compatibility

Sanctum is the public framework. VinceAI is the original personal/reference deployment and historical project name. Read the [canonical project report](SANCTUM-V1-PROJECT-REPORT.md) for design/history; use [qualification](qualification.md) and [acceptance](acceptance.md) for current measured behavior. Historical report counts are the original 174-file, 151-test snapshot. Calendar qualification covered native reads, bounded broker output and local summary generation; it did not independently audit every natural-language answer.

The [complete rename audit](../SANCTUM-RENAME-AUDIT.md) records every original source occurrence. The report is included without rewriting its historical filenames, benchmark numbers or original naming note.

## Retained contracts

| Identifier | Why retained |
|---|---|
| `VINCEAI_*` runtime environment variables | Existing launchers, brokers and rendered private configuration agree on these names. No new precedence/alias behavior is introduced. |
| `vinceai-reliability`, `vinceai-mcp-guard` plugin IDs | Persisted OpenClaw allowlists and plugin configuration bind these identities. Package/display names are Sanctum. |
| `vinceai__*` MCP tools, profile ID `vinceai`, dated `vinceai-approved:20260907` catalog | Static schemas, approval/guard matching, captured fixtures and reliability checks require consistent identities. |
| File Steward/privacy scope `vinceai` | This is a schema/policy key, not a permission to inspect an arbitrary directory. Keep protected-root and privacy-floor behavior stable. |
| `vinceai-qwen80b`, Pod ownership prefixes, `/workspace/vinceai`, readiness markers | Model identity, allocation reconciliation, reuse and cleanup must continue to recognize the qualified worker. |
| Keychain labels and legacy fallback paths containing VinceAI/vinceai | Renaming cannot migrate credentials or personal data implicitly. Prefix-owned deployments explicitly configure private locations. |
| Telemetry schema, verification symbol/idempotency keys | Preserve compatibility with captured records and one-use verification logic. |
| `gate/install.py`, old service labels in migration examples | Historical reference-deployment migration material. Fresh installations use `scripts/release_operator.py`; publishing does not run legacy migration. |

New setup generates `org.sanctum.<prefix-hash>.gpu-janitor`. Existing private prefixes remain unchanged and keep their receipts. Configure a fresh prefix for the published release; do not reseal old deployment state to hide drift. Newly created source archives and npm package names use Sanctum.
