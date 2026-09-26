# Operations and recovery

`./sanctum setup` creates isolated configuration, installs the host runtimes and
prepares the pinned local model without starting services. `./sanctum start`,
`status`, `ready`, `logs` and `stop` are the normal whole-stack interface. The existing
`make doctor`, gateway-only `make up|down` and `scripts/component.py` interfaces
remain available for diagnosis and upgrades. Do not mix gateway-only or
foreground starts with an already managed stack.

Foreground components use `scripts/component.py`. Start only one owner for each socket/port. An occupied gateway port fails rather than adopting or killing an unknown process. A startup timeout is not permission to start a duplicate. Inspect the private log and process state.

## Routine startup and shutdown

Always pass the same private prefix:

```sh
./sanctum start --prefix /absolute/private/prefix
./sanctum status --prefix /absolute/private/prefix
./sanctum ready --prefix /absolute/private/prefix
```

The detached supervisor starts MLX first and checks the exact model identity,
then starts the gateway, configured broker group and WebUI. It records its own
identity and every child PID/command in `state/stack-process.json`, writes
separate private logs and reports a failed phase if a component exits. An
occupied port or a separately managed gateway is refused rather than adopted.
Before launching the broker group, the runner inspects only the exact selected
broker socket paths. An owner-controlled socket that is old and refuses two
connection attempts is atomically moved into a mode-0700
`state/amendments/stale-broker-sockets-*` recovery directory. A live listener,
new socket, non-socket path, changed inode or unsafe ownership/mode is refused
for manual inspection. Brokers also remove their own sockets on clean exit.
Use an individual component only for focused diagnosis after the managed stack
is stopped.

For shutdown, end or cancel active Gate and Work Mode sessions first, then run:

```sh
./sanctum stop --prefix /absolute/private/prefix
```

The command first runs the existing guarded gateway shutdown. Unresolved GPU
ownership or active leases block the stop and leave supervision intact. After
gateway shutdown succeeds, only the exact recorded WebUI, broker and MLX
processes are signaled; stale or unknown processes are not killed. The complete
first-install and WebUI enrollment path is in the
[end-to-end quickstart](quickstart.md).

The GPU controller's rendered `manage.py status|stop|resume|sweep` remains an explicit owner interface. Stop can delete owned compute; do not invoke it against an unrelated production deployment. If deletion is uncertain, keep cleanup supervision intact. Never clear allocation intent just because one provider query found no Pod.

`manage.py status|stop|resume --release PRIVATE_LEAD` addresses the staged lead release explicitly. The no-argument janitor form `manage.py sweep` reconciles both `PRIVATE_80B` and `PRIVATE_LEAD`; it attempts both even when the inactive lifecycle reports the other managed Pod. It fails only when neither release can be reconciled. The two releases remain mutually exclusive and use separate state and lease stores.

Work Mode is invoked only from an authenticated owner session with `/work start PROFILE -- GOAL`. `/work status` and `/work result TASK_ID` expose bounded task state; `/work cancel` requests a deterministic stop; `/work end` removes the isolated worktree, closes the private lease and retains the minimized private receipt. A terminal result deliberately keeps the workspace and lease available for owner inspection until `/work end`; the independent GPU janitor still enforces lease expiry, idle grace and maximum runtime after gateway loss. Mutation is limited to exact observed replacements, bounded text-file create/delete/move operations, and one exact preflighted multi-file text patch. It does not expose arbitrary host paths, a generic shell, fuzzy patches, binary/vendor/generated edits or partial patch commits.

After a successful edit, Work Mode keeps the permitted inspection and edit capabilities available so a multi-file candidate can be finished. The host still marks test evidence stale and hides `FINAL` until a test runs. A successful explicit test invokes the host evaluator and, when configured, the reviewer. The model can still escalate; its private receipt records only a digest, fixed category and broad concept flags for the reason, never the reason text.

The edit intent exposes four exact argument shapes: replace uses `path`, `old_text`, and `new_text` with no operation; create uses `operation=create`, `path`, and `new_text`; delete uses `operation=delete` and `path`; move uses `operation=move`, `path`, and `destination`. A malformed shape is rejected before authority or mutation and consumes the existing bounded correction turn. A provider or execution failure with uncertain mutation still stops the task.

Doctor refuses config/source drift. Preserve the receipt and investigate the exact change. Setup refuses a partial/nonempty prefix rather than erasing it. Keep the old deployment until new acceptance closes. No uninstall removes credentials, databases, snapshots, model caches or provider volumes.

Use the validated configuration amendment command with the gateway stopped; it records a private rollback transaction and refuses unknown authority fields. Persistent service installation remains an explicit owner deployment step; a prefix-specific GPU janitor template is generated. Do not describe the foreground component launcher as a replacement for the reference installation's proven janitor supervision.

## Measured lifecycle behavior

