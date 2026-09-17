# Project 3 installed retirement and non-inference preflight

Observed 2026-09-17 UTC. This is implementing-session evidence, not independent Project 3 acceptance. No GPU allocation or model inference occurred. The reviewed [retirement implementation](PROJECT-3-QWEN-80B-RETIREMENT.md) passed 407 packaged tests with zero failures/errors/skips. This post-install report is deliberately outside that completed source freeze; it does not change installed executable identity.

This report describes the pre-authorization checkpoint. The owner subsequently approved one allocation; the [live-attempt report](PROJECT-3-QWEN-LIVE-MICROPROBE.md) records its pre-inference verifier failure and provider-confirmed cleanup. No model inference occurred in that attempt either.

## Installed identity and ownership

The expected branch and HEAD remain unchanged, with the uncommitted repair and empty index preserved. Exactly one `scripts/upgrade_work_mode.py --apply` completed successfully. Its 49-file overlay was compared byte-for-byte against reviewed rendering, every installed FREEZE entry was checked, the full installation receipt verified, and runtime pins remained unchanged.

| Identity | Value |
| --- | --- |
| Amendment | `work-mode-1789617422916167000` |
| Source manifest SHA-256 | `8bbd18b1d7000be828a29e06ae977e16507810ae146d41277c554672b13d289b` |
| Installed gate FREEZE SHA-256 | `01931a75ea41085cdb1a201142a1cbae033a88527676c3679aef0f39bceef4ed` |
| Installed receipt SHA-256 | `1f012dd977fa08e4500af2c7ddfb458cab979eadff115b0e4908cc0ac1b5c4f9` |
| Rollback transaction SHA-256 | `f9b5df5eaa8469e6480f357f6bb2fb6d8326fed3140d25243223549c77cb7b88` |

Rollback transaction and content-minimized evidence remain under the external private candidate. Historical receipts/descriptors/cache/model artifacts and the persistent volume were preserved. No resource deletion was needed: the provider reported zero managed 80B allocations and zero managed lead allocations. Initial structural inspection found both releases OFFLINE, zero leases/active requests/unresolved experiments, no unresolved allocation intent, and no uncertain ownership. The historical lead allocation ID had a recorded absence confirmation and no owned pod.

The gateway was already stopped, with its loopback port not listening. The reviewed cleanup-only bridge verified source/install, established fresh provider absence and recorded PRIVATE_80B RETIRED. Subsequent installed janitor sweeps and local inspection confirmed RETIRED, zero leases, zero active requests, no pending ownership. Missing/true legacy configuration and old owner commands cannot revive inference. Both GPU autostart settings remain false.

Doctor passed on the new installed bytes, first stopped and then running. The supported operator started the gateway; recorded process/executable/entrypoint/source/install identities match, and loopback health passes. The authenticated owner bridge successfully invoked `/work help`, `/gate help`, `/gate new`, `/gate status`, `/gate include 80b`, and `/gate private80 allow`. Work Mode is registered; gate output reports 80B retired/unavailable. Only help/status/refusal commands ran, with no Work Mode task or inference.

## Production schemas and exact runtime boundary

Installed `preflight-work-intent.mjs --json` and `runtime-readiness.mjs` produced exactly the source artifacts. They cover ordinary ineligible/eligible, research ineligible/eligible, post-patch test-only and reviewer, with both projected generation and authoritative semantic identities. Schema-preflight output SHA-256: `8a172367e64cd4dec9aa6a36fc0900c4275b89847158c65850641df3890a2920`. Runtime request artifact SHA-256: `87450d85b00327390e5568a44d2e7edbe3cec56b56d121a052c062107e5d6837`.

The installed exact-runtime verifier returned **NOT_RUN / EXACT_ENVIRONMENT_IDENTITY_ABSENT**. No compatible local vLLM serving/compiler environment was found. The unchanged intended release is `nvidia/Qwen3.5-122B-A10B-NVFP4`, revision `98915d837c4e7c87ac8296d02e89de19b3207e6d`, vLLM 0.20.1, with unchanged quantization/MoE/attention/KV/thinking/sampling/output/context profile.

