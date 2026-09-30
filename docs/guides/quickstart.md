# End-to-end quickstart

This guide takes a new isolated Sanctum prefix from source verification to a
saved Open WebUI conversation. It also records the normal restart and shutdown
sequence. The stable `main` branch describes V1.2. The `v1.3-dev` branch is an
integration line, not a release; use it only when intentionally evaluating
V1.3 behavior.

## 1. Prerequisites

The supported full runtime is macOS on Apple Silicon with Node 26.8.1, Python
3.12.14 and `uv`. Allow roughly 6 GiB for source dependencies and the two
prefix-owned Python environments, plus the cached Qwen weights. Docker Desktop
is required only for Work Mode and optional container-backed integrations.

Choose one absolute, owner-private prefix and use it consistently. The examples
below keep it outside the repository:

```sh
export SANCTUM_PREFIX="$HOME/.local/share/sanctum-v1"
mkdir -p "$SANCTUM_PREFIX"
chmod 700 "$SANCTUM_PREFIX"
```

The directory must be empty for the first setup. Do not point it at an existing
OpenClaw home, an existing Open WebUI database or another Sanctum deployment.

## 2. Set up Sanctum

```sh
git clone https://github.com/vnsparacio/sanctum.git
cd sanctum

./sanctum setup
```

The resumable runner installs repository dependencies if absent, verifies the
reviewed source, creates authentication material and private state, installs
the separate pinned MLX and Open WebUI environments, and downloads the pinned
Qwen weights only when they are absent. Use `--cache-only` to require an
existing model cache and refuse network download. Existing complete runtimes
are verified and retained; partial or unexpected runtimes are never overwritten.

Optional sources are configured with one owner-private proposal. The runner
installs the reviewed web runtime before applying a proposal that enables web:

```sh
./sanctum setup \
  --proposal /absolute/private/setup-proposal.json \
  --authorize
```

`--authorize` accepts a web API key through hidden input and launches only the
read-only Google OAuth scopes named by configured Gmail or Calendar accounts.
Never put secrets in the proposal or command line. The proposal schema and
examples are in [configuration](configuration.md). Hosted Qwen/frontier routes
are optional; setup reports whether the isolated OpenRouter profile is still an
owner checkpoint, while local operation requires no hosted API key.

## 3. Start Sanctum

```sh
cd /absolute/path/to/sanctum
./sanctum start
```

The command returns when MLX has loaded the exact local model, the authenticated
gateway is listening, every configured broker socket is reachable and Open
WebUI is healthy. It runs one detached, owner-scoped supervisor and stores logs
beneath `$SANCTUM_PREFIX/logs`. It refuses unknown listeners instead of adopting
or killing them. If a previous broker crashed and left an exact private Unix
socket behind, startup proves that the owner-controlled socket has no listener
and moves it to a private recovery directory before continuing. It never
removes or adopts a live, unsafe or unknown path.

The default loopback endpoints are:

| Component | Address |
| --- | --- |
| Open WebUI | `http://127.0.0.1:28000` |
| Local MLX model | `http://127.0.0.1:28080` |
| Sanctum/OpenClaw gateway | `http://127.0.0.1:28789` |

If a port is occupied, stop and identify the exact listener. Do not launch a
duplicate gateway or a competing model server.

Run the combined readiness check after startup or whenever an integration
changes:

```sh
./sanctum ready
```

It distinguishes healthy services from WebUI owner/function enrollment,
read-only Google OAuth, the web-search credential and optional hosted-model
authorization. It returns exact next actions without printing account names or
secret values. Messages Full Disk Access and per-conversation selection of
**Mac prompt gate** remain explicit owner checks because macOS and WebUI own
those decisions.

## 4. Complete the Open WebUI checkpoint

Open `http://127.0.0.1:28000` and create the local owner administrator. In
Open WebUI **Functions**:

1. Import `$SANCTUM_PREFIX/gate/webui/guard.py` as the boundary filter.
2. Import `$SANCTUM_PREFIX/gate/webui/pipe.py` as the **Mac prompt gate** pipe.
3. Confirm the current pipe metadata version is `2.1.0`.
4. Enable the guard on the Mac prompt gate model.
5. Create and save a normal administrator-owned chat.

