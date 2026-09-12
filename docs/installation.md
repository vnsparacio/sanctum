# Installation

## Core and host requirements

The tested source contract targets OpenClaw 2026.8.1, Node 26.8.1 and Python 3.12.14. `make deps` installs the root npm lock and the three pinned media dependencies into `.venv`. It does not install global packages. `make build` builds six plugins and checks reviewed OpenClaw artifacts. Then run tests, audit, setup and doctor.

The source-only test path can run without an Apple GPU. Full local MLX inference requires Apple Silicon/macOS. Run `.venv/bin/python scripts/bootstrap.py mlx --prefix /absolute/private/prefix`. This installs `host/requirements-macos.txt` into that prefix’s `runtime/mlx` environment. The launcher uses this exact environment and never adopts a model executable from PATH. The preserved model is `mlx-community/Qwen3-4B-Instruct-2507-4bit`. A first launch may download weights; allow sufficient disk and memory. Check available memory before running a second server beside production. Qualification on this Mac used existing downloaded weights with `--cache-only`; a new model download was not repeated.

```sh
.venv/bin/python scripts/component.py mlx --prefix /absolute/private/prefix --cache-only
# In another terminal, check the model identity:
.venv/bin/python scripts/component.py mlx --prefix /absolute/private/prefix --health
# In another terminal:
make up
```

Component processes run in the foreground. Stop them with Ctrl-C. The launcher retains conservative concurrency/cache/prefill limits. It does not supervise MLX through a system-wide service.

## WebUI

Run `.venv/bin/python scripts/bootstrap.py webui --prefix /absolute/private/prefix`, then `.venv/bin/python scripts/component.py webui --prefix /absolute/private/prefix`. The pinned `open-webui==0.11.1` runtime is installed into `runtime/webui` under that prefix. It retains Open WebUI’s license and branding. Production remains unchanged. Data lives under the prefix; UI binds loopback port 28000. Create your own administrator account locally.

In WebUI Functions, import the rendered prefix `gate/webui/guard.py` as the gate boundary filter and `gate/webui/pipe.py` as its pipe. Enable the filter on the gate model. Use a saved administrator chat, not a temporary chat. Run `/gate new` and `/gate help`. Upload/RAG/search/memory preprocessing must remain blocked. The host bridge and gateway use the generated private configuration; copying the pipe from the unrendered source will not work.

## Optional personal sources

The inspected host used `imsg` 0.14.2, `gog` 0.38.1 and Apple `jq` 1.7.1. Install compatible versions separately. Check their versions/contracts against the original read-only wrappers before enabling. Do not grant OpenClaw broad Full Disk Access. Grant only the Messages wrapper's documented host access; never disable SIP.

Gmail/Calendar wrappers expect a dedicated read-only Google environment at prefix `state/google-readonly`, with account files in `config/gmail-read/account` and `config/calendar-read/account`. Configure Google OAuth locally with the minimum read scopes. Never grant send/calendar-write scopes for this package. The wrappers retain read-only command restrictions.

After read-only OAuth/host permission setup, write an owner-only JSON proposal outside source, for example `{"integrations":["gmail","calendar"],"accounts":{"gmail":"you@example.invalid","calendar":"you@example.invalid"}}`. Replace the fictional addresses locally. Apply it with `.venv/bin/python scripts/configure.py --proposal /absolute/private/proposal.json`. The gateway must be stopped. This explicit amendment updates only supported fields, records private before/after state, and updates the configuration receipt. It cannot enable generic shell, broaden provider policy or remove approvals. Run doctor, restart the gateway, then run the relevant foreground broker.

Configuration amendments also support `contacts`, `file_roots` and a small set of GPU resource/credential references. `--rollback /absolute/private/amendment-directory` restores only matching before/after files and refuses intervening edits. Broker markers are managed by the same integration proposal.
Contacts are explicit aliases in `config/contacts.json`; the default is empty and unknown contacts fail. File roots initially point into prefix `files/`; no home-directory access is implied. Markdown and files can run through their respective component launchers once their optional tool configuration is reviewed.

## Strong reasoning tiers

Hosted credentials, current provider eligibility and Runpod resources require explicit operator setup and acceptance. The sample GPU resource ID is a non-operational placeholder and autostart is disabled. The existing lifecycle code preserves reconciliation, budget, tunnel and cleanup rules. Do not enable it until configuration, a checksummed v2.13.0 Runpod CLI, SSH identity, private storage and independent cleanup have been reviewed. No provider resources are created by installation.

## Independent GPU cleanup

Setup generates `config/gpu-janitor.plist` with a prefix-specific label and isolated environment. Before enabling autostart, review it and load it explicitly with `launchctl bootstrap gui/$(id -u) /absolute/prefix/config/gpu-janitor.plist` in an owner-approved installation window. This installs no new model authority: it only sweeps existing ownership. The configuration amendment refuses autostart without a loaded matching janitor, reviewed resource ID, private SSH key and checksum-matching Runpod CLI. It never creates a Pod itself. Persistent installation across login and live outage/cleanup acceptance remain operator deployment checks.

## Bootstrap failure and WebUI defaults

An existing runtime directory is never overwritten. If dependency installation failed after creating a venv, inspect the private failure log; resume the exact requirements install with `uv pip install --python /absolute/private/prefix/runtime/mlx/bin/python -r host/requirements-macos.txt`, then `uv pip check --python /absolute/private/prefix/runtime/mlx/bin/python`. For WebUI use `runtime/webui/bin/python` and `host/requirements-webui.txt`. Alternatively choose a new prefix. Do not copy production environments.

WebUI binds only loopback. New-state defaults disable external OpenAI/Ollama connections, updates, web search, arena models, automation and memory; CORS is limited to the two loopback origins on port 28000. WebUI persists configuration in its database: changed environment defaults do not override an already saved setting. In an existing candidate UI, explicitly review and disable these settings through its administrator controls. Import the filter and attach it to the gate model before chatting. Its source rejects uploads/tools/features before downstream processing.

The full application backend and interactive saved chat were tested with a separate synthetic administrator. This account belongs only to qualification; create your own account for deployment. The gate filter disables implicit WebUI built-in tools through per-request legacy function-calling mode while rejecting explicitly requested tools. Calendar/Gmail reads used explicitly authorized read-only credentials; fresh OAuth enrollment was not repeated. Following disk recovery, the isolated login janitor swept and restarted successfully, and the bounded private GPU lifecycle passed through verified cleanup. The owner-run Messages helper and candidate broker/wrapper check also passed in an authorized Terminal. A wrapper history limit of one fetches at most three raw records because it prefetches two before removing empty texts; distinguish returned count from underlying reads when setting a privacy bound.

Plan free disk space for both environments and caches: measured WebUI dependencies occupied about 2 GiB, npm about 1 GiB, and the shared test Python package cache about 2.5 GiB, excluding MLX weights. Repeated source-copy builds need additional room. A qualification attempt exhausted free space and passed after removing only disposable test dependency copies. Never delete model weights or production state as an automatic installer recovery.
