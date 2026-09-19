# Symphony implementation worker charter

The implementation worker is the only role that may modify source, and only
through Symphony when a Linear issue simultaneously has status `Ready for
Agent` and label `symphony`. The human owner alone controls that gate. The
worker uses Sol-medium by default, starts from latest `v1.2-dev`, works on the
deterministic `symphony/<issue-identifier-lowercase>` branch, validates
proportionally, commits, pushes, opens an unmerged PR targeting `v1.2-dev`,
updates the persistent Linear workpad, moves the issue to `Human Review`, and
stops.

The worker may not broaden scope, merge, move work to Done, bypass Human
Review, or weaken privacy, security, authority, validation, or egress
boundaries. Rework resumes the existing issue branch and PR only after human
feedback.

## Hard governor

`sanctum_agents.symphony_supervisor` launches the unmodified external Symphony
engineering-preview binary behind a Sanctum-owned process-group supervisor. It
uses Symphony's loopback state API while keeping a private persistent ledger of
issue first-seen time and per-session high-water marks. This makes the limits
span normal continuation sessions and service restarts rather than relying on
Symphony's per-worker `max_turns` alone.

The first-version implementation envelope is one concurrent issue, one hour
total elapsed time, eight aggregate turns, 500,000 aggregate reported tokens,
two retries, five minutes without an event, one MiB of service output, and a
30-second state-API grace period. A violation terminates the whole process
group, leaves Linear state untouched, exits with code 75, and creates a private
incident receipt containing the exact observed value and limit.

Start only through:

```sh
export SANCTUM_SYMPHONY_BIN=/absolute/path/to/symphony
export SYMPHONY_WORKSPACE_ROOT=/absolute/private/workspace/root
export LINEAR_API_KEY=... # set locally; never paste or commit it
.venv/bin/python -m sanctum_agents.cli symphony-preflight
.venv/bin/python -m sanctum_agents.cli symphony-run
```

`SANCTUM_SYMPHONY_BIN` should point to the inspected external reference checkout
or a reviewed signed standalone binary; no owner-home path is frozen into
source. The supervisor explicitly passes the reference implementation's
required engineering-preview acknowledgement flag. It also uses `mise`
automatically when the selected development binary is adjacent to `mise.toml`.

## Validation profiles

- `docs-config`: focused format/schema/reference checks, `git diff --check`,
  source-freeze checks when applicable, and `make audit`.
- `normal-code`: focused tests plus `make build`, `make test`, and `make audit`.
- `architecture-security`: `make deps`, `make build`, `make test`, `make audit`,
  and focused security/contract tests.

These are minimums; `AGENTS.md` and issue-specific requirements take
precedence. The host router treats WORKFLOW, AGENTS, security files, authority
code, and the supervisor itself as architecture/security work.

## Qualification status

The workflow parses under the inspected Symphony schema with the intended
model, timeouts, concurrency, retry backoff, and active states. A fake-service
integration smoke proves process-group termination and incident creation. A
real controlled Linear issue cannot be created or advanced in this environment
because `LINEAR_API_KEY` / `linear_graphql` access is unavailable; live
qualification therefore remains blocked, and implementation `write_enabled`
stays false.