Select **Mac prompt gate** in the WebUI model picker. Do not select the raw MLX
provider: the pipe is what preserves Sanctum sessions, disclosure decisions and
local-tool boundaries. Disable WebUI search, memory, tools, skills, uploads,
RAG, arena and other preprocessing features for this model.

Open WebUI stores imported functions in its database. Updating the rendered
file on disk does not update an already imported function. Re-import or replace
the pipe after an upgrade that changes `gate/webui/pipe.py`.

## 5. Talk to Assistant Mode

Send ordinary text in the saved chat. The pipe turns it into a local gate
request; `/gate ask` remains available but is not required.

The WebUI model picker selects the Sanctum gate, not a raw reasoning provider.
Within that gate:

- ordinary text uses the configured quality policy and eligible tiers;
- `/gate ask-235 QUESTION` requests the hosted Qwen 235B route unless policy
  requires the frontier tier;
- `/gate ask-strong QUESTION` requests the frontier tier;
- `/gate exclude local|235b|vision|frontier` removes a tier for the current
  session and `/gate include NAME` restores it;
- `/gate mode active` allows quality routing, while `/gate mode shadow` records
  the recommendation but keeps eligible text on local Qwen;
- `/gate status` reports the session, quality mode and eligible tiers;
- `/gate new` clears gate history and starts a genuinely new conversation.

Private 80B is retired and cannot be selected. Hosted models are reasoning-only
and never receive Mac tools or action authority. Sanctum does not silently fall
back when a selected model is unavailable.

## 6. Understand consent dialogs

Local Qwen answers do not require disclosure approval. When the gate proposes
sending current prompt text to a hosted model, the WebUI pipe presents an
authenticated confirmation dialog:

- **send once** approves one exact, expiring disclosure;
- the Gemini audit option grants only current-prompt risk classification for
  at most eight calls or 15 minutes, whichever comes first;
- **keep local/deny** sends nothing to that destination.

The audit grant never covers history, attachments, tool results, answer
generation or actions. Use `/gate audit status` to inspect it and `/gate audit
revoke` to remove it. Raw `/gate approve <id>` commands remain a protocol and
diagnostic path, but an up-to-date WebUI pipe presents the normal owner choice
as a dialog.

## 7. Use Work Mode

Work Mode is separate from Assistant Mode and always requires an explicit owner
command:

```text
/work start PROFILE -- GOAL
/work status
/work result TASK_ID
/work cancel
/work end
```

It operates only in an isolated task worktree. The current bounded editor can
make an exact replacement in an observed UTF-8 file, create one new text file,
delete or move an observed text file, or apply one exact multi-file text patch.
The Mac rejects path escapes, protected paths, symlinks, binary/vendor/generated
content, fuzzy patching, replacement of an existing create/move destination and
partial multi-file commits. Repository commands come from a fixed profile in a
pinned non-root container; Work Mode has no generic host shell or Docker socket.

Work Mode is not enabled by a fresh core setup. Existing accepted deployments
install it through the stopped-gateway amendment described in
[installation](installation.md#install-or-upgrade-work-mode). That amendment
requires the independent janitor, verified offline GPU ownership and Docker.

## 8. Stop or restart

Before shutdown, finish or cancel active work. A terminal Work Mode result keeps
its worktree and lease until `/work end` so it can be inspected.

```sh
./sanctum status
./sanctum stop
```

The stop command first uses the existing gateway shutdown guard, including
lease and GPU-ownership checks. Only after it succeeds does the supervisor stop
the exact WebUI, broker-group and MLX processes it recorded. Private state,
credentials, WebUI data and model caches are retained. If ownership or an
active lease is uncertain, shutdown refuses and supervision remains in place.
Do not delete the prefix to stop the application.

For the next session, repeat section 3. Open WebUI state persists, so account
creation and function import are not repeated unless an upgrade changed the
rendered guard or pipe.

## Next steps

- [Detailed installation and upgrades](installation.md)
- [Configuration and optional integrations](configuration.md)
- [Routine operations](operations.md)
- [Troubleshooting](troubleshooting.md)
- [Migration and rollback](migration.md)
