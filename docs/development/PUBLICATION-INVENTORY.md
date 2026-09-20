# Source publication inventory

Only files listed in SOURCE-MANIFEST.json belong to this candidate. The original private working directory is not the publication target.

| Area | Classification | Included / excluded |
|---|---|---|
| gate, plugins, reliability, router, host, scripts | PUBLIC SOURCE | Reviewed runtime/operator source; no provider resources or credentials |
| tests and explicitly selected fixtures | PUBLIC SYNTHETIC TEST DATA | Fictional contact/source examples; no historical private corpus |
| docs and root Markdown | PUBLIC DOCUMENTATION | Maintained candidate docs and dated aggregate history |
| config, gate SETTINGS, MCP profile, package lock | LOCAL CONFIG TEMPLATE / PUBLIC BUILD CONFIG | Generalized paths/resources; exact dependency pins |
| node_modules, .venv, dist, bytecode | GENERATED / REBUILDABLE | Excluded from source/archive |
| .local, state, logs, databases, receipts | LOCAL RUNTIME STATE | Excluded and private |
| OAuth, Keychain, SSH, approval keys, tokens | SECRET / CREDENTIAL | Never imported into candidate source |
| attachments, source histories, browser state | PERSONAL / PRIVATE DATA | Excluded |
| weights, embeddings, benchmark/training corpora | LARGE MODEL / CACHE / PRIVATE DATA | Excluded |
| Original reports, backups and development runs | HISTORICAL EVIDENCE | Excluded; aggregate reviewed history only |

Automated scanning found no candidate credential-pattern, private-artifact or documentation-link findings. Contextual review removed the original owner path, embedded contact aliases and private volume reference. npm lock entries contain no local file dependencies. This is a bounded audit, not proof against every possible secret format.

The public release starts with clean initial history from this allowlisted source. Private development archaeology is not imported. Dependencies retain upstream licenses; Sanctum source now uses Apache-2.0; external runtimes retain separate terms. Review the historical V1 acceptance record and the current release guide before publication.
