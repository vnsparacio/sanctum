# Configuration and secrets

`gate/SETTINGS.json` is a reviewed template. Setup binds its Python, gate, state and config paths in a private prefix and computes a deployment-specific freeze. The unrendered template is not an executable production configuration. Source integrity is checked before rendering.

The generated environment defines OpenClaw state/config, socket cache, contact mapping, file roots, gateway/MLX ports and the local auth database. It does not redefine the user's HOME. Model/provider IDs, price ceilings, disclosure expiry and safety policy retain their dated production values. These values are version pins, not current catalog/pricing promises. The Gemini audit session grant is source-pinned to at most eight eligible calls or 15 minutes, whichever comes first; each call remains subject to the existing per-request and total network budgets. Changing these authority bounds or the configured audit destination requires a reviewed source release, not a private runtime amendment.

`config/openclaw.json` contains a new gateway token and is mode 0600. Gate authority material, contacts, accounts and receipts remain local. OpenRouter credentials must belong in the isolated OpenClaw auth store; direct OpenAI retention authorization stays false. Keychain references and a dedicated SSH path are configured locally; do not copy production secret values into the source tree.

The first candidate configuration is intentionally minimal: exact utilities are available, optional tool integrations need reviewed setup, GPU autostart is false, and contact aliases are empty. File root configuration accepts only the established scope names and absolute paths; model arguments cannot change those roots.

Restricted interaction content telemetry remains disabled by default. The
reviewed `content_telemetry` settings contain only `enabled`,
`retention_days`, and `access_policy`; the local spool root is derived beneath
the external private state directory at `telemetry/content`. It is separate
from the metadata-only operational `ops/` spool and cannot be selected by a
request, model response, or environment-provided destination. Enabling or
changing collection policy requires an owner-reviewed stopped-gateway settings
amendment and a new private source freeze.

Create an owner-only proposal file outside source containing all three policy
fields, then apply it with the ordinary validated amendment command. Enabling
requires a concrete retention period; destination names and credentials do not
belong in this proposal:

```json
{
  "content_telemetry": {
    "enabled": true,
    "retention_days": 30,
    "access_policy": "owner_only"
  }
}
```

```sh
.venv/bin/python scripts/configure.py \
  --prefix /absolute/private/prefix \
  --proposal /absolute/private/content-telemetry-policy.json
make doctor PREFIX=/absolute/private/prefix
```

Content delivery has a second, private configuration file based on
`config/examples/content-telemetry-delivery.json`. Copy it beneath the external
private prefix, keep it owner-owned mode `0600`, replace the bucket, region,
AWS CLI and profile bindings locally, and enable it only after the IAM and
prefix review in the content telemetry runbook. Never put AWS access keys,
session tokens, account IDs, bucket names, or a rendered delivery file in Git.
The profile must resolve through the owner's external AWS credential store.
The content destination must not be `ops/`; the delivery validator rejects an
operational prefix and unknown fields, including embedded credential fields.

Changed config/settings invalidate integrity. The current setup refuses to overwrite them. Use `scripts/configure.py --proposal` for supported integration/contact/root/account/GPU reference changes, or the bounded `web_retrieval.max_results` amendment. It validates a narrow schema, requires a stopped gateway, writes a private rollback transaction before modification and explicitly updates only the affected hashes. Unsupported policy/provider changes require a separate reviewed release. Do not edit hashes merely to suppress a failure. Environment changes controlling authority paths are operator decisions and must be kept outside model/tool input.

For a reviewed Source-First code update on an existing prefix, stop the managed
stack and run `scripts/upgrade_source_first.py` with
`--prefix /absolute/private/prefix --apply`. This narrow amendment backs up
the installed gate files and receipt to a private rollback record. It accepts
an offline GPU, or the main GPU's
confirmed `RETIRED` state, only when no pod, uncertain allocation, or main or
private-lead lease remains; any private-lead GPU must be offline. It does not
change GPU settings, credentials, or provider resources. Run
`make doctor PREFIX=/absolute/private/prefix` after applying it, then restart
the stack and perform a fresh gate canary. Do not change GPU state to satisfy
the check.

For a fresh installation, the setup runner can apply that same private proposal
after installing any required optional web runtime:

```sh
./sanctum setup --prefix /absolute/private/prefix \
  --proposal /absolute/private/setup-proposal.json \
  --authorize
```

The proposal never contains secrets. `--authorize` reads the Parallel key with
terminal echo disabled and passes it over standard input to the isolated
OpenClaw secret store. For configured Gmail and Calendar accounts it launches
`gog` with `--readonly` and Gmail sending disabled. OAuth browser consent,
Messages Full Disk Access and Open WebUI owner/function enrollment remain
visible owner actions. Re-running with the same proposal digest skips the
configuration amendment; changed proposals still pass through the stopped-
gateway validator and private rollback record.

The runner also checks, without printing secret data, whether exactly one
OpenRouter API-key profile is present for optional hosted Qwen/frontier routes.
It reports a checkpoint when absent; local-only operation does not require that
credential. Provider authentication remains in the isolated OpenClaw auth
store because it may not be copied into a proposal, command line or source.

