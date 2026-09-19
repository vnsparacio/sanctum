# Triage / Chief of Staff charter

Triage keeps the Linear backlog coherent without becoming an authorization
agent. It reads a bounded snapshot of Triage, Backlog, and Watch issues, but may
classify only items currently in Triage. It may leave an item, move it to
Backlog or Watch, cancel deterministic noise, link related issues, or mark a
concrete duplicate. A duplicate is represented as a relation to the retained
issue plus a `Canceled` transition; Sanctum does not invent a Duplicate status.

Triage never adds `symphony`, moves work to `Ready for Agent`, changes product
requirements, implements code, or fabricates evidence. Uncertainty remains in
Triage for owner review. Host validation rejects unknown issue IDs, changes to
non-Triage items, duplicate targets outside the supplied snapshot, duplicate
decisions, malformed output, and any transition outside the management queues.

The default model is Luna-medium. Terra-medium is available only through the
explicit `--escalate` option for an unusually ambiguous or large bounded
snapshot. Run the current read-only shadow path with:

```sh
.venv/bin/python -m sanctum_agents.cli run triage --mode shadow \
  --snapshot tests/fixtures/linear-triage-snapshot.json
```

The fixture path is required until authenticated Linear metadata and snapshot
queries can be qualified. `dry-run` and `shadow` write only private artifacts.
`live` remains disabled. The accepted Luna shadow classified two duplicate
Triage findings against one retained Backlog item in 8.76 seconds, one turn,
and 12,820 reported tokens, with zero Linear writes and no repository mutation.
