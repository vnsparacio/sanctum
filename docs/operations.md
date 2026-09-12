# Operations and recovery

`make setup` creates isolated configuration without starting services. `make doctor` verifies source/runtime/config hashes. `make up` starts the candidate gateway; `status` checks its recorded identity; `logs` returns a private log location. `down` signals only a process matching this candidate's recorded executable and port. If GPU autostart is configured it first invokes the existing managed stop procedure, which may delete owned compute; uncertain cleanup blocks shutdown. `uninstall` stops that gateway and retains private state. No LaunchAgent is installed by the new setup.

Foreground components use `scripts/component.py`. Start only one owner for each socket/port. An occupied gateway port fails rather than adopting or killing an unknown process. A startup timeout is not permission to start a duplicate. Inspect the private log and process state.

The GPU controller's rendered `manage.py status|stop|resume|sweep` remains an explicit owner interface. Stop can delete owned compute; do not invoke it against an unrelated production deployment. If deletion is uncertain, keep cleanup supervision intact. Never clear allocation intent just because one provider query found no Pod.

Doctor refuses config/source drift. Preserve the receipt and investigate the exact change. Setup refuses a partial/nonempty prefix rather than erasing it. Keep the old deployment until new acceptance closes. No uninstall removes credentials, databases, snapshots, model caches or provider volumes.

Use the validated configuration amendment command with the gateway stopped; it records a private rollback transaction and refuses unknown authority fields. Persistent service installation remains an explicit owner deployment step; a prefix-specific GPU janitor template is generated. Do not describe the foreground component launcher as a replacement for the reference installation's proven janitor supervision.

## Measured lifecycle behavior

Cold gateway startup now waits up to 60 seconds. Shutdown verifies the candidate process has exited within 15 seconds; a timeout remains an explicit pending/error state. MLX and WebUI remain foreground components. `component.py mlx|webui --health --prefix ...` checks only that component’s loopback health/identity, not end-to-end inference.

After disk recovery, the uniquely named test janitor executed an offline sweep and another after restart. It was loaded and confirmed active before the approved GPU test, and remained available until provider-side deletion and zero leases were confirmed. Only then was it unloaded and its exact test plist removed. The earlier xpcproxy failure is retained as historical evidence. Repeat this validation for a new deployment; no production service was replaced.

An interrupted foreground broker can leave a stale Unix socket. Inspect its owner and confirm no listener remains before removing that exact socket. Do not delete a socket merely because a new launch failed, and never use a broad process-name kill.
