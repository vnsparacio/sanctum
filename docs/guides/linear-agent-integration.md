# Linear agent integration

This guide reproduces Sanctum's Linear metadata qualification and bounded
management-agent activation. It does not authorize implementation. Only the
owner may set both `Ready for Agent` and `symphony`, and only the owner may
merge or move work to Done.

## Prerequisites

- Run from the canonical Sanctum checkout on an issue-scoped branch based on
  the current `origin/v1.2-dev`.
- Install the pinned dependencies with `make deps`; reuse an existing healthy
  `.venv` rather than deleting it.
- Create the project, workflow states, labels, `source` label group, and issue
  templates named in `tests/fixtures/linear-metadata.json`.
- Keep Repo Steward, Product Scout, and Triage writes and schedules disabled
  until metadata and shadow checks pass for a new workspace.

The configured project slug is workspace-specific. A different project needs a
reviewed update to `config/agents.json` and its synthetic metadata fixture. Do
not rename live objects or edit a captured snapshot to hide a mismatch.

## Establish authentication without echoing it

In zsh, enter the token into the shell that will run the checks:

```sh
read -rs "LINEAR_API_KEY?Linear API key: "
printf '\n'
export LINEAR_API_KEY
test -n "$LINEAR_API_KEY" && printf 'Linear authentication is available.\n'
```

The token must remain in the owner-controlled environment. Never put it in a
prompt, issue, source file, `.env`, command argument, generated snapshot, or
log. Do not create a raw-token GraphQL helper.

Codex desktop automations inherit the desktop app's environment. If the app is
launched from a shell, export `LINEAR_API_KEY` and `SANCTUM_AGENT_PREFIX` before
launching it. If the Mac session supplies GUI environment variables another
way, keep that configuration outside the repository. Fully quit and relaunch
Codex after changing its launch environment.

## Capture and validate metadata

The capture command is read-only. It performs two narrow GraphQL queries,
requires exactly one project team, checks every required state, label, label
group, and issue template, then atomically writes IDs and names only:

```sh
.venv/bin/python -m sanctum_agents.cli linear-metadata-capture
.venv/bin/python -m sanctum_agents.cli linear-metadata-check
.venv/bin/python -m sanctum_agents.cli validate-config
.venv/bin/python -m sanctum_agents.cli models-check
.venv/bin/python -m sanctum_agents.cli schedule-plan
```

The result is
`$SANCTUM_AGENT_PREFIX/state/linear-metadata.json`, with its directory mode
`0700` and file mode `0600`. Capture stops before replacing the file if a
required name is missing, duplicated, attached to the wrong label group, has
the wrong template type, or would require unreviewed pagination.

## Prove read-only behavior in shadow mode

```sh
.venv/bin/python -m sanctum_agents.cli run repo-steward --mode shadow
.venv/bin/python -m sanctum_agents.cli run product-scout --mode shadow
.venv/bin/python -m sanctum_agents.cli run triage --mode shadow \
  --snapshot tests/fixtures/linear-triage-snapshot.json
```

Review the private artifacts and JSONL logs. A valid shadow run performs zero
external writes and leaves the repository unchanged. Stop if evidence is
invented, a budget stop is reported as success, or a role proposes either
implementation gate.

## Activate one role at a time

Activation is a reviewed source change, not a runtime toggle. For each role:

1. Enable only that role's `write_enabled` setting.
2. Keep its creation cap at one for the initial live period.
3. Run one manual live smoke.
4. Inspect the Linear issue and the private run artifact.
5. Replay the same proposal and confirm it resolves as a duplicate.
6. Enable the matching schedule only after the smoke is accepted.

The reviewed live commands are listed in `config/schedules.json`. Triage
captures a fresh authenticated snapshot automatically, considers only
management states with one approved management source label, and fails closed
instead of silently truncating a paginated result.

Management roles may create or organize findings only. They cannot add
`symphony`, move an issue to `Ready for Agent`, modify source, merge, or move an
issue to Done.

## Install Codex desktop schedules

Create one automation for each enabled entry in `config/schedules.json`, using
the saved local Sanctum project and the configured America/Los_Angeles time.
Each automation should run only the listed command from the repository root,
remain quiet on a non-actionable success, and report failures, budget stops,
candidate artifacts, management changes needing review, or required owner
action. Do not override the centrally configured model.

Local automations require the desktop app and computer to be available at run
time. See the official [Codex Automations documentation](https://learn.chatgpt.com/docs/automations?surface=app)
for current scheduling behavior.

## Verify and roll back

After activation, run:

```sh
make build
make test
make audit
git diff --check
```

To stop future management writes, pause the desktop automations first, then
make a reviewed source change that disables the affected schedules and
`write_enabled` flags. Do not delete or rewrite live issues as rollback.

Symphony is a separate owner checkpoint. A passing metadata capture and active
management schedules do not authorize it. Before the first controlled smoke,
the owner must select a tiny issue, personally apply both execution gates, and
run the separate `symphony-preflight` procedure in the agent-system runbook.
