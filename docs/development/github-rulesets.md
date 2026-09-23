# GitHub protected-branch ruleset

The active repository ruleset named `Protect main and v1.3-dev` covers exactly
`main` and `v1.3-dev`. Its reviewed source is
`.github/rulesets/protected-branches.json`.

For ordinary actors, the ruleset:

- requires every change to arrive through a pull request;
- prevents branch deletion;
- blocks force pushes; and
- requires every current GitHub Actions CI check to complete successfully; and
- requires review conversations to be resolved before merge.

## Required CI checks

The required status-check rule is deliberately loose: a pull request does not
have to be rebased onto the latest target-branch commit, but every check below
must report a successful conclusion for the pull request's tested commit before
the normal merge path is available. A failed or pending required check blocks
that path.

The required contexts are the GitHub Actions job names emitted by
`.github/workflows/ci.yml`:

- `Python format`
- `Python lint`
- `Plugin build and manifests`
- `Contracts / Gate JavaScript`
- `Contracts / Gate Python`
- `Contracts / Reliability`
- `Contracts / MCP containment`
- `Contracts / Owned plugins`
- `Contracts / Release and portability`
- `Contracts / Agent management`
- `Publication, source integrity, and compose`

Each context is restricted to the GitHub Actions app (integration ID `15368`),
as observed on the current `v1.3-dev` check runs. The repository contract test
derives job and matrix names from `ci.yml` and requires an exact set match with
the ruleset. Adding, removing, or renaming a CI job therefore fails validation
until the required-check policy is reviewed and updated in the same change.

Prefer keeping a job's public `name` stable while restructuring its steps. If a
check must be renamed, use staged pull requests: first emit both old and new
names, then update the live ruleset after the new check has reported
successfully, and only then remove the old name. This avoids a window where a
renamed required check is never reported and every ordinary merge remains
pending.

The pull-request rule intentionally requires zero approving reviews. Sanctum is
a single-owner repository: requiring another approval would make the existing
feature-branch-to-PR flow impossible without using the emergency bypass on
every merge. The owner still reviews and merges each implementation PR, as
required by `AGENTS.md`; automation may prepare an unmerged PR but may not
merge it or move the associated Linear issue to `Done`.

## Emergency bypass

The only bypass entry is GitHub's built-in repository `Admin` role
(`RepositoryRole` ID `5`) in `always` mode. On this personal repository that is
Vince, the repository owner. The bypass exists for emergency recovery, such as
repairing an otherwise unusable protected branch. It is not the ordinary merge
path.

No GitHub App, integration, deploy key, write role, or maintain role has a
bypass entry. Adding one would let automation or another ordinary actor evade
the PR path and requires a separately reviewed policy change.

When the bypass is used, record the reason and affected commit in the relevant
Linear issue or release evidence. Restore the normal feature-branch and PR flow
immediately afterward. Do not disable the ruleset or broaden the bypass list as
a shortcut.

## Installation and verification

Repository rulesets are live GitHub settings; committing the reviewed JSON does
not install them. A repository administrator must create or reconcile the
ruleset in **Settings > Rules > Rulesets**, keep enforcement set to `Active`,
and compare every field with the reviewed JSON. GitHub exports omit bypass
actors, so verify the `Admin` bypass separately in the UI.

After installation, verify through GitHub's repository rules API that:

1. the ruleset is active and its include list is exactly `main` and
   `v1.3-dev`;
2. deletion, non-fast-forward updates, and pull-request rules are present;
3. all eleven required status-check contexts match the list above, are sourced
   from GitHub Actions integration `15368`, and strict/up-to-date mode is off;
4. the only bypass actor is repository role `Admin`; and
5. a normal feature branch can be pushed and opened as a PR to `v1.3-dev`,
   while a non-admin direct update, force push, or deletion is rejected.

Before declaring live enforcement complete, also confirm with ordinary-actor
test pull requests that one failing required check and one pending required
check each keep the merge control blocked. Passing checks do not merge the pull
request automatically: the owner still performs the explicit merge.

The repository contract tests validate the checked-in policy. Live GitHub
inspection is required as separate evidence because an offline test cannot
prove provider-side enforcement.
