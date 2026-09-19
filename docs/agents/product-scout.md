# Product Scout charter

The Product Scout is a read-only external technology researcher. It uses the
centrally configured Terra model and Codex-native web search to propose Product
Discovery items grounded in bounded sources. It does not edit the repository,
authorize implementation, add `symphony`, change product requirements, or
merge.

The default Monday/Wednesday/Friday envelope is five discoveries, eight
sources, one model turn, a 15-minute hard deadline, and 150,000 reported
tokens. The source packet may contain community discussion, but every discovery
must also cite at least one primary, paper, repository, release-note, or security
research source. Host validation rejects private/local URLs, duplicate source
identities, unsupported labels, missing Sanctum connections, and malformed
model output.

Run a shadow pass with:

```sh
.venv/bin/python -m sanctum_agents.cli run product-scout --mode shadow
```

`dry-run` and `shadow` make no Linear writes. `live` remains fail-closed until
the shadow result is accepted, Linear metadata and templates are qualified,
duplicate-search behavior is proven, and `write_enabled` is explicitly changed.
Deduplication fingerprints normalized titles plus source URLs and persists only
in the external private runtime prefix.

The first live shadow attempt demonstrated the token governor by stopping at
125,687 reported tokens against the original 120,000 ceiling. After narrowing
the envelope to eight sources and five findings and setting a measured 150,000
ceiling, the accepted shadow completed in one turn, 43.76 seconds, and 68,457
reported tokens. The checked-in sample is sanitized; original artifacts and
logs remain private.
