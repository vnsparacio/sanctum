# Secret scanning and push protection

Sanctum uses two independent controls: GitHub secret scanning and push
protection at the repository boundary, and the repository-owned publication
audit run by `make audit`. Neither control proves that a file is safe, and one
must not be disabled because the other passes.

## Live GitHub control

Repository settings and alerts are live provider state. Checked-in files and
offline tests cannot enable or prove them. A repository administrator must
verify **Settings > Security > Advanced Security** and the repository's
**Security > Secret scanning** alert view. For this public repository, enable
secret scanning and repository push protection wherever GitHub offers the
controls, then review both open and closed alerts without copying secret values
into source, issues, logs or test fixtures.

Record only the setting state, alert number, provider/type, affected path and
resolution. A genuine exposed credential must be revoked or rotated before its
alert is closed; deleting the current file does not remove it from Git history.
Do not create a real credential or commit a provider-shaped value to test the
feature. GitHub's published supported-pattern list and behavior are live
provider contracts and can change independently of this repository.

## Repository publication audit

`scripts/audit.py` scans every source file and reports only a relative filename
and finding category, never the matching value. CI runs it through `make audit`.
The local rules cover:

- RSA, EC, OpenSSH, generic PKCS#8 and PGP private-key headers;
- current and legacy recognizable GitHub token prefixes;
- Linear API and OAuth token prefixes;
- recognizable OpenAI, AWS access-key-ID and Firecrawl key prefixes;
- long assignments to Sanctum's known credential variables, including Linear,
  GitHub, OpenAI, AWS, Runpod, Splunk, Parallel and Firecrawl variables;
- committed environment files other than `.env.example`, private-key/artifact
  extensions, symlinks, large files and owner-home paths.

Tests construct nonfunctional samples from fragments at runtime so the
repository never contains a complete provider-shaped fixture. Documentation
placeholders such as `...`, `<token>` and `YOUR-API-KEY` remain allowed.

## Detection limits

GitHub scanning is strongest for supported, recognizable provider formats.
Push protection covers only a subset of secret-scanning patterns and can skip
or time out on unusually large pushes. Some paired credentials, such as AWS
access-key IDs and secrets, require both parts in the same file. Generic
password detection, validity checks, custom patterns and provider coverage
depend on repository type, account plan and GitHub's current configuration.

The local audit intentionally uses deterministic patterns and does not validate
credentials or send them to a provider. Opaque values without a stable prefix
remain detectable only when assigned to a known credential variable or stored
in a blocked file type. In particular, arbitrary Splunk, Runpod and Parallel
values, legacy provider tokens, encoded/encrypted values, split strings,
dynamically assembled values and renamed variables can evade both controls.
False negatives and false positives remain possible.

Therefore credentials stay in the external private prefix, Keychain or the
isolated secret store. Before every publication, inspect the diff and staged
file list, run `make audit`, and treat any GitHub alert or push-protection block
as a stop condition. Never bypass a block merely because a value is described
as a test value; use a non-provider-shaped synthetic fixture instead.
