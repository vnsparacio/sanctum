# Operations and recovery

`make setup` creates isolated configuration without starting services. `make doctor` verifies source/runtime/config hashes. `make up` starts the candidate gateway; `status` checks its recorded identity; `logs` returns a private log location. `down` signals only a process matching this candidate's recorded executable and port. If GPU autostart is configured it first invokes the existing managed stop procedure, which may delete owned compute; uncertain cleanup blocks shutdown. `uninstall` stops that gateway and retains private state. No LaunchAgent is installed by the new setup.

Foreground components use `scripts/component.py`. Start only one owner for each socket/port. An occupied gateway port fails rather than adopting or killing an unknown process. A startup timeout is not permission to start a duplicate. Inspect the private log and process state.

The GPU controller's rendered `manage.py status|stop|resume|sweep` remains an explicit owner interface. Stop can delete owned compute; do not invoke it against an unrelated production deployment. If deletion is uncertain, keep cleanup supervision intact. Never clear allocation intent just because one provider query found no Pod.

`manage.py status|stop|resume --release PRIVATE_LEAD` addresses the staged lead release explicitly. The no-argument janitor form `manage.py sweep` reconciles both `PRIVATE_80B` and `PRIVATE_LEAD`; it attempts both even when the inactive lifecycle reports the other managed Pod. It fails only when neither release can be reconciled. The two releases remain mutually exclusive and use separate state and lease stores.

Work Mode is invoked only from an authenticated owner session with `/work start PROFILE -- GOAL`. `/work status` and `/work result TASK_ID` expose bounded task state; `/work cancel` requests a deterministic stop; `/work end` removes the isolated worktree, closes the private lease and retains the minimized private receipt. A terminal result deliberately keeps the workspace and lease available for owner inspection until `/work end`; the independent GPU janitor still enforces lease expiry, idle grace and maximum runtime after gateway loss.

Doctor refuses config/source drift. Preserve the receipt and investigate the exact change. Setup refuses a partial/nonempty prefix rather than erasing it. Keep the old deployment until new acceptance closes. No uninstall removes credentials, databases, snapshots, model caches or provider volumes.

Use the validated configuration amendment command with the gateway stopped; it records a private rollback transaction and refuses unknown authority fields. Persistent service installation remains an explicit owner deployment step; a prefix-specific GPU janitor template is generated. Do not describe the foreground component launcher as a replacement for the reference installation's proven janitor supervision.

## Measured lifecycle behavior

Cold gateway startup now waits up to 60 seconds. Shutdown verifies the candidate process has exited within 15 seconds; a timeout remains an explicit pending/error state. MLX and WebUI remain foreground components. `component.py mlx|webui --health --prefix ...` checks only that component’s loopback health/identity, not end-to-end inference.

After disk recovery, the uniquely named test janitor executed an offline sweep and another after restart. It was loaded and confirmed active before the approved GPU test, and remained available until provider-side deletion and zero leases were confirmed. Only then was it unloaded and its exact test plist removed. The earlier xpcproxy failure is retained as historical evidence. Repeat this validation for a new deployment; no production service was replaced.

An interrupted foreground broker can leave a stale Unix socket. Inspect its owner and confirm no listener remains before removing that exact socket. Do not delete a socket merely because a new launch failed, and never use a broad process-name kill.

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
