# Repo Steward charter

The Repo Steward is a read-only engineering-health observer. It uses the
centrally configured Terra model to turn bounded repository evidence into
candidate Engineering Findings. It does not edit the repository, authorize
implementation, add `symphony`, move work to `Ready for Agent`, or merge.

## Operating modes

- `dry-run` and `shadow` produce a local artifact under the private agent
  prefix and make zero Linear writes.
- `live` remains fail-closed until the shadow output is accepted, Linear
  metadata has been qualified, and `write_enabled` is explicitly changed.
- Weekday runs are incremental from the last successfully stored commit.
  `--deep` is reserved for the optional weekly review.

Run a shadow pass with:

```sh
.venv/bin/python -m sanctum_agents.cli run repo-steward --mode shadow
```

The role has one exclusive lock, a hard process-group wall-clock limit, a
bounded output buffer, model token and turn counters when emitted by Codex,
repository/file/marker caps, a finding cap, deterministic fingerprints, and a
private structured log. Model output is schema constrained and then validated
again by host code. Unknown evidence, unknown labels, duplicate references, or
malformed fields fail the run rather than creating a finding.

The current collector prioritizes tracked changes since the last successful
run, explicit workflow-safety checks, and bounded debt-marker/test-gap evidence.
The hard total-runtime check evaluates the complete effective control: the
workflow declaration, a positive implementation timeout, and the persistent
supervisor ledger and enforcement for both running and retrying work. No single
wording match is treated as proof that the control is absent.
Python debt markers are collected from comment tokens so fixture strings do not
become repository-health evidence.
GitHub/CI and Linear backlog evidence belong to the live qualification step;
absence of authenticated Linear access must never be interpreted as an empty
backlog or successful duplicate search.

## Shadow acceptance

Acceptance requires zero repository changes, zero Linear writes, a private
artifact and log, a supported configured model, a completed bounded run, and
only concrete evidence-linked findings. A checked-in sanitized example lives
at `docs/current/agent-system/shadow/repo-steward.json`; the original artifact stays outside Git.
