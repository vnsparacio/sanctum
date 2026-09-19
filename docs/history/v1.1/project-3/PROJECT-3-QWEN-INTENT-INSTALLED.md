# Project 3 host decision guidance: installed checks

The [host decision guidance repair](PROJECT-3-QWEN-INTENT-GUIDANCE.md) is installed through reversible amendment `work-mode-1789622404253044000`. This post-install observation report is outside the completed source freeze.

Source-manifest SHA-256: `56fda1d5b1eed492ae865eeec06e77340a2ff83bc2876f86e2ca08323bef9528`.
Installed FREEZE SHA-256: `888a0197cec1802f5179921668d12789a1ecc87852400b312a01ee0d46aa84dd`.
Receipt SHA-256: `0916c8ed05cb4faacb90ea229e9f9695c4615ebc1efecf81c18429f2add925cd`.
Transaction SHA-256: `bf5a248357fc61268e57da8e0dcf719a4975c36e41d1d7c065c38b73ca089b4a`.
Readiness artifact SHA-256: `13b34ad574d42fda43fd006d653a64f67cb7b3105e1dba72e1df7382ea2eea2b`.

All 50 overlay files match rendered source; all 68 frozen installed files, receipt and runtime pins verify. The runtime artifact is unchanged and matches source; the production backend's system message changed as explained in the new source freeze. Token measurement uses that actual backend. Doctor passes while stopped and after restart with gateway identity matching and socket healthy. Authenticated help, status and permanent 80B refusal pass. Both GPU autostarts remain off.

An installed metadata-only experiment verified a fresh supervisor heartbeat and zero allocations/model calls, then completed cleanup. A subsequent structural preflight briefly refused with retirement ownership unreconciled; a fresh read showed RETIRED with a current confirmation and zero ownership, and the retry passed. No guard was weakened or resource allocated to get past this refusal. Provider inventory and final quote are retained in private evidence.

The next private operator has tested non-inference diagnostic pauses for both verifier and semantic failures, preserves the same allocation/deadline, never resumes inference after a failed semantic probe, and retains only bounded content-minimized telemetry. Source, install, operator, probe wrapper and artifact hashes bind any fresh authorization. It refuses without that authorization.

No fourth allocation has been authorized or performed. Live behavior of the guidance repair remains unverified. The prior live run proved the compiler compatibility fix but failed the first semantic microprobe. Project 3 remains unaccepted; real coding and qualification remain later gates.