Actual serving backend selection (including resolution of an unchanged `auto` setting), all distribution versions/RECORD digests, compiler module digests, and full generation/semantic schema compilation with fresh matcher state for every representative/EOS are **allocation-required** evidence. They are not inferred from source dialect labels, mocks, AJV, or local tokenizer success. No environment was upgraded or backend selection replaced to manufacture a pass. They must be established in the existing pinned runtime before any readiness smoke/proposal; failure causes cleanup with zero model reservations.

## Pinned tokenizer and rendered headroom

Only public tokenizer/config/template files were retrieved from the immutable model revision into the external private cache. No model weights were downloaded. AutoTokenizer used local files only and remote code disabled. The existing local measurement environment is Transformers 5.16.1, tokenizers 0.23.1, Jinja2 3.1.6; its distribution RECORD digests are retained privately. This proves the pinned-byte local measurement, not the actual serving distribution identity, which must be compared after allocation.

| Pinned file | SHA-256 |
| --- | --- |
| `tokenizer.json` | `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42` |
| `tokenizer_config.json` | `316230d6a809701f4db5ea8f8fc862bc3a6f3229c937c174e674ff3ca0a64ac8` |
| `chat_template.jinja` / selected template | `a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715` |
| `config.json` | `4bbd5a6e8662d412cb6e57efeee5dfd4f8e13dc07e2b43398994f85a58f9993d` |
| `vocab.json` | `ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003` |

The first local helper result incorrectly counted BatchEncoding mapping keys. Its two-token totals and negative overhead were rejected and marked INVALID, not accepted as evidence. Corrected measurement explicitly obtains flat integer token IDs and independently verifies equality with tokenization of the rendered chat string. The exact serving check must likewise verify token-return shape and independently compare rendered counts before trusting the prepared verifier's totals. A mismatch stops before inference; no source/runtime adaptation or latest-package installation is authorized to force compatibility.

Every row uses the actual installed production payload builder, thinking disabled, generation prompt included, 4096 profile reserve, 1024 proposal ceiling and 32768 model window. These six synthetic representative requests are not proof that every possible 64000-character request fits.

| Request | System content | User content | Rendered total | Template overhead | Remaining headroom |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordinary initial | 77 | 1169 | 1263 | 17 | 27409 |
| Accumulated observations | 77 | 4504 | 4598 | 17 | 24074 |
| Active correction | 77 | 4715 | 4809 | 17 | 23863 |
| Current 64000-character boundary | 77 | 8966 | 9060 | 17 | 19612 |
| Post-patch test-only | 77 | 764 | 858 | 17 | 27814 |
| Reviewer | 77 | 453 | 547 | 17 | 28125 |

## Installed controls and supervision

A fresh installed **non-inference** experiment exercised real source/install binding, exact limits and independent watcher heartbeat. It reserved zero inference attempts and made zero allocation attempts. It was then cancelled and reconciled to COMPLETE / CONFIRMED; no unresolved experiment or lease remains. The independent process identity was verified and its clean exit observed; the launchd janitor remains loaded.

An isolated synthetic store using only installed modules additionally verified stale binding/install denial, token ceilings, deadline refusal, the one-readiness/five-proposal/six-total split and four processes competing for the last reservation: exactly one succeeded. These synthetic reservations never touched the production experiment allowance or a model endpoint. The 120-second cleanup reserve, absolute deadline and source/install bindings are unchanged.

The actual independent janitor's successful run count advanced from 3142 before installation to 3156 at the final check; last exit code was zero and its configured interval is 30 seconds. Installed supervisor heartbeat was directly observed in the zero-attempt check, rather than inferred solely from a plist. Final doctor confirmed current running identity and health; both stores still had zero leases/requests/unresolved experiments.

## Current provider terms and proposed ceiling

