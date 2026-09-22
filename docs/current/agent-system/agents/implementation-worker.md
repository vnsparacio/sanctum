# Symphony implementation worker charter

The implementation worker is the only role that may modify source, and only
through Symphony when a Linear issue simultaneously has status `Ready for
Agent`, label `symphony`, and exactly one of `agent-standard` or `agent-deep`.
The human owner alone controls those gates. The standard worker uses Sol-medium;
the deep worker uses Astra-high only after an owner-routed model-reasoning
escalation. Both start from latest `v1.3-dev` and work on the
deterministic `symphony/<issue-identifier-lowercase>` branch, validate
proportionally, asks the host Git control plane to commit and push, opens an
unmerged PR targeting `v1.3-dev`,
updates the persistent Linear workpad, moves the issue to `Human Review`, and
stops.

The worker may not broaden scope, merge, move work to Done, bypass Human
Review, or weaken privacy, security, authority, validation, or egress
boundaries. Rework resumes the existing issue branch and PR only after human
feedback.

## Implementation backend selection

The reviewed `config/agents.json` `symphony.implementation_backend` value
selects exactly `codex` or `work-mode`. `codex` retains `WORKFLOW.md` and
`WORKFLOW.deep.md`. `work-mode` resolves only the separately configured
`work_mode_workflow` and `work_mode_deep_workflow` paths; those workflows are
not selected by issue content, labels, or model output. Unknown values and
unsafe workflow paths fail configuration loading. Backend selection changes
only the worker workflow. Symphony continues to own the execution gate,
workspace preparation, aggregate budgets, validation and Git control planes,
and the mandatory Human Review stop.

## Hard governor

`sanctum_agents.symphony_supervisor` launches the unmodified external Symphony
engineering-preview binary behind a Sanctum-owned process-group supervisor. It
uses Symphony's loopback state API while keeping a private persistent ledger of
issue first-seen time and per-session high-water marks. This makes the limits
span normal continuation sessions and service restarts rather than relying on
Symphony's per-worker `max_turns` alone.

The standard implementation envelope is one concurrent issue, six hours total
elapsed time, 40 aggregate turns, 8,000,000 aggregate reported tokens, three
retries, 16 MiB of service output, and a 30-second state-API grace period. The
deep envelope is eight hours, 60 aggregate turns, and 12,000,000 tokens with
the same concurrency and retry bounds. Symphony separately owns a 60-minute
turn timeout and 15-minute worker silence timeout. A violation terminates the
whole process group, leaves Linear state untouched, exits with code 75, and
creates a private incident receipt containing the exact observed value and
limit.

Symphony's blocked state is also terminal for the current supervisor
invocation. A deterministic environment/control-plane blocker is recorded
once, requests operator input, and cannot consume continuation or retry loops.

Start only through:

```sh
export SANCTUM_SYMPHONY_BIN=/absolute/path/to/symphony
export SYMPHONY_WORKSPACE_ROOT=/absolute/private/workspace/root
export LINEAR_API_KEY=... # set locally; never paste or commit it
.venv/bin/python -m sanctum_agents.cli symphony-preflight
.venv/bin/python -m sanctum_agents.cli symphony-run
```

Pass `--worker-class deep` to both commands only for an issue carrying
`agent-deep`. Standard is the default. Both classes share the same exclusive
lock, so implementation concurrency remains one.

`SANCTUM_SYMPHONY_BIN` should point to the inspected external reference checkout
or a reviewed signed standalone binary; no owner-home path is frozen into
source. The supervisor explicitly passes the reference implementation's
required engineering-preview acknowledgement flag. It also uses `mise`
automatically when the selected development binary is adjacent to `mise.toml`.

## Git authority boundary

Codex remains in `workspace-write`; direct `.git` mutation is intentionally
unavailable. Trusted lifecycle hooks run the reviewed broker before each turn
to fetch only `origin/v1.3-dev` and establish or validate the deterministic
issue branch. The worker receives only `git_workspace_status`,
`git_commit_issue_changes`, `git_push_issue_branch`, and
`git_reconcile_operation`, plus the distinct bounded
`github_ensure_issue_pull_request` handoff. Every mutating call uses a stable
operation ID; an uncertain commit, push, or PR result must be reconciled and
must not be replayed under a new ID. There is no arbitrary Git/GitHub
argument tool, force push, branch deletion, merge, protected-branch write, or
caller-selected repository/remote/base/head.

The broker executable is the source-manifest-verified canonical copy, not the
copy inside the issue workspace. It binds the real workspace path, device,
inode, in-place Git directory, issue identifier, canonical remote, accepted
base, and deterministic branch into a private host lease. Commit accepts only
explicit relative nonsymlink paths. Push is a normal push of the current issue
branch to origin. Pending commit/push receipts live under the external private
agent prefix; an uncertain result is reconciled against actual Git state and
is never blindly replayed.

Git subprocesses receive an allowlisted environment. Tracker credentials are
removed by Symphony, credential values are never returned, and the fixed local
GitHub CLI plus its private external authentication directory may be used only
by the broker's bounded remote read/push/PR operations. The worker sandbox
cannot read that directory. Repository hooks are disabled and repository code
is not executed by the broker.

## Validation profiles

- `docs-config`: focused format/schema/reference checks, `git diff --check`,
  source-freeze checks when applicable, and `make audit`.
- `normal-code`: focused tests plus `make build`, `make test`, and `make audit`.
- `architecture-security`: `make deps`, `make build`, `make test`, `make audit`,
  and focused security/contract tests.

These fixed commands execute through a manifest-verified host runner bound to
the leased issue workspace. The worker cannot supply an arbitrary command or
receive credentials. Receipts bind the operation to the current Git and file
state. These are minimums; `AGENTS.md` and issue-specific requirements take
precedence. The host router treats WORKFLOW, AGENTS, security files, authority
code, and the supervisor itself as architecture/security work.

## Qualification status

The workflow parses under the inspected Symphony schema with the intended
model, timeouts, concurrency, retry backoff, and active states. Synthetic
integration tests prove process-group termination, incidents, explicit resume,
validation isolation, and Git/PR reconciliation. Live TTE-9/TTE-14 history is
diagnostic evidence, not post-change qualification. A new controlled smoke
must reach Human Review before enabling continuous implementation; until then,
implementation `write_enabled` stays false.
