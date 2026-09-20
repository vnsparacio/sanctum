# Troubleshooting

| Symptom | Check / recovery |
|---|---|
| Dependency download fails | Separate unavailable cache/DNS/network access from a bad version pin. Keep the failure log. Do not substitute latest. |
| Plugin metadata generator rejects entry | Hook plugins use definePluginEntry; tool-only metadata generation does not apply. Use make build. |
| Source/runtime drift | Compare reviewed hashes and changes. Do not auto-refresh pins. |
| Setup refuses nonempty prefix | Preserve the contents and inspect partial installation; choose an empty private directory. |
| Gateway exits | Inspect private gateway log; validate configuration using isolated OpenClaw state. |
| Local answer unavailable | Check MLX model identity, selected loopback port, gateway authentication and agent model. Bare-model health does not establish the agent path. |
| Personal tool unavailable | Configure the read-only account/permission, marker, socket and explicitly allowed tool; do not broaden API/shell access. |
| Unknown contact | Add an explicit local mapping after review; do not broaden the search automatically. |
| Approval unavailable/expired | Deny/stop and obtain a fresh exact approval. Never add standing approval. |
| GPU allocation unresolved | Reconcile persisted intent; do not blindly create another Pod. |
| Deletion unconfirmed | Keep janitor running and reconcile provider state. Cached OFFLINE alone is insufficient. |
| WebUI drops gate command | Use an administrator-owned saved chat and rendered pipe/filter; preserve preprocessing restrictions. |

Distinguish model selection, plugin dispatch, broker/wrapper response, provider readiness and UI finalization. A model's explanation of a tool error is not evidence of the underlying cause.

## Qualification findings

A cold gateway can require more than ten seconds; the launcher now waits up to sixty. Never start a duplicate after a pending-start message. Host launchers require their prefix-owned runtime; a globally installed executable is intentionally not adopted.

If a janitor appears in `launchctl print` as `xpcproxy` but creates no state, treat cleanup as unverified. Direct execution succeeding does not establish launchd execution. Preserve the diagnostic record, inspect local OS launch restrictions, and complete a new isolated lifecycle test before enabling GPU. Do not remove quarantine or weaken OS protections speculatively.

WebUI settings persist. After changing defaults, inspect the candidate administrator settings for retained arena/automation/memory options. Its gate filter must remain enabled. Live missing-MLX and missing-gateway tests produced actionable errors without automatic retry or fallback.

The qualification retry after disk recovery passed janitor restart and a bounded live GPU lifecycle. Earlier failure guidance remains applicable on another host. Messages may work in one macOS application context and fail in another; an OS privacy denial is not an empty conversation. Obtain owner assistance in an authorized context rather than disabling OS protections.

If a saved browser chat rejects `/gate help` as a tool request while HTTP tests pass, confirm that the rendered gate filter includes the browser-session implicit-tool fix. It must select legacy function-calling mode before WebUI adds built-in tools; do not remove explicit-tool rejection. The isolated browser is the host-native `openclaw` profile. A model-selected sandbox target fails because no sandbox browser is configured; keep the profile restriction and evaluation denial intact.
