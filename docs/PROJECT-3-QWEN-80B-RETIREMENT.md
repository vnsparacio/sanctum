# Project 3 permanent PRIVATE_80B retirement

Implementation and targeted self-review, not independent acceptance. Project 3 remains unaccepted. The owner permanently retired PRIVATE_80B; PRIVATE_LEAD remains the sole inference-capable private release. The larger uncommitted repair remains part of the review target.

## Starting source and decision

The canonical checkout is the location in [the baseline](V1.1-LIVE-BASELINE.md), on `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`, eleven commits ahead of its local tracking reference, with an empty index. Starting inventory: 279 files, including untracked source. Starting SOURCE-MANIFEST SHA-256: `8b0026b6dd706c829d262cc2ceb86556caa87c5b5f2c35ea78cfcf96b0a34f22`. Synthetic inventories, authenticated pre-edit copies, and exact command logs are retained in `/tmp/sanctum-80b-retirement-20260917`.

All requested baseline/protocol/pre-live reports and architecture/configuration/migration instructions were read. Prior review dispositions remain historical evidence. No branch/index/history operation, legacy-tree edit, model/profile repin, hosted planner, semantic normalization, extra correction, authority/egress/evaluator/containment relaxation or qualification fixture change belongs to this delta.

## Runtime changes

- `plugin/core.mjs`, `src/dispatch.py`, `src/authority.py`, and `worker.py`: 80B is permanently excluded from ordinary routing, session selection, include/allow, disclosure tickets, signing and worker dispatch. Missing/true legacy configuration cannot revive it. Explicit 80B requests receive fixed host-owned retirement refusal; ordinary policy can independently choose a hosted tier, retaining its separate exact disclosure requirement.
- `src/lifecycle.py`: all 80B lease admission, infer/propose, resume and readiness methods refuse before provider/model work. Cleanup status/stop/sweep remain. Retirement preserves all historical lease rows regardless of expiry and verifies provider absence before recording RETIRED. Pending or uncertain local/provider ownership reports RECONCILIATION_REQUIRED. A discovered record reopens reconciliation and never inference. Only recorded allocations of the historical namespace can be deleted; an unrelated lead resource or unrecorded managed pod fails closed.
- `src/backends.py`, `src/runpod.py`, and `runtime/bootstrap-vllm.sh`: direct completion, smoke, create/start/resume, remote bootstrap and SSH execution cannot revive 80B. The historical executable bootstrap now only refuses. The historical release descriptor is byte-preserved, including old launch metadata as evidence, and is not an executable restore path. Persistent volumes, caches, receipts and model artifacts are preserved.
- `src/retirement.py`, `src/experiment.py`, `src/experiment_lifecycle.py`, and `experiment_control.py`: historical inspection is read-only and never creates an empty 80B lease database or takes a second inference admission transaction. Production creation/allocation requires confirmed retirement; reservations and diagnostic checks refuse subsequently discovered historical ownership. Terminal cleanup still preserves unresolved historical facts. PRIVATE_LEAD retains atomic six/one/five reservations, 16/1024 ceilings, absolute deadline, 120-second reserve, independent supervisor, and its lease/provider ownership semantics.
- `watch.py`, `install.py`, and `scripts/release_operator.py`: terminal RETIRED is recognized by cleanup/shutdown; unresolved ownership still blocks it. The independent janitor remains installed and can rediscover ownership.
- `scripts/retire_private80.py`: reviewed stopped-gateway bridge for reconciling installed historical ownership before the new amendment. It verifies source/install, uses only installed private bindings and pinned provider CLI, invokes the cleanup-only lifecycle, and neither copies executable files nor changes hashes. Provider errors are content-minimized.
- `scripts/upgrade_work_mode.py`: coherent overlay includes all changed gate runtime modules and new retirement helper. Installation requires RETIRED evidence, zero leases and no uncertain allocation, plus the existing stopped gateway and loaded janitor checks. Exactly one supported apply remains the installation path.

Existing tri-state process evidence and atomic proposal-worker/lease finalization remain intact. Ordinary lead pruning stays serialized with experiment admission, with provider/readiness/model I/O outside transactions. Retired sweep never prunes unknown rows, including outside experiments. No 80B inference lease is created or awaited.

## Permanent tests and self-review

`test_retirement.py` adds 23 synthetic regression methods for default/legacy/explicit opt-in refusal, signed and injected-worker bypasses, lifecycle/readiness/resume, direct backend/provider/bootstrap bypasses, cleanup status/stop, recorded allocation deletion, persistent-storage/descriptor preservation, unknown ownership, reopened reconciliation, empty-store isolation and post-retirement dispatch refusal. Existing routing, authorization, lifecycle and cleanup tests were updated to the permanent decision: positive inference lifecycle tests now exercise PRIVATE_LEAD, while 80B tests assert refusal or cleanup.

Fresh skeptical counterexamples additionally cover a recorded allocation ID with missing pod ID, a record pointing at the wrong release namespace, malformed historical storage and invalid retirement proof. They exposed the need to inspect orphan allocation IDs and reject cross-namespace deletion; those are fixed before full validation. Direct provider-call create bypass was also closed. This is a targeted implementing self-review, not an independent acceptance audit.