Whole-stack startup permits up to five minutes for a cold cached MLX load, 60
seconds for the gateway, 30 seconds for broker sockets and three minutes for
WebUI. The foreground component commands retain their existing behavior for
diagnosis. `component.py mlx|webui --health --prefix ...` checks only that
component's loopback health/identity, not end-to-end inference. Shutdown
verifies the candidate gateway process has exited within 15 seconds; a timeout
remains an explicit pending/error state. `make doctor
PREFIX=/absolute/private/prefix` also reports `webui_function_sync`; `pass`
means the active imported guard and pipe exactly match the reviewed rendered
files, while `stale`, `missing`, `inactive`, `unsafe`, or `unavailable`
requires owner inspection and re-import rather than silent database
replacement.

`./sanctum ready --prefix ...` combines the service report with privacy-safe
readiness metadata for the WebUI owner, imported guard/pipe, configured brokers,
Google OAuth, web search and optional hosted models. It does not read personal
messages or account content, auto-grant macOS permissions, modify the WebUI
database or select a model for the owner. A `ready` result means required
services, imported functions and configured credentials are present; the report
still reminds the owner about Messages Full Disk Access and the per-chat **Mac
prompt gate** selection.

The WebUI bridge waits beyond the gate's bounded local execution deadline before it closes its authenticated loopback connection. This prevents the UI transport from cancelling a still-valid MLX request; the gate and model deadlines remain bounded and no request is automatically replayed.

After disk recovery, the uniquely named test janitor executed an offline sweep and another after restart. It was loaded and confirmed active before the approved GPU test, and remained available until provider-side deletion and zero leases were confirmed. Only then was it unloaded and its exact test plist removed. The earlier xpcproxy failure is retained as historical evidence. Repeat this validation for a new deployment; no production service was replaced.

An interrupted foreground broker can leave a stale Unix socket. Normal managed
startup now performs the bounded exact-path recovery described above and
preserves the socket as rollback evidence. If it refuses recovery, inspect that
exact path and listener; do not delete a socket merely because launch failed,
and never use a broad process-name kill.

## Content telemetry delivery deployment

This repository does not perform live AWS IAM, bucket, credential, scheduler,
or Splunk mutation. After the reviewed source is installed and the gateway is
stopped, the owner must complete these later actions:

1. Choose a dedicated content bucket or a dedicated `content/` prefix that is
   disjoint from the existing operational `ops/` destination. Retain the
   existing operational writer, policy and schedule unchanged.
2. Create a Mac AWS profile backed by a credential limited to conditional
   `PutObject` on that content prefix. Enroll credentials through the external
   AWS credential mechanism; never paste them into the delivery JSON, source,
   logs or chat.
3. Create a separate Splunk AWS credential with read/list access only to the
   content prefix, and configure a separate input/index/sourcetype only after
   privacy and retention review. Do not grant the Mac writer read or delete,
   and do not grant either credential access to `ops/` through this change.
4. Copy `config/examples/content-telemetry-delivery.json` to a private path
   such as `$SANCTUM_PRIVATE_PREFIX/config/content-telemetry-delivery.json`,
   replace only the local destination/CLI/profile bindings, set mode `0600`,
   and set `enabled` to `true` after the policy is active.
5. Run the command once with the candidate gateway stopped, inspect its
   content-free count summary and the private spool, then install a bounded
   owner scheduler only after that canary succeeds:

```sh
node "$SANCTUM_PRIVATE_PREFIX/gate/content-telemetry/delivery.mjs" \
  --config "$SANCTUM_PRIVATE_PREFIX/config/content-telemetry-delivery.json" \
  --root "$SANCTUM_PRIVATE_PREFIX/state/telemetry/content"
```

The Mac writer identity policy can be limited to the following shape (replace
the placeholder locally; do not commit the rendered policy):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "WriteSanctumContentOnly",
    "Effect": "Allow",
    "Action": "s3:PutObject",
    "Resource": "arn:aws:s3:::<CONTENT_BUCKET>/content/*"
  }]
}
```

The separate Splunk reader policy can be limited to listing the content prefix
and reading its objects:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListSanctumContentOnly",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<CONTENT_BUCKET>",
      "Condition": {"StringLike": {"s3:prefix": ["content/*"]}}
    },
    {
      "Sid": "ReadSanctumContentOnly",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::<CONTENT_BUCKET>/content/*"
    }
  ]
}
```

Bucket policy, Object Lock/versioning, encryption, lifecycle/retention and
Splunk deletion semantics are owner security decisions outside this slice.
The client-side conditional put is mandatory even when stronger bucket
immutability is later enabled. A nonzero delivery run affects only the
delivery job: unresolved batches remain in `failed`, and Sanctum stays
available. Investigate privately; do not refresh hashes, delete batches or
broaden IAM to make a retry pass.
