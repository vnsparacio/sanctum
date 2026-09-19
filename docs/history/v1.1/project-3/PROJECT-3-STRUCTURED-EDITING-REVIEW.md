# Project 3 structured editing — independent offline review

Date: 2026-09-17. Verdict: **PASS for the offline editing boundary, with the explicit operational limitations below.** This is not acceptance of the complete repair: an observed successful canary and the unchanged 11-case qualification remain separate gates. No inference, provider call, GPU operation, installation, private runtime mutation or dependency installation was performed by this reviewer.

## Reviewed identity and scope

The review began on `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`, with the existing substantial dirty Project 3 working tree. It did not treat all changes against HEAD as this repair. The privately retained starting source inventory was compared to current bytes: 23 existing files changed, all within the declared repair paths; three declared files were new (`gate/src/worktree_edit.py` and the two editor test files). The source freeze is a separate artifact. No unrelated source modification was introduced by the reviewer; this report is its only repository addition.

Reviewed source freeze before this report: `454bd98e7d86b56a9a10c62581c09ed5f6e2785ab3dc3aba635f4e1b247e55dd`.

| Source | SHA-256 |
| --- | --- |
| `gate/src/worktree_edit.py` | `b8010ca1bc6ff5af7f5e51e5b7c26003ec2fdbc4f6f9e31b59974d869019e9fa` |
| `gate/worker.py` | `d72044bc2b07c72eb728d2835fa0915edf59ba3c0d95a37667c11d56b0b82a27` |
| `gate/plugin/work-command.mjs` | `498aa14d0b8213db0d036b11992212fb913657c26dd6346b99d06d896ddef433` |
| `gate/plugin/work-mode.mjs` | `07800ff8bce0dcc53e1973b18093f020764aeb6ed252fb284ab87557753f7a13` |
| `gate/src/authority.py` | `0dce16f23ce536f51e2f99768f5f5d87d8e4fec8d401daa547f5afa2e58410f1` |
| `gate/plugin/workspace-tools.mjs` | `23f7da989286bb7872fc2acbfcd282f421f486d50bde1ffef94091fb0f7666ee` |
| `scripts/configure.py` | `9f6d7faca4fa961666b7beae5133a941489dfae99f733b759acaa48225194363` |
| `reliability/runtime-pins.json` | `36a8a6e22d1c3f1cf85cd2e3b79fb15d4519d418d0519df7d0b977d1af0f9ff2` |

Later report inclusion or commits may change the source-freeze digest; these file identities identify the reviewed implementation independently. The implementing agent reported the initial 475-test baseline and 505 passing packaged tests before the review findings. Those are implementation-run evidence, not independently repeated full-suite counts. This reviewer ran the narrower independent and packaged checks recorded below.

## Findings discovered and repaired during review

**R1 — post-mutation persistence failure could be reported as not started. Closed.** The original `locked()` context persisted `editor.json` after `_apply()` returned. An injected `OSError` only when saving `editor.json` produced changed candidate bytes and an edit receipt, but escaped `apply()`. The worker returned `UNAVAILABLE`, and the work-command adapter classified every non-OK response as `NOT_STARTED`. This lost execution uncertainty.

The repaired `apply()` covers context-manager persistence and returns `EDIT_STATE_UNAVAILABLE / COMPLETION_UNKNOWN` if an edit succeeded or was already uncertain. The identical independent injection now returns that result while retaining the observed changed file. Non-OK worker responses and missing/failed gateway mutation responses are conservative unknown outcomes; the Work Mode invoke wrapper also catches fetch/JSON response failures for this mutation. The coordinator stops on unknown execution before egress or another model action. Ordinary backend refusal envelopes with an explicit `NOT_STARTED` result preserve that state.

**R2 — supported workspace routes were not all serialized against editing, and post-write checking could miss an unrelated concurrent change. Closed within the supported-writer boundary.** Initially, an injected change to the other mutable file immediately after the final pre-write inventory returned `OK`. Scoped integrity alone accepts authorized mutable-file changes and could not prove the actual post-state was the approved candidate.

The worker now shares the editor task lock for listing, internal patches, commands, integrity, original acceptance execution and cleanup; reads, observation confirmation and edits acquire it internally. A concurrent independent test held the lock and attempted each of the six outer worker routes. None entered its implementation until release. Candidate command execution copies inputs into a disposable container volume and does not expose a live host workspace mount. The editor also computes the exact expected full content inventory and compares the post-write inventory. Repeating the unrelated-file injection now returns `EDIT_APPLY_RACE / COMPLETION_UNKNOWN`.

The residual trusted-owner race is explicitly described below; these repairs do not turn POSIX rename into a compare-and-swap primitive.

## Boundary conclusions

