# Interactive Qwen Code with the private model

This is the owner-operated coding interface. Qwen Code runs on the Mac in the
chosen project directory. Its ordinary file and shell tools act there, under
Qwen Code's interactive approval mode. Sanctum supplies only the private model
route and managed Runpod lifecycle for this path. This is **not Work Mode**:
Work Mode's isolated workspace, host patch authority, protected evaluator,
reviewer, task ledger, and Human Review gate do not apply to edits made by the
interactive Qwen process.

Qwen Code's Mac shell runs with the owner's ordinary account permissions. The
default approval prompts are useful for interactive control, but they are not
an OS isolation boundary. Run it only in projects whose instructions and
dependencies you trust, or opt into Qwen's separate sandbox setting.

## What happens

1. Run `qwen` from a project directory. The Mac starts a loopback-only model
   bridge; this does not allocate a GPU. In `/model`, choose **Sanctum private
   122B (Runpod on demand)**. A fresh install selects that model initially.
2. The first message sent to this model starts a single PRIVATE_LEAD hold through
   the existing owner lifecycle. The managed Runpod pod serves the pinned
   `nvidia/Qwen3.5-122B-A10B-NVFP4` revision from the existing persistent
   volume. The model route is the existing local vLLM SSH tunnel, not a
   Sanctum-gateway OpenAI endpoint.
3. Qwen Code's tools read, edit, and run commands in the Mac project. The local
   bridge accepts only the configured model identity and the one per-process
   loopback token. The Runpod account credential remains in the Mac Keychain;
   the Qwen process receives only the local bridge token.
4. Exiting Qwen ends the hold, releases its lease, and confirms managed GPU
   shutdown. The independent janitor remains the recovery owner. The first
   request waits up to 12 minutes for startup. The requested hold window is 45
   minutes with a $5 compute ceiling; a later request requires restarting Qwen.
   There is no automatic second allocation in that window. If the launcher is
   killed during provider startup, the independent janitor still enforces the
   installed private-lead runtime cap of two hours; inspect provider state
   before assuming the pod has stopped.

Qwen Code has no documented model-selection hook. Choosing the model in `/model`
does not create a paid pod; the first message to it is the automatic trigger.
The model list endpoint is static and cannot start the GPU. Other Qwen model
providers are unaffected.

## Install after the source PR is merged

From the canonical checkout on the reviewed `v1.3-dev` commit, with the private
gateway stopped:

```sh
make deps
make build
make test
make audit
make doctor PREFIX=/absolute/private/prefix
.venv/bin/python -B scripts/qwen_interactive.py --install \
  --sanctum-prefix /absolute/private/prefix
```

The installer uses the repository's pinned Qwen Code 0.24.6 npm lock, installs
it under the external private prefix, adds one `sanctum` provider to
`~/.qwen/settings.json`, and places the `qwen` launcher in `~/.local/bin`.
It preserves other provider entries and backs up an existing settings file
under the private prefix before amending it. It refuses to replace another
`qwen` launcher. Confirm `~/.local/bin` is on `PATH` and run `qwen --version`.

Then:

```sh
cd /path/to/your/project
qwen
```

Use Qwen's ordinary approval prompts for file edits and shell commands. Do not
use `--yolo` for the default interactive workflow. Exiting the TUI releases the
managed hold. To check cleanup, run the installed
`gate/manage.py status --release PRIVATE_LEAD` command and confirm `OFFLINE`,
zero leases and zero active requests; also confirm the owner account has no
managed pod. Persistent model storage is retained.

## Qualification state

The installed Qwen CLI and the provider entry have been tested against a local
synthetic streaming endpoint. Contract tests cover static model listing, local
authentication, model identity, single hold startup, and clean hold exit. A
billable live interactive call through the new bridge remains to be observed.
Historical headless MoodLog and Work Mode results do not qualify this direct
Mac coding path.

Official references: [Qwen model providers](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/model-providers/),
[Qwen tools](https://qwenlm.github.io/qwen-code-docs/en/developers/tools/introduction/),
and [Qwen approval modes](https://qwenlm.github.io/qwen-code-docs/en/users/features/approval-mode/).
