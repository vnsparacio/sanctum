# Security Policy

## Supported versions

| Version | Status |
| --- | --- |
| `v1.3-dev` | Active development; security reports are accepted before release. |
| `1.2.x` | Current release line; security fixes are accepted. |
| `1.1.x` and earlier | Historical release lines; no security updates are planned. |

The repository is the source of truth for supported source and packaging. A
private owner deployment can remain on an older version for rollback or
qualification evidence without making that version supported.

## Report a vulnerability privately

Use [GitHub's private vulnerability reporting
form](https://github.com/vnsparacio/sanctum/security/advisories/new) for a
suspected security vulnerability. Private vulnerability reporting is enabled
for this repository, and maintainers coordinate through the resulting GitHub
Security Advisory. A personal email address is not required.

Do not disclose a sensitive finding in a public issue, discussion, pull
request, commit, or other public channel. If a public issue is suitable only
after sensitive details are removed, submit the private report first and
coordinate disclosure with the maintainers.

Include enough information to investigate without including private owner
data:

- the affected version, commit, and component;
- the security impact and the boundary that was expected to hold;
- minimal reproduction steps using synthetic data;
- relevant configuration with credentials, account identifiers, private
  paths, prompts, source bodies, and logs removed; and
- any known prerequisites or mitigations.

Do not test against another person's deployment or access data beyond what is
needed to demonstrate the issue. Please allow maintainers to investigate and
coordinate a fix before public disclosure. The project does not promise a
response or remediation deadline.

## Repository vulnerabilities and private runtime state

This policy covers vulnerabilities in the published repository, including its
source, packaging, default configuration, documentation, and dependency use.
Report a repository weakness that can expose owner-private runtime state, but
describe it with synthetic or redacted evidence.

Owner configuration, credentials, account and contact bindings, model caches,
sessions, approvals, receipts, personal content, and live operational evidence
belong in the owner's external private prefix. They are not repository content
and must not be copied into a report. If you encounter actual owner-private
state, stop accessing it, preserve it privately, and report only the repository
mechanism or boundary failure through the private form. Credential rotation,
account recovery, deployment containment, and incident response remain actions
for the affected owner.

## Security model

Reasoning is replaceable. Authority stays on the Mac. Sanctum is a single-owner
personal system, not a multi-tenant service or a universal defense against
prompt injection.

### Trusted boundary

The authenticated owner and deterministic local code control approvals, data
disclosure, configuration, credentials and tool capability. Web content,
messages, emails, calendar entries, documents, filenames, memory, tool results
and model answers are untrusted data. An instruction embedded in any of these
cannot confer authority.

Risk classification supplies signals. It cannot approve a destination,
declassify data, lower retained high stakes, change provider policy or
authorize a local action. A larger model does not receive greater authority.

### Structural restrictions

- Remote adapters expose no local tools or provider control-plane credentials.
- Messages/Gmail/Calendar mutation is absent. Calendar rejects mutation
  methods.
- Markdown creation is bounded to configured destinations, without
  overwrite/edit/delete.
- File Steward uses approved roots, opaque identifiers and conflict checks.
  Move/rename/undo approval fails closed. No generic deletion/Trash operation
  exists.
- Browser Guard preserves a separate browser identity, blocks evaluate and
  requires approval for consequential interaction.
- The normal tool profile excludes generic exec/process/write/edit. Optional
  tools must be explicitly configured.
- Only predeclared harmless argument forms can be repaired before execution.
  Backend actions are never automatically replayed.

### Integrity and disclosure

The gate verifies a deployment freeze, signed one-use worker requests and
durable replay state. Tickets bind purpose, destination, settings, revision and
expiry. Additional history/attachments require exact disclosure approval.
Initial audit context remains minimal. Hosted transport pins providers, denies
data collection and disables fallback; provider policy is not an independent
retention audit.

The reliability layer validates actual captured schemas against reviewed
runtime hashes. Build fails on unexpected OpenClaw drift. Packaging changes
received an explicit reviewed hash update; production hashes were not
rewritten. Never use a hash refresh as recovery from unexplained drift.

The candidate does not import the owner's credentials, browser profile or
service databases. Preserve GPU allocation intent and cleanup on migration.
Mac/network/provider outage can delay compute deletion and billing can
continue.

## Reviewed dependency exception

The pinned development test runner retains one moderate advisory represented
by two npm entries. Its vulnerable server path is not used by the prescribed
Node test workflow. See [dependency
review](docs/development/dependency-review.md); this is an exposure assessment,
not a patched-dependency claim.
