# Installation and upgrades

Use the [end-to-end quickstart](quickstart.md) for the shortest path to a local
conversation. This guide explains component installation, Work Mode, upgrades
and operator checkpoints in more detail.

## Core source and private prefix

The tested source contract targets OpenClaw 2026.8.1, Node 26.8.1 and Python
3.12.14. Full local inference requires Apple Silicon and macOS. Source-only
verification can run without an Apple GPU, personal accounts or paid-provider
credentials.

```sh
make deps
make build
make test
make audit
make setup PREFIX=/absolute/private/prefix
make doctor PREFIX=/absolute/private/prefix
```

`make deps` installs the root npm lock and pinned Python dependencies into the
existing repository `.venv`; inspect that environment before recreating it.
`make build` compiles six plugins and validates reviewed OpenClaw artifacts.
Setup renders a new private installation and refuses a partial or changed
prefix. It never adopts another OpenClaw home or WebUI database.

## Local Qwen through MLX

```sh
.venv/bin/python scripts/bootstrap.py mlx \
  --prefix /absolute/private/prefix
```

This installs `host/requirements-macos.txt` into the prefix-owned
`runtime/mlx` environment. The launcher never adopts a model executable from
`PATH`. The pinned model is
`mlx-community/Qwen3-4B-Instruct-2507-4bit`. A first launch may download
weights; the accepted deployment reuses existing weights with `--cache-only`.

```sh
# Foreground model server
.venv/bin/python scripts/component.py mlx \
  --prefix /absolute/private/prefix \
  --cache-only

# Separate terminal: identity and health
.venv/bin/python scripts/component.py mlx \
  --prefix /absolute/private/prefix \
  --health
```

The launcher retains conservative concurrency, cache and prefill limits. Stop
it with Ctrl-C. Do not run two heavy model servers merely to avoid a maintenance
window.

## Open WebUI

```sh
.venv/bin/python scripts/bootstrap.py webui \
  --prefix /absolute/private/prefix
.venv/bin/python scripts/component.py webui \
  --prefix /absolute/private/prefix
```

The pinned `open-webui==0.11.1` runtime lives beneath `runtime/webui`, preserves
Open WebUI licensing/branding and binds only to `127.0.0.1:28000`. Its data is
isolated beneath the prefix. Create an owner administrator locally.

In Open WebUI **Functions**, import the rendered files from the prefix, not the
unrendered repository copies:

- `gate/webui/guard.py` — enable this boundary filter on the gate model;
- `gate/webui/pipe.py` — select the resulting **Mac prompt gate** model.

Use a saved administrator chat. Temporary chats do not have the stable identity
required for approval scope. Keep uploads, tools, skills, RAG, search, memory,
arena and automation disabled. The filter selects legacy function-calling mode
to prevent WebUI from adding implicit built-in tools while continuing to reject
explicit tool or feature requests.

Open WebUI persists imported function source in its database. An on-disk
upgrade is not enough: when `gate/webui/pipe.py` or `guard.py` changes,
re-import or replace that function and confirm the rendered pipe version before
testing. The current conversational pipe is version `2.1.0`.

## Start the complete local path

Start MLX first, verify it, start the gateway, start the broker group, and then
start WebUI:

```sh
# Terminal 1
.venv/bin/python scripts/component.py mlx \
  --prefix /absolute/private/prefix \
  --cache-only

# Terminal 2
.venv/bin/python scripts/component.py mlx \
  --prefix /absolute/private/prefix \
  --health
make up PREFIX=/absolute/private/prefix
make doctor PREFIX=/absolute/private/prefix

# Terminal 3
.venv/bin/python scripts/component.py brokers \
  --prefix /absolute/private/prefix

# Terminal 4
.venv/bin/python scripts/component.py webui \
  --prefix /absolute/private/prefix
```

The gateway uses the recorded prefix and port; omitting `PREFIX` starts or
inspects the repository `.local` candidate instead. Component health checks
establish only that component's loopback identity, not an end-to-end answer.
The `brokers` component starts enabled Messages, Gmail and Calendar integrations
plus the local Markdown and file brokers. It stops the whole group if one exits;
individual broker component names remain available for focused diagnosis.

## Install or upgrade Work Mode

Work Mode is an optional, separately reviewed runtime amendment. It is not
enabled by fresh core setup and is not a shortcut around GPU or cleanup
qualification. The amendment requires:

- the candidate gateway stopped;
- Docker Desktop healthy on a local Unix socket;
- the generated independent GPU janitor reviewed, loaded and executing;
- permanent private-80B retirement recorded;
- both managed releases offline with no leases, Pod identity or uncertain
  allocation; and
- the installed receipt and source manifest still valid.

For an accepted deployment that satisfies those conditions:

```sh
make down PREFIX=/absolute/private/prefix
.venv/bin/python scripts/upgrade_work_mode.py \
  --prefix /absolute/private/prefix \
  --apply
make doctor PREFIX=/absolute/private/prefix
```

