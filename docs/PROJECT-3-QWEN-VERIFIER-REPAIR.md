# Project 3 serving-verifier repair

This repair follows the [approved attempt's pre-inference failure](PROJECT-3-QWEN-LIVE-MICROPROBE.md). The owner requested a plan and execution to resolve it. The implementation plan is: reproduce the cache failure without paid compute; package a corrected verifier; test cache/model/token/error boundaries; review and validate the complete package; install through the supported stopped-gateway reversible amendment; then request fresh allocation authorization for live confirmation. The previously approved allocation is consumed and is not reused as spending authority.

## Starting identity and scope

The branch remains `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`, with the existing uncommitted Project 3 repair and empty index preserved. Starting source-manifest SHA-256 is `8bbd18b1d7000be828a29e06ae977e16507810ae146d41277c554672b13d289b`. Exact before-copies of affected files and the starting manifest/status were retained outside source. The historical failed run and its receipts remain unchanged.

Only these changes belong to this repair:

- New `gate/verify_serving_runtime.py`: derives the launch/cache contract from the unchanged reviewed bootstrap, checks the actual process command and cache environment, binds the existing offline cache before importing model libraries, validates requested model/revision and the resolved immutable snapshot, runs production schema/compiler/token checks, and rechecks server identity. Failures retain stage, exception class and bounded frame metadata without messages, source lines, absolute paths or local variables.
- `gate/verify_exact_runtime.py`: requests explicit flat token IDs, validates their shape and independently compares tokenization of the rendered chat string. A BatchEncoding mapping can no longer masquerade as a two-token prompt.
- New `gate/tests/test_serving_verifier.py`: regression and refusal tests, plus isolated orchestration with external-package stubs clearly distinguished from actual compiler proof.
- `gate/tests/test_prelive_targeted.py`: its synthetic tokenizer now supplies consistent rendered text/IDs for the strengthened token contract; fresh grammar/EOS and rejection assertions remain unchanged.
- `gate/tests/test_prelive_package.py`: requires/imports the new verifier in the isolated installed overlay.
- `scripts/upgrade_work_mode.py`: includes the new verifier in the existing reversible amendment.
- This report and only the explained changed/new manifest entries.

Qwen checkpoint/revision, vLLM version, backend selection, quantization, attention/MoE/KV/thinking/sampling/context/output settings, correction limit, authority, evaluator, egress, resource ownership, deadline, inference budget and cleanup supervision are unchanged. PRIVATE_80B remains permanently retired. Legacy source is untouched. No commits, branch switches, pushes, PRs or promotions are part of this repair.

## Reproduction and verification boundaries

The existing local Hugging Face library reproduced `LocalEntryNotFoundError` using a wrong cache with a synthetic immutable snapshot present elsewhere. In a fresh subprocess, the corrected binding resolved that same snapshot with network connections explicitly denied. No weights were loaded or downloaded. This is an actual library/cache regression, not a mock success.

The existing pinned tokenizer/template independently measured all six production request forms through the corrected helper: input totals 1263, 4598, 4809, 9060, 858 and 547; remaining headroom 27409, 24074, 23863, 19612, 27814 and 28125 with the unchanged 4096 reserve and 32768 window. No inference or weight loading occurred. This is local pinned-byte evidence, not serving-distribution proof.

The first focused run caught a parser error in joining the bootstrap's continued shell command (13 setup errors); it was corrected before installation. No paid attempt was used for debugging. Final validation and installation evidence are recorded below when complete.

## Targeted self-review

Cache configuration is verified against the running server before imports, rather than merely setting an ambient variable. A conflicting observed server cache/endpoint or non-offline mode refuses. The launcher command must match the reviewed bootstrap; alternate model, runtime arguments or interpreter directory refuse. Offline model-ID-to-snapshot rewriting is expected and checked against the immutable revision. A changed/replaced server invalidates otherwise successful compiler results.

The verifier never calls a completion endpoint or creates resources. The unchanged installed ledger, signed dispatch and independent cleanup still govern any later inference. External compiler stubs test orchestration only; actual backend selection, resolved distributions/RECORDs/modules and full-schema acceptance must still be measured on the serving allocation. `auto` is not replaced. An unsupported backend or compiler failure remains a failure.

Raw library stdout/stderr is suppressed, including native file descriptors, and failures retain only structural metadata. Existing failed-run evidence is not overwritten. This is implementing-session self-review, not independent Project 3 acceptance.

## Validation and installation

The existing Python 3.12.14 dependency environment was inspected before running the cache-only `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps`; it passed without recreating the environment. `make build` passed all six plugin builds and pin checks. `make audit` scanned 288 source files with zero issues.

Focused commands were `../.venv/bin/python -B -m unittest discover -s tests -p test_serving_verifier.py` (22 passed) and the same command with `-p 'test_prelive*.py'` (69 passed), from `gate`. The targeted pre-live compiler tests also passed (12). Package closure includes 50 overlay files, 56 JavaScript and 73 Python edges; isolated imports and exact production builders passed without the checkout on the module path.

One complete `umask 022; make test` passed **429 tests**: gate Node 110, gate Python 240, reliability Node 31, reliability Python 11, MCP 8, release Python 18, and plugin tests 11. There were zero failures, errors or skips. Focused tests are not added to that total. No required source change followed this successful full run.

Installation identity and later non-inference checks are retained separately so this reviewed source freeze can remain stable. No new allocation is authorized or performed by this repair.

## Rollback and next gate

Source rollback uses the retained exact before-copies for only the files changed here; do not reset the larger Project 3 working tree. Installed rollback uses the amendment's supported rollback transaction after gateway shutdown and confirmed zero ownership; historical receipts and the persistent volume remain preserved.

After offline validation and installation, live confirmation requires one newly authorized allocation under the same bounded microprobe terms. A pass then opens only the separately authorized real-coding stage; the 11-case qualification and fresh independent acceptance remain later gates.