Project 3G installs Work Mode only through the stopped-gateway, reversible `scripts/upgrade_work_mode.py` amendment. The amendment verifies source and installed receipts, confirms both managed GPU releases are offline with no leases, confirms the independent janitor is loaded, builds and records the exact local runner image, and writes private work profiles outside Git. It installs the complete current Gate runtime closure, including content-telemetry validators and their schemas, so applying Work Mode cannot leave a newly imported Gate dependency absent. It enables PRIVATE_LEAD for explicit signed Work Mode proposals while leaving background GPU autostart disabled. OpenClaw ownership is explicit: `main` remains the system owner and receives ordinary Assistant/local-answer work, while a separate `workmode-broker` agent receives only the five Work Mode semantic capabilities plus the two internal Source-First adapters. The `main` agent pins thinking off both in OpenClaw and in MLX chat-template arguments. Its model catalog also pins a 4,096-token output limit that applies independently to every internal tool-selection and final-answer turn. Gate deliberately omits an outer OpenAI-compatible completion cap because OpenClaw treats that cap as a shared budget across the complete multi-turn agent request. A local answer remains bounded to four minutes, with a 270-second worker ceiling and longer WebUI transport ceilings so the transports cannot cancel MLX first. This per-agent setting does not change the Work Mode broker. The ordinary `/gate` Assistant path and its tool policy otherwise remain unchanged. After an amendment changes the rendered WebUI pipe or guard, replace the imported function in Open WebUI; its database does not automatically reload the on-disk file.

The local Qwen catalog now uses a 24,576-token context window while retaining its 4,096-token per-turn output limit. OpenClaw estimates input conservatively for loopback proxy endpoints; with the previous 16,384-token catalog window, a tool-heavy Gmail search/read exchange could reduce the final generation allowance to one token even though MLX had room to answer. This change does not alter weights, tools, routing, or fallback policy. Existing private Work Mode installations receive the reviewed catalog change through the stopped-gateway amendment, then require a gateway restart.

## Optional migration bindings

The supported amendment schema also accepts `notes_dir`: an existing absolute directory outside source with no symlink components. The Markdown broker uses this owner binding; the default remains prefix-owned notes. GPU `local_port` may select a distinct nonprivileged loopback tunnel port; gateway, model and WebUI ports are rejected. Other GPU policy remains pinned.

`integrations` may include `web` and `mcp`. For web, first run `.venv/bin/python scripts/bootstrap.py web --prefix /absolute/private/prefix`. This installs the reviewed Parallel and Firecrawl 2026.8.1 packages with lockfile integrity and scripts disabled; Firecrawl is retained in the optional runtime payload for rollback compatibility but is not activated. Enroll `PARALLEL_API_KEY` through the isolated OpenClaw secret store using masked input or standard input, never in a proposal or source. The generated provider configuration contains only a store reference. Search uses Parallel and is bounded to six results; the stopped-gateway `web_retrieval.max_results` amendment may lower or restore that bound within one through six. Fetch uses OpenClaw's core guarded HTTP/readability path and remains bounded to 6000 characters. It does not silently switch to Firecrawl when a site rejects extraction. These third-party packages are optional runtime dependencies, separate from the unchanged core runtime pins.

For current public requests, Source-First keeps a public `today` cue in its minimized search query. A single ZIP explicitly supplied for a non-private weather request is retained as the requested location; unrelated numeric identifiers and ZIPs in private context remain omitted. Current-day ZIP weather searches use a short location/forecast query so surrounding instructions cannot dilute retrieval. For that weather case, candidates must identify the ZIP, authoritative forecast pages are tried first, and fetched content must contain a concrete numeric weather condition before evidence is marked adequate. Search/fetch success or generic mentions of forecasting do not suffice: the Mac gate requires a grounded, delivered citation for `WEB_REQUIRED` requests and refuses an unsupported forecast.

For a fetched source that supports only part of a request, the answer prompts require a cited answer for supported facts and an explicit statement that an omitted field is not stated. `GROUNDED` describes support for claims actually made, not completeness of requested fields; the response still records `EVIDENCE_GAP`. Neither local nor hosted reasoning may infer a precipitation probability or no-rain claim merely from sunny conditions. The citation and `WEB_REQUIRED` validation rules are unchanged.

The gate's local-agent handoff narrows the per-turn OpenClaw tool surface for explicit Gmail, Messages, and Calendar requests to the requested source family. A second pre-tool guard blocks a wrong-family call, and no personal-source answer is delivered without a successful requested-family tool call. The Source-First evidence answer has no optional local tools. These restrictions do not grant new capabilities or replace owner permissions.

MCP amendments generate a unique profile identity per prefix and an exact three-tool transport. Run `.venv/bin/python scripts/mcp_gateway.py install --prefix /absolute/private/prefix` with Docker available. It imports only a missing candidate profile and refuses a changed existing profile. The transport verifies the profile before every start, uses the pinned container images, restricts mounts to the prefix input directory, disables container networking and call logging, and retains the Hugging Face per-call disclosure guard. It never reuses the legacy profile identity. No profile or container is started by configuration alone.