The command builds and records the pinned non-root runner image, installs the
Work Mode runtime closure, configures explicit OpenClaw agent ownership with
`main` as the system/local-answer owner, and writes a private rollback record
beneath `state/amendments/`. It leaves GPU autostart disabled. A refusal occurs
before mutation when a safety precondition fails. If a later installation step
fails after a transaction is created, preserve the record and use the supported
rollback path; do not work around the failure by editing receipts or state.

After an amendment that updates WebUI functions, restart WebUI and re-import the
rendered pipe. This is required for conversational consent dialogs because the
existing WebUI database retains its previously imported function source.

Rollback accepts only a transaction belonging to the same prefix:

```sh
.venv/bin/python scripts/upgrade_work_mode.py \
  --prefix /absolute/private/prefix \
  --rollback /absolute/private/prefix/state/amendments/work-mode-TRANSACTION
make doctor PREFIX=/absolute/private/prefix
```

Private task receipts and the runner image are retained for evidence.

## Assistant Mode and model choice

Select **Mac prompt gate** in Open WebUI. Ordinary text enters Assistant Mode
directly. The gate decides among eligible local, hosted, multimodal and frontier
reasoners under reviewed policy; the WebUI picker is not a raw provider switch.
Use `/gate ask-235` or `/gate ask-strong` for explicit routing requests and
`/gate exclude`/`include` to control session eligibility. Private 80B remains
retired. Hosted reasoning receives no local tools.

When a hosted disclosure is proposed, the pipe shows a confirmation dialog for
one exact send, the bounded Gemini audit grant, or keep-local/deny. The session
grant covers only current-prompt risk classification for at most eight calls or
15 minutes. `/gate audit status` and `/gate audit revoke` inspect and remove it.

## Work Mode behavior

`/work start PROFILE -- GOAL` creates an isolated task worktree. Current bounded
mutation supports:

- exact replacement of one uniquely observed UTF-8 string;
- creation of one new bounded UTF-8 text file;
- deletion or movement of an observed text file; and
- one exact, preflighted multi-file unified text patch with rollback on partial
  failure.

It does not permit path escapes, arbitrary host files, symlink traversal,
binary/vendor/generated content, fuzzy patching, generic shell arguments,
networked runner commands, live host mounts, Docker-socket access or worker
credentials. Protected files and project-specific task contracts can further
reduce the mutable set.

## Optional personal sources

The inspected host used `imsg` 0.14.2, `gog` 0.38.1 and Apple `jq` 1.7.1.
Install compatible versions separately and compare their contracts with the
read-only wrappers. Do not grant OpenClaw broad Full Disk Access or disable SIP.

Gmail and Calendar expect a dedicated read-only Google environment beneath
`state/google-readonly`, with account files in `config/gmail-read/account` and
`config/calendar-read/account`. Enroll the minimum read scopes locally. Never
put credentials or real account values in source or chat.

Apply supported account, contact, file-root and integration bindings through a
private proposal while the gateway is stopped:

```sh
.venv/bin/python scripts/configure.py \
  --prefix /absolute/private/prefix \
  --proposal /absolute/private/proposal.json
make doctor PREFIX=/absolute/private/prefix
```

The amendment changes only reviewed fields and records private rollback state.
It cannot enable generic shell, broaden provider policy or remove approvals.
Restart the `brokers` component after an integration amendment so it selects the
new enabled set.

## Hosted and private reasoning

Hosted credentials, current provider eligibility and Runpod resources require
explicit owner setup and acceptance. Sample GPU identifiers are
non-operational; autostart is disabled. Do not enable private compute until the
resource references, checksummed Runpod CLI, SSH identity, storage, pricing,
budgets and independent cleanup have been reviewed. Installation alone creates
no provider resource.

Setup generates a prefix-specific `config/gpu-janitor.plist`. Review it before
loading it in an approved installation window:

```sh
launchctl bootstrap "gui/$(id -u)" \
  /absolute/private/prefix/config/gpu-janitor.plist
```

Do not bootstrap an already loaded label. Actual launchd execution and an
offline sweep must pass before enabling any automatic compute. Preserve cleanup
supervision whenever resource ownership is uncertain.

## Bootstrap failures and persistent settings

An existing runtime directory is never overwritten. If dependency installation
fails after venv creation, inspect its private log and resume the exact pinned
requirements install; do not substitute latest versions or copy another
deployment's environment.

WebUI settings persist in its database, so changed environment defaults do not
override saved arena, automation, memory or connection settings. Recheck them
after upgrades. The qualification administrator is synthetic and is not a
deployment account; create your own owner administrator.

Plan disk space for roughly 2 GiB of WebUI dependencies, 1 GiB of npm
dependencies, 2.5 GiB of shared Python test cache, both prefix environments and
model weights. Never delete model caches or private runtime data as an automatic
installer recovery.
