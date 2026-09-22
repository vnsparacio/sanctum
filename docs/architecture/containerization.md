# Container and host boundary

V1 is hybrid. MLX, TCC-sensitive Messages, Keychain, private sockets, local approvals, browser identity and GPU cleanup belong on the Mac in the validated design. OpenClaw and WebUI remain host services because the current pipe invokes a host bridge with private gateway identity.

The existing curated Docker MCP surface is preserved in a static profile: time, approved public Hugging Face search and scoped Markdown conversion. The profile's file input mount is generated from the selected prefix and read-only. No dynamic catalog management, broad home mount, Docker socket, privileged container or generic shell is model-visible.

V1.3 Work Mode repository commands cross a separate host-owned OCI boundary.
The model-facing request contains a reviewed operation name and an explicit
repository-relative working directory; it must also repeat the fixed offline
network, workspace/tmp mount, scrubbed environment, and no-credential policy.
Missing or widened fields fail closed. A private profile—not issue text or the
model—maps the operation to an argument vector and selects a digest-pinned
image, local container socket, and non-root identity. The container receives
only the task workspace and bounded tmpfs: it receives no host home, Keychain,
Docker socket, inherited environment, credentials, arbitrary host cwd, or
additional mount. The API exposes neither an argv field nor a shell string.

`compose.yaml` defines an optional, digest-pinned time service with no network, a read-only filesystem, dropped capabilities and a temporary /tmp. It is an MCP reference process, not an HTTP endpoint or a whole-system deployment. Run it only when wiring the static MCP gateway. The profile's other providers require separate explicit configuration.

Do not containerize WebUI merely by changing its image: host bridge execution, authentication and disclosure behavior must be preserved and tested first. No all-container clean install is claimed. GPU inference remains loopback on the remote worker, reached through the Mac's validated SSH tunnel.

## Qualification scope

No complete runtime image is distributed. The optional digest-pinned MCP time reference was previously started with network disabled; Compose is checked again in final source-copy verification. An unavailable Docker socket was simulated without stopping the owner’s daemon. This does not establish full live MCP catalog acceptance or containerize macOS authority/MLX. Bundled binary images require a separate license redistribution review.