- Normal tool registration, capability manifests, semantic schemas, preflight artifacts and default task selection expose `worktree_edit`, with no `worktree_patch`, file-create, file-delete, replace-file fallback or edits array. Internal signed patch handling remains present for trusted host use and shares the lock. No local 4B/helper-model editing path was added.
- The exact fields are `path`, nonempty `old_text`, and possibly empty `new_text`; task identity is supplied by the host. Extra fields fail. JavaScript transport/binding/reliability and Python application preserve whitespace, tabs, escapes, Unicode and CRLF. UTF-8 byte ceilings are enforced again on the host, independently of schema string-length limits.
- Pending reads alone do not authorize edits. Host confirmation follows result egress and the bounded-envelope check; withheld or omitted results cannot create a valid observation. Confirmation binds the path and host token. Observations include task/workspace, generation, full-file digest, type/size, visible byte range and exact visible text. Editing requires a matching current digest and a complete observed target string. Generation is recorded, while per-file digest freshness permits reading two files and editing them sequentially.
- Path traversal, Git internals, noncanonical path forms, symlink components, nonregular files, multiple hard links, unsupported encodings, protected paths and out-of-scope paths fail closed. Actual protected bytes/inodes are checked before and after mutation. The existing authenticated original-test proof and evaluator/reviewer implementation were not redesigned.
- The replacement counts overlapping occurrences and accepts exactly one. Candidate construction is only the original prefix plus the exact model `new_text` plus the original suffix. There is no fuzzy match, regex/AST fallback, whitespace repair or host-authored replacement. No-op and size refusals are explicit.
- Git renders the two byte strings in a separate temporary directory with fixed configuration and external diff/textconv disabled. The actual-mutation assessment receives that canonical diff; its allow result is bound to the diff digest. Independently reverse-applying and reapplying emitted diffs reproduced the exact preimage and candidate, including non-ASCII, CRLF, escapes and absent final newline.
- Semantic mismatch/staleness/unobserved failures remove edit capability from the next decision surface until a confirmed same-path read. Listing or another-file reads do not clear recovery. Blind proposals are rejected without execution and remain subject to the existing bounded correction policy. Successful edits invalidate that path's observation and require tests; another same-path mutation requires a fresh read.
- Success receipts expose bounded digests and facts, not source. Private proposal/preimage/diff artifacts enable later independent reconstruction. Failure results do not inject source or arbitrary exception text. The reported zero invention/fuzzy counts are supported by source inspection and independent reconstruction, not by trusting those numeric fields alone.

## Independent verification

All behavioral fixtures use disposable temporary directories and synthetic source. Temporary harnesses are retained under `/tmp/sanctum-structured-editor-independent-20260917`; they are not runtime inputs.

| Check | Result |
| --- | --- |
| `independent.py`: eight independently authored cases | PASS: exact Git roundtrip without final newline; canonical-authority digest mismatch; protected tampering; cross-path observation-token refusal; truncated multibyte observation; content-safe receipts and exact transform; symlink parent; per-file invalidation/sequential files. |
| `signed.py`: actual `authority.authorize` → `worker.execute` | PASS: unconfirmed source refusal, confirmed exact edit, nonce replay refusal, signature tampering refusal and extra-field rejection. No live worker service or credentials used. |
| `locking.py`: six interleavings through worker entry | PASS: each supported route blocks behind the task edit lock and proceeds after release. |
| `persist-probe.py`: private state write failure after mutation | Reproduced original defect; repaired result is `EDIT_STATE_UNAVAILABLE / COMPLETION_UNKNOWN`. |
| `probe.py`: adversarial filesystem interleavings | Unrelated post-inventory mutation is now detected as unknown. Noncooperating trusted-owner target/parent mutations retain the limitations below. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_worktree_edit.py'` | 27 PASS on the repaired implementation. |
| `node --test --test-reporter=tap gate/tests/worktree-edit.test.mjs` | 6 PASS: surfaces, exact transport, recovery, no blind execution, withheld/omitted observations and required tests after withheld mutation success. |
| `package.py`: isolated package reconstruction/imports | PASS: 54 upgrade files, 57 relative JavaScript import edges, 83 local Python import edges, required assets and all seven current preflight artifacts. Imports executed outside the checkout package, without lifecycle construction. |
| Starting/current qualification source comparison | Only the metrics collector and attachment of editing facts changed. Existing eleven cases, acceptance thresholds, fixture generation and protected originals are unchanged. |

The signed harness initially hit `unsafe_state_permissions` because its synthetic state parent was not mode 0700; correcting the temporary fixture permissions made the signed checks pass. This was not a product defect. Repeated checks after the implementation repairs are verification of changed behavior, not additional unique test totals.

## Operational limitations and rollback

**The Mac owner and noncooperating same-UID processes remain trusted.** A deterministic injection immediately before the real `os.replace` that overwrites the target can still be overwritten by the editor and return success. Moving the already-open parent directory outside the workspace immediately before rename can cause the descriptor-anchored write to follow that moved directory; the later post-state check returns unknown, but does not undo the write. Reproduction: replace `editor.os.replace` temporarily with a wrapper that performs either filesystem operation immediately before invoking the original function for a `.sanctum-edit-*` source. The probes operate exclusively on synthetic paths.

These interleavings cannot be produced by the model's supported capabilities under the shared lock and copy-only runner. The lock is advisory, not a defense against an arbitrary process with the owner's filesystem privileges. Keep isolated candidate paths quiescent outside the supported host operations. This review does not claim prevention of all same-UID races, an atomic path/content compare-and-swap, or protection against a compromised Mac owner.

**A private amendment rollback alone is not a coherent runnable rollback.** The canonical source supplies the live reliability registration/schema module, while the private prefix supplies installed work-command/editor files. Restoring only the private transaction can therefore leave patch-era installed code paired with edit-era source registrations. Roll back the exact private transaction and restore its matching reviewed source version/schema-artifact pin while the gateway is stopped and managed ownership is reconciled; preserve newer work and private receipts. Build/source verification, installed verification and private doctor must pass before restart. The existing write-ahead transaction preserves prior bytes and removes newly added files. The amendment/rollback code and packaged synthetic coverage were reviewed; no actual private rollback or installation was performed here.

Read results exceeding the 12,000-character serialized result-envelope budget are withheld as omitted; callers may need smaller `max_chars`. There is no offset-range read in this repair. A success metric of `all(diff_correspondence)` over zero successful edits is vacuously true; reports must distinguish “no diff observed” from demonstrated correctness and independently reconstruct live applied edits from their private artifacts.

No canary trajectory, model success rate, live result egress, actual protected-test execution on this repaired runtime, GPU cleanup, cost, or 11-case completion result is asserted here. The full repair must not be called accepted on this offline review alone.
