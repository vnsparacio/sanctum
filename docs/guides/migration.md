# Owner migration and rollback

**Requires a separately approved migration window. None of these cutover
commands has been run.** The repository now provides an owner-scoped stack
supervisor, but a source-level lifecycle test is not a production cutover
qualification. Owner-specific OAuth, macOS privacy and WebUI enrollment still
must be completed for the deployment. Do not replace production services
without the checks below and an approved rollback window.

This procedure deliberately creates new conversations/approvals and retains the old deployment for rollback. It does not import historical chats, outstanding gate approvals, nonces or File Steward undo records. Finish/undo old file transactions and close old sessions before cutover. If history-preserving migration is required, stop: no supported importer exists.

## Prepare without changing production

Run from the repository-managed V1 root after all gates pass:

```sh
SANCTUM_REPO="$PWD"
SANCTUM_PREFIX="$HOME/.local/share/sanctum-v1"
SANCTUM_BACKUP="$HOME/.local/share/sanctum-migration-backups/$(date +%Y%m%d-%H%M%S)"
umask 077
mkdir -p "$SANCTUM_BACKUP"
make deps
make build
make test
make audit
./sanctum setup --prefix "$SANCTUM_PREFIX" --cache-only
make doctor PREFIX="$SANCTUM_PREFIX"
```

The prefix must be empty or an already matching setup. Never point it at .openclaw or production WebUI data. Review a private configuration proposal for read-only accounts, explicit contacts, approved file roots and existing GPU references. Do not copy the production OpenClaw config wholesale. Apply only the reviewed proposal while the candidate gateway is stopped:

```sh
: "${SANCTUM_PROPOSAL:?Set the path to the reviewed private proposal JSON}"
.venv/bin/python scripts/configure.py --prefix "$SANCTUM_PREFIX" --proposal "$SANCTUM_PROPOSAL"
make doctor PREFIX="$SANCTUM_PREFIX"
```

Provision provider credentials into the new isolated auth store through the pinned OpenClaw credential workflow. Enroll read-only Google access in the new Google home, or explicitly review a private copy of the dedicated read-only store; never copy a broader write-enabled account. Keep new browser identity isolated. These account/credential enrollment steps require owner input and are not safely replaceable by an unconditional database-copy command.

The generated GPU janitor must pass actual launchd execution, not merely appear loaded. For each new prefix, review the exact plist, install/load its unique label, and confirm an offline sweep before enabling GPU autostart through a separate reviewed proposal. Never stop either cleanup owner while any allocation is uncertain.

## Cutover in an approved maintenance window

1. Close existing gate sessions and finish any file undo obligations. Through the existing production gate’s owner control, stop private compute. Confirm provider-side zero owned Pods plus no leases, active requests or unresolved allocation intent. Retain production cleanup until this is proven. Do not rely only on a cached OFFLINE label.
2. Back up stable original configuration/state privately after quiescing writes. The following locations describe the measured Mac; verify them before running:

```sh
ditto "$HOME/.openclaw" "$SANCTUM_BACKUP/openclaw"
ditto "$HOME/.local/share/vinceai-ui/data" "$SANCTUM_BACKUP/webui-data"
cp "$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist" "$SANCTUM_BACKUP/"
cp "$HOME/Library/LaunchAgents/com.vinceai.openwebui.plist" "$SANCTUM_BACKUP/"
cp "$HOME/Library/LaunchAgents/net.vinceai.phase10-gpu-janitor.plist" "$SANCTUM_BACKUP/"
```

3. Stop original gateway/WebUI services only after an explicit cutover approval:

```sh
launchctl bootout "gui/$(id -u)/ai.openclaw.gateway"
launchctl bootout "gui/$(id -u)/com.vinceai.openwebui"
```

The original MLX server has no discovered LaunchAgent. Its measured command is reproduced under rollback below. Before stopping it, inspect the current process and confirm that exact executable/model/port identity; signal only that verified PID. Never use a broad process-name kill. Do not run two loaded models on a memory-constrained Mac merely to avoid a maintenance window.

4. Start the candidate model, gateway, configured brokers and WebUI through the
   owner-scoped supervisor:

```sh
./sanctum start --prefix "$SANCTUM_PREFIX"
./sanctum status --prefix "$SANCTUM_PREFIX"
```

5. Open loopback port 28000. Enroll the owner administrator; import `$SANCTUM_PREFIX/gate/webui/pipe.py` and `guard.py` in Functions, enable the filter on the gate model, and use a saved chat. Confirm disabled external connections/arena/automation/memory/search. Test `/gate new`, `/gate help`, `/gate status`, a normal local request and the exact disclosure prompt. Re-run approved personal/file/browser checks and a bounded GPU cleanup test. Do not copy the qualification account/database into production.
6. Keep the old source, state, services and backups intact. Only after sustained acceptance should the old janitor be unloaded, and only with confirmed zero old ownership. No volume deletion belongs in migration.

## Rollback

1. End candidate sessions and perform the candidate’s managed GPU stop. Confirm provider-side deletion/no ownership before stopping cleanup. If deletion is uncertain, preserve both cleanup supervision and ownership records; do not roll back by killing processes or deleting state.
2. Stop the candidate with `./sanctum stop --prefix "$SANCTUM_PREFIX"`. It
   runs the existing GPU/lease guard before signaling only its recorded
   processes. Keep all candidate state, logs and receipts for diagnosis;
   shutdown does not delete them.
3. If original MLX was stopped, restore its measured command in a dedicated terminal:

```sh
"$HOME/.local/share/uv/tools/mlx-lm/bin/python" "$HOME/.local/bin/mlx_lm.server" \
  --model mlx-community/Qwen3-4B-Instruct-2507-4bit --host 127.0.0.1 --port 8080 \
  --max-tokens 4096 --decode-concurrency 1 --prompt-concurrency 1 \
  --prefill-step-size 512 --prompt-cache-size 2 --prompt-cache-bytes 4294967296
```

4. Restore the original services if they were unloaded:

```sh
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/ai.openclaw.gateway.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.vinceai.openwebui.plist"
# Only if this original janitor was unloaded after zero ownership was confirmed:
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/net.vinceai.phase10-gpu-janitor.plist"
```

Do not bootstrap an already loaded label. Original configuration was never overwritten, so ordinary rollback does not restore entire databases from backup. If a file was changed during a future migration, compare hashes and restore only that owned change; preserve unrelated edits and durable GPU ownership. Confirm the original saved WebUI chat, local answer and read-only integrations before ending the maintenance window.
