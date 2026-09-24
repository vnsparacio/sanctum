# Troubleshooting

| Symptom | Check / recovery |
|---|---|
| Dependency download fails | Separate unavailable cache/DNS/network access from a bad version pin. Keep the failure log. Do not substitute latest. |
| Plugin metadata generator rejects entry | Hook plugins use definePluginEntry; tool-only metadata generation does not apply. Use make build. |
| Source/runtime drift | Compare reviewed hashes and changes. Do not auto-refresh pins. |
| Setup refuses nonempty prefix | Preserve the contents and inspect partial installation; choose an empty private directory. |
| Gateway exits | Inspect `make status PREFIX=...` and the private gateway log; validate configuration with `make doctor PREFIX=...`. Do not start a duplicate while startup is pending. |
| Gate plugin reports `Cannot find module './ajv.mjs'` | An existing prefix has an incomplete content-telemetry runtime closure. Stop the candidate gateway, run `.venv/bin/python scripts/upgrade_content_telemetry_runtime.py --prefix /absolute/private/prefix`, run `make doctor PREFIX=/absolute/private/prefix`, then restart it. Current Work Mode amendments include this closure. |
| Local answer unavailable | Confirm MLX model identity and health, run doctor, check the selected loopback port, gateway authentication and agent model, and confirm Open WebUI is using **Mac prompt gate**, not the raw MLX provider. Bare-model health does not establish the authenticated agent path. After a Work Mode upgrade, reapply the supported amendment so `main` owns local requests and ambient model resolution. |
| Local tool answer ends with `Reply truncated at the model's output token limit` after only a fragment, or tools succeed but `LOCAL_4B answering was unavailable` follows | Stop the gateway, apply the current `scripts/upgrade_work_mode.py` amendment, run `make doctor PREFIX=...`, and restart. Current source pins `main.thinkingDefault` to `off`, sends `chat_template_kwargs.enable_thinking=false` to MLX, and pins the local model catalog to 4,096 output tokens per internal turn. Gate does not send an outer `max_completion_tokens` cap, which OpenClaw would share across tool selection, tool follow-up, and the final answer. Gate refuses a local handoff if these runtime pins drift. Do not route personal tool results to a hosted model as a workaround. |
| Personal tool unavailable | Configure the read-only account/permission, marker, socket and explicitly allowed tool; do not broaden API/shell access. |
| Unknown contact | Add an explicit local mapping after review; do not broaden the search automatically. |
| WebUI prints `/gate approve <id>` instead of a dialog | Re-import the rendered prefix `gate/webui/pipe.py` into Open WebUI Functions and confirm version `2.1.0`. Updating the file on disk does not replace the function stored in the WebUI database. Exact commands remain valid for protocol diagnosis, but the current owner flow uses confirmation dialogs. |
| Approval unavailable/expired | Deny/stop and obtain a fresh exact approval. The optional audit grant is limited to current-prompt classification, eight calls and 15 minutes; inspect it with `/gate audit status` and remove it with `/gate audit revoke`. |
| GPU allocation unresolved | Reconcile persisted intent; do not blindly create another Pod. |
| Deletion unconfirmed | Keep janitor running and reconcile provider state. Cached OFFLINE alone is insufficient. |
| WebUI drops gate command | Use an administrator-owned saved chat and rendered pipe/filter; preserve preprocessing restrictions. |
| Wrong model or unexpected raw answer | Select **Mac prompt gate** in WebUI. Use ordinary text for policy routing, `/gate ask-235` for hosted Qwen, `/gate ask-strong` for the frontier tier, and `/gate status` to inspect the session. Sanctum deliberately does not silently fall back. |
| Work Mode amendment says Docker timed out | Confirm Docker Desktop's engine is healthy, not merely that its UI process exists. `docker version` and the active local Unix context must return before retrying. The amendment refuses before writing when this preflight fails. Do not delete Docker data or edit a receipt to bypass it. |
| Work Mode amendment refuses ownership or janitor state | Keep the gateway stopped. Reconcile both managed releases to offline/no leases, confirm permanent private-80B retirement and verify the prefix-specific janitor is loaded. Preserve uncertain ownership and use the refusal as the blocker. |
| Candidate port already occupied | Identify the exact listener on ports 28000, 28080 or 28789. Stop only a verified candidate process. A legacy gateway on a different recorded port is not the candidate and should not be killed as cleanup. |

Distinguish model selection, plugin dispatch, broker/wrapper response, provider readiness and UI finalization. A model's explanation of a tool error is not evidence of the underlying cause.

## Local answer diagnostic order

Run these checks from the source tree with the same prefix used at startup:

```sh
.venv/bin/python scripts/component.py mlx \
  --prefix /absolute/private/prefix \
  --health
make status PREFIX=/absolute/private/prefix
make doctor PREFIX=/absolute/private/prefix
make logs PREFIX=/absolute/private/prefix
```

MLX health proves only the model server. Doctor proves the installed source,
runtime pins and rendered configuration. A successful end-to-end local answer
also requires the authenticated OpenClaw gateway, explicit `main` ownership,
the Gate local adapter, the current rendered WebUI pipe and a saved owner chat.

If the installation predates explicit Work Mode ownership and all amendment
preconditions are satisfied, stop the gateway and apply the current supported
upgrade:

```sh
make down PREFIX=/absolute/private/prefix
.venv/bin/python scripts/upgrade_work_mode.py \
  --prefix /absolute/private/prefix \
  --apply
make doctor PREFIX=/absolute/private/prefix
```

Restart the normal component sequence and re-import the pipe if its version
changed. Do not manually add an agent owner or refresh hashes in the private
prefix.

## Qualification findings

A cold gateway can require more than ten seconds; the launcher now waits up to sixty. Never start a duplicate after a pending-start message. Host launchers require their prefix-owned runtime; a globally installed executable is intentionally not adopted.

If a janitor appears in `launchctl print` as `xpcproxy` but creates no state, treat cleanup as unverified. Direct execution succeeding does not establish launchd execution. Preserve the diagnostic record, inspect local OS launch restrictions, and complete a new isolated lifecycle test before enabling GPU. Do not remove quarantine or weaken OS protections speculatively.

WebUI settings persist. After changing defaults, inspect the candidate administrator settings for retained arena/automation/memory options. Its gate filter must remain enabled. Live missing-MLX and missing-gateway tests produced actionable errors without automatic retry or fallback.

The qualification retry after disk recovery passed janitor restart and a bounded live GPU lifecycle. Earlier failure guidance remains applicable on another host. Messages may work in one macOS application context and fail in another; an OS privacy denial is not an empty conversation. Obtain owner assistance in an authorized context rather than disabling OS protections.

If a saved browser chat rejects `/gate help` as a tool request while HTTP tests pass, confirm that the rendered gate filter includes the browser-session implicit-tool fix. It must select legacy function-calling mode before WebUI adds built-in tools; do not remove explicit-tool rejection. The isolated browser is the host-native `openclaw` profile. A model-selected sandbox target fails because no sandbox browser is configured; keep the profile restriction and evaluation denial intact.