The initial pre-live run had four failures and one error: stale OFFLINE expectations, new retirement preconditions missing from synthetic fixtures, a missing tier in a direct worker fixture, and cleanup needing explicit renewed retirement after historical reconciliation. Final focused runs passed after those changes; no failing run is relabeled as a pass.

## Offline validation

Existing venv inspected first: Python 3.12.14, Pillow 12.3.0, pypdf 6.18.0, imageio-ffmpeg 0.6.0. Build/test/amendment side effects were inspected before execution. Cache-only dependency bootstrap does not upgrade model/compiler/runtime pins. Tests use synthetic state/providers and harmless children; existing local cached OCI tests remain part of the supported suite. No provider mutation or model inference is part of these checks.

| Command | Result |
| --- | --- |
| `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps` | PASS; existing environment, 383 cached npm packages and three Python requirements. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_retirement.py'` | 23 PASS, zero failures/errors/skips. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_prelive*.py'` | 69 PASS, zero failures/errors/skips. |
| `node --test --test-reporter=tap gate/tests/core.test.mjs gate/tests/prelive.test.mjs gate/tests/protocol-repair.test.mjs gate/tests/protocol-targeted.test.mjs` | 55 PASS, zero failures/skips. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_protocol_*.py'` | 15 PASS, zero failures/errors/skips. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_runtime.py'` | 71 PASS, zero failures/errors/skips. |
| `.venv/bin/python -B /tmp/sanctum-prelive-targeted-review-20260917/cleanup-counterexamples.py` | Original two independent counterexamples PASS: preserved historical row and independently live unknown worker remain LOCAL_PENDING. |
| `.venv/bin/python -B /tmp/sanctum-prelive-independent-review-20260917/ledger-controls.py` | Six retained independent controls PASS. |
| `.venv/bin/python -B /tmp/sanctum-prelive-targeted-review-20260917/compiler-controls.py` | Four retained independent orchestration controls PASS, 50 fresh wrappers across twelve full-schema checks; not exact compiler proof. |
| `make build` | PASS, six plugin builds/validations, capability manifest and unchanged runtime pins. |
| `umask 022` then `make test` | **407 PASS**, zero failures/errors/skips, one complete run: gate Node 110, gate Python 218, reliability Node 31, reliability Python 11, MCP Node 8, release Python 18, plugin tests 11. |
| Isolated package closure (included above) | **49 overlay files, 56 JavaScript and 71 Python local edges**; isolated imports/builders identical, unavailable exact-runtime CLI remains NOT_RUN. |
| `make audit` | PASS, 283 files, zero issues. |
| `.venv/bin/python -B -c 'from scripts.release_operator import verify; verify(); print("Source manifest and runtime pins match")'` | PASS; final report-only freeze rechecked. |
| `git diff --check` plus all-untracked trailing-whitespace scan | PASS. |
| Changed-runtime overlay and immutable-profile comparison | PASS; no omitted runtime file; lead runtime/profile/dependency pins and historical descriptor unchanged. |

Focused counts are subsets of the packaged total, not additional tests. Historical independent scripts are separate. Exact compiler/backend, tokenizer/template and rendered-token evidence is not supplied by synthetic tests.

## Freeze, package and rollback

The explicit new SOURCE-MANIFEST freeze updates only entries whose changes are explained here and adds the new helper, retirement tests, stopped-gateway bridge and this report. Unrelated hashes and PRIVATE_LEAD model/runtime pins remain unchanged. Full before/after inventories and the manifest digest are retained with the synthetic evidence to avoid self-reference.

The coherent 49-file overlay was materialized over the installed base with source modules unavailable to its import path. All local Python/JavaScript modules resolved and production request artifacts were identical. This proves package closure, not actual installed identity.

Source rollback consists of reversing only the authenticated delta relative to the starting inventory; preserve the larger uncommitted repair and do not reset the checkout. Deployment rollback uses the retained stopped-gateway Work Mode transaction after confirmed zero ownership and completed experiments. Restoring older executable source would restore its old inference behavior, so it cannot be used as a supported way to revive retired 80B. Preserve private receipts, state, model storage and cleanup supervision; never replace whole databases.

## Remaining runtime gates

Historical ownership reconciliation, supported amendment and installed byte/FREEZE/receipt verification, new-byte doctor, authenticated gateway/help, installed production schema artifacts, exact backend/compiler identity or clearly separated allocation-required evidence, exact tokenizer/template/headroom, installed controls and read-only current provider pricing/capacity remain runtime gates. This source report does not fabricate their completion. They will be recorded separately without changing this reviewed source freeze after installation.

No allocation or paid inference is authorized by this work. Stop before paid compute and request the owner's explicit one-allocation/900-second/six-attempt bounded microprobe authorization only if the necessary preflight gates are met. No real coding or 11-case qualification is included; coding clean success precedes unchanged qualification under a later separate authorization.

Offline implementation and targeted self-review passed. No known source blocker remains. This is not Project 3 acceptance. Installation/runtime results are separate evidence.
