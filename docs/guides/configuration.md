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

Project 3G installs Work Mode only through the stopped-gateway, reversible `scripts/upgrade_work_mode.py` amendment. The amendment verifies source and installed receipts, confirms both managed GPU releases are offline with no leases, confirms the independent janitor is loaded, builds and records the exact local runner image, and writes private work profiles outside Git. It enables PRIVATE_LEAD for explicit signed Work Mode proposals while leaving background GPU autostart disabled. OpenClaw ownership becomes explicit: `main` remains the system owner and receives ordinary Assistant/local-answer work, while a separate `workmode-broker` agent receives only the five Work Mode semantic capabilities plus the two internal Source-First adapters. After an amendment changes the rendered WebUI pipe or guard, replace the imported function in Open WebUI; its database does not automatically reload the on-disk file.

## Optional migration bindings

The supported amendment schema also accepts `notes_dir`: an existing absolute directory outside source with no symlink components. The Markdown broker uses this owner binding; the default remains prefix-owned notes. GPU `local_port` may select a distinct nonprivileged loopback tunnel port; gateway, model and WebUI ports are rejected. Other GPU policy remains pinned.

`integrations` may include `web` and `mcp`. For web, first run `.venv/bin/python scripts/bootstrap.py web --prefix /absolute/private/prefix`. This installs only the reviewed Parallel and Firecrawl 2026.8.1 packages with lockfile integrity and scripts disabled. Their archive identities match the legacy qualified installation. Enroll `PARALLEL_API_KEY` through the isolated OpenClaw secret store using masked input or standard input, never in a proposal or source. The generated provider configuration contains only a store reference. Search remains Parallel, bounded to one result by default; the stopped-gateway `web_retrieval.max_results` amendment may raise it no higher than six for Source-First ranking. Fetch remains Firecrawl, bounded to 6000 characters. These third-party packages are optional runtime dependencies, separate from the unchanged core runtime pins.

MCP amendments generate a unique profile identity per prefix and an exact three-tool transport. Run `.venv/bin/python scripts/mcp_gateway.py install --prefix /absolute/private/prefix` with Docker available. It imports only a missing candidate profile and refuses a changed existing profile. The transport verifies the profile before every start, uses the pinned container images, restricts mounts to the prefix input directory, disables container networking and call logging, and retains the Hugging Face per-call disclosure guard. It never reuses the legacy profile identity. No profile or container is started by configuration alone.
