# Project 3 verifier repair — installed checkpoint

Observed 2026-09-17 UTC after the [reviewed verifier repair](PROJECT-3-QWEN-VERIFIER-REPAIR.md). This post-install evidence report is deliberately outside the executable source freeze. No allocation, model download, readiness smoke, proposal, coding task or qualification was performed during this repair.

The cache defect and associated model-path/token-shape defects are corrected and verified offline. Live serving confirmation remains outstanding; do not describe offline tests as a passed microprobe.

## Installed identity

The candidate was confirmed zero-owned, PRIVATE_80B RETIRED, PRIVATE_LEAD OFFLINE, with zero leases or unresolved experiments, a loaded independent janitor and both autostart flags false. The supported operator stopped the gateway. Exactly one new stopped-gateway reversible amendment installed this repair; the earlier amendment and failed-run evidence were preserved.

| Identity | Value |
| --- | --- |
| Amendment | `work-mode-1789619949000168000` |
| Source manifest SHA-256 | `5a1f69c5b40b78668d2059e839dd4f5fb3874d0af9c36c7febe0abd1f12662a2` |
| Installed FREEZE SHA-256 | `9f744032da1231911cd7009c79d41a239eeb346364b0c2e4c9bab203fc482a81` |
| Installed receipt SHA-256 | `b6af849e44bb78013e11c21c7b9aa659c871d1185e00f8a3bf717008d7014b10` |
| Rollback transaction SHA-256 | `581a69a3bc4f9f1881c69e0254b28b5b0bb03908d789fe4fbc4f8d09d9c24b61` |

All 50 overlay files matched the reviewed rendering byte-for-byte. Full installed FREEZE/receipt and source/runtime integrity passed. Runtime and Qwen profile pins remain unchanged. Doctor passed while stopped and after the supported restart; the running gateway's identity and loopback health matched the new installation.

Authenticated `/work help`, `/gate new`, `/gate status` and the old 80B include-command refusal passed. The initial immediate post-start help check did not complete successfully; the later bounded authenticated checks all passed. Only commands with no inference were used.

## Installed checks

Installed production preflight and runtime-request artifacts equal their source counterparts. Their SHA-256 identities remain `8a172367e64cd4dec9aa6a36fc0900c4275b89847158c65850641df3890a2920` and `87450d85b00327390e5568a44d2e7edbe3cec56b56d121a052c062107e5d6837`, respectively. The installed serving verifier refuses on this non-serving Mac with a structured `SERVER_IDENTITY` stage, as expected; this is not compiler proof.

A fresh metadata-only installed experiment verified the new source/install binding, live independent supervisor heartbeat and the exact six-total/one-readiness/five-proposal and 16/1024-token ceilings. It made zero allocation attempts and zero inference reservations, then reconciled to COMPLETE / CONFIRMED. No unresolved experiment remains.

The final read-only provider check reported zero managed allocations, available target capacity with Low stock at USD 2.09/hour, and the preserved configured 150-GB volume. The janitor had advanced to 3227 runs with last exit code zero. PRIVATE_80B retirement remained confirmed with zero requests/leases/pending ownership; PRIVATE_LEAD had zero leases and no unresolved experiment.

The complete offline suite passed 429 tests with zero failures/errors/skips; focused regressions, real offline cache reproduction/fix, real pinned-tokenizer measurements and package closure are documented in the repair report. Those local successes do not establish the remote distribution/compiler identity.

## Prepared continuation and authorization

The new private staged caller uses the installed `verify_serving_runtime.py` and `verify_exact_runtime.py`; it no longer carries an improvised remote verifier. Its authorization binds source, installation, operator-script and probe-caller hashes. It refuses before any provider call without a fresh, unexpired explicit authorization; this refusal was checked and created no experiment. The retained proposal has `ownerAuthorized:false`. The consumed earlier approval is not reused or silently extended.

The concrete request remains exactly one allocation, at most 900 seconds including verification/cleanup, USD 0.75 ceiling at at most USD 2.09/hour, one 16-token readiness smoke and five 1024-token proposals, six total reservations, and only the three fixed microprobes. Current-rate conservative full-lifetime estimate remains below USD 0.56 including the previously itemized temporary disk and two existing-storage hourly buckets. Existing persistent storage continues independently. Price/capacity/ownership and supervision must be rechecked immediately before a newly authorized allocation.

On that one allocation, establish exact cache/model/backend/compiler/token proof before any inference. Failure stops and cleans up; success permits only the bounded readiness and fixed probes. No replacement allocation, correction-limit increase, profile change, real coding or qualification is authorized by this checkpoint. Confirm provider absence, local worker exit and zero leases before concluding cleanup; uncertainty retains supervision.

**PRIVATE_LEAD INSTALLED AND READY — OWNER AUTHORIZATION REQUIRED FOR LIVE MICROPROBE**

Project 3 remains unaccepted. A fresh independent audit still owns final acceptance.
