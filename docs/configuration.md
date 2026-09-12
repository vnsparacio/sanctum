# Configuration and secrets

`gate/SETTINGS.json` is a reviewed template. Setup binds its Python, gate, state and config paths in a private prefix and computes a deployment-specific freeze. The unrendered template is not an executable production configuration. Source integrity is checked before rendering.

The generated environment defines OpenClaw state/config, socket cache, contact mapping, file roots, gateway/MLX ports and the local auth database. It does not redefine the user's HOME. Model/provider IDs, price ceilings, disclosure expiry and safety policy retain their dated production values. These values are version pins, not current catalog/pricing promises.

`config/openclaw.json` contains a new gateway token and is mode 0600. Gate authority material, contacts, accounts and receipts remain local. OpenRouter credentials must belong in the isolated OpenClaw auth store; direct OpenAI retention authorization stays false. Keychain references and a dedicated SSH path are configured locally; do not copy production secret values into the source tree.

The first candidate configuration is intentionally minimal: exact utilities are available, optional tool integrations need reviewed setup, GPU autostart is false, and contact aliases are empty. File root configuration accepts only the established scope names and absolute paths; model arguments cannot change those roots.

Changed config/settings invalidate integrity. The current setup refuses to overwrite them. Use `scripts/configure.py --proposal` for supported integration/contact/root/account/GPU reference changes. It validates a narrow schema, requires a stopped gateway, writes a private rollback transaction before modification and explicitly updates only the affected hashes. Unsupported policy/provider changes require a separate reviewed release. Do not edit hashes merely to suppress a failure. Environment changes controlling authority paths are operator decisions and must be kept outside model/tool input.
