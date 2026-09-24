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
SANCTUM_PREFIX="$HOME/.local/share/sanctum-v1"
mkdir -p "$SANCTUM_PREFIX"
chmod 700 "$SANCTUM_PREFIX"
```

The directory must be empty for the first setup. Do not point it at an existing
OpenClaw home, an existing Open WebUI database or another Sanctum deployment.

## 2. Verify and install the source

```sh
git clone https://github.com/vnsparacio/sanctum.git
cd sanctum

make deps
make build
make test
make audit
make setup PREFIX="$SANCTUM_PREFIX"
make doctor PREFIX="$SANCTUM_PREFIX"
```

`make setup` creates authentication material, rendered configuration, private
state directories and an integrity receipt. It does not import accounts, start
models or contact a paid provider. Re-running setup is safe only while the
installed receipt still matches; drift is refused rather than overwritten.

## 3. Install the local model and WebUI runtimes

```sh
.venv/bin/python scripts/bootstrap.py mlx --prefix "$SANCTUM_PREFIX"
.venv/bin/python scripts/bootstrap.py webui --prefix "$SANCTUM_PREFIX"
make doctor PREFIX="$SANCTUM_PREFIX"
```

The MLX environment and Open WebUI environment are separate and live beneath
the prefix. The first MLX start may download the pinned Qwen weights. Use
`--cache-only` when the weights already exist and no download should occur.

## 4. Start Sanctum

Keep the foreground component terminals open. Start only one heavy model
server on a memory-constrained Mac.

Terminal 1 — local Qwen through MLX:

```sh
cd /absolute/path/to/sanctum
.venv/bin/python scripts/component.py mlx \
  --prefix "$SANCTUM_PREFIX" \
  --cache-only
```

Terminal 2 — verify MLX, then start the authenticated gateway:

```sh
cd /absolute/path/to/sanctum
.venv/bin/python scripts/component.py mlx \
  --prefix "$SANCTUM_PREFIX" \
  --health
make up PREFIX="$SANCTUM_PREFIX"
make doctor PREFIX="$SANCTUM_PREFIX"
```

Terminal 3 — Open WebUI:

```sh
cd /absolute/path/to/sanctum
.venv/bin/python scripts/component.py webui \
  --prefix "$SANCTUM_PREFIX"
```

The default loopback endpoints are:

| Component | Address |
| --- | --- |
| Open WebUI | `http://127.0.0.1:28000` |
| Local MLX model | `http://127.0.0.1:28080` |
| Sanctum/OpenClaw gateway | `http://127.0.0.1:28789` |

If a port is occupied, stop and identify the exact listener. Do not launch a
duplicate gateway or a competing model server.

## 5. Complete the Open WebUI checkpoint

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

## 6. Talk to Assistant Mode

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

## 7. Understand consent dialogs

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

## 8. Use Work Mode

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

## 9. Stop or restart

Before shutdown, finish or cancel active work. A terminal Work Mode result keeps
its worktree and lease until `/work end` so it can be inspected.

```sh
make down PREFIX="$SANCTUM_PREFIX"
```

Then stop WebUI with Ctrl-C in its terminal and stop MLX with Ctrl-C in its
terminal. Keep the independent GPU janitor loaded whenever ownership could be
uncertain. Do not delete the prefix to stop the application.

For the next session, repeat section 4. Open WebUI state persists, so account
creation and function import are not repeated unless an upgrade changed the
rendered guard or pipe.

## Next steps

- [Detailed installation and upgrades](installation.md)
- [Configuration and optional integrations](configuration.md)
- [Routine operations](operations.md)
- [Troubleshooting](troubleshooting.md)
- [Migration and rollback](migration.md)