Read-only checks through the installed pinned Runpod CLI 2.13.0-3560e35 authenticated the account, verified zero managed allocations, the configured persistent volume and sufficient existing credit for one hour. The configured NVIDIA RTX PRO 6000 Blackwell Server Edition was available with **Low** stock at **USD 2.09/hour**. Availability/price must be rechecked at the later authorized allocation boundary; no replacement allocation is allowed.

Runpod documents per-second Pod compute/container-disk billing, no ingress/egress fees, and a one-hour-credit balance requirement (not a one-hour minimum compute charge). Container disk is USD 0.10/GB/month; network volumes are billed hourly. See [Pod pricing](https://docs.runpod.io/pods/pricing) and [billing overview](https://docs.runpod.io/accounts-billing/billing). A more specific Pod startup/deletion transition tariff was not established; conservatively count the entire allocation-to-confirmed-deletion interval, including preparation and cleanup. No new credit purchase or account/billing configuration change was made.

The account has one configured 150-GB volume. Two recent hourly billing buckets each charged USD 0.014583333395421505 for 150 GB, consistent with USD 10.50/month at the standard rate. The CLI did not report an explicit storage-tier field; observed billing, rather than a guessed tier, is the evidence. This existing storage continues after compute cleanup and will be preserved.

At the quoted rate, 900 seconds costs USD 0.5225 compute. Thirty GB temporary disk for that interval is approximately USD 0.00105. Conservatively attributing two existing-volume hourly buckets adds approximately USD 0.02917: below **USD 0.56** in total under the reviewed lifetime and confirmed-deletion conditions. Proposed owner spending ceiling: **USD 0.75** for this microprobe, with ongoing existing storage itemized separately. Uncertain deletion is not proof that billing stopped; retain supervision and report uncertainty rather than inventing a guaranteed provider-side hard cap.

## Authorization boundary and continuation

**PRIVATE_LEAD INSTALLED AND READY — OWNER AUTHORIZATION REQUIRED FOR LIVE MICROPROBE**

“Ready” means the Mac-side implementation and non-inference preflight above are complete. The explicitly permitted allocation-required compiler/backend/serving-tokenizer checks remain open and gate all inference. The owner has not authorized spending, and no live authorization document with `ownerAuthorized:true` was created.

Request exactly one allocation, at most 900 seconds including verification/readiness/probes/cleanup, six total reservations, at most one 16-token readiness smoke and five 1024-token proposals, exactly inspection → host-seeded post-patch test → inability, existing one-correction allowance, and USD 0.75 ceiling at a price no higher than the quoted USD 2.09/hour. A price increase requires renewed terms; lack of capacity ends the attempt without replacement.

The all-in-one installed runner requires `independentReview` and `exactCompiler` attestations before allocation. This implementing conversation cannot truthfully set the first, and the second is allocation-required. **Do not fabricate those booleans or invoke that all-in-one path.** The reviewed installed command-level `experiment_control.py` lifecycle permits explicit staging: create the owner-authorized bound ledger, start/verify the independent watcher, make one allocation, establish exact environment/compiler/rendered-token evidence without completion calls, then invoke its single readiness command and the same reviewed `runProtocolMicroprobes` through signed PRIVATE_LEAD dispatch. Preserve the same ledger, deadline, six-attempt budget, source/install bindings, cleanup reserve and cleanup supervisor throughout. This is an operator sequencing boundary, not a change to inference acceptance or permission to skip a gate. Any unavailable runtime proof stops and cleans up before smoke/proposals.

After a successful microprobe and provider-confirmed cleanup, report readiness for one separately authorized unseen real coding task. Its patch must be Qwen-authored, with useful inspection/reasoning, Mac-authorized execution, actual passing test, fresh evaluator and normal reviewer behavior where applicable. Only genuine COMPLETE with no schema/transport/environment/authority/egress/containment error, uncertainty, budget anomaly, receipt discrepancy or subsequent source/profile/config change opens the unchanged 11-case qualification gate. Do not run either stage under microprobe authorization. Final Project 3 acceptance remains a fresh independent audit.
