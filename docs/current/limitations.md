# Release limitations

The V1 recommendation was **READY WITH DOCUMENTED EXCEPTIONS**. See the historical [qualification](../history/v1/qualification.md) for exact gates.

- Host operations target macOS; MLX requires Apple Silicon. Linux CI has not run here.
- Fresh source-only build and host-runtime installation used package caches/downloads. MLX reused existing cached weights; no new multi-GB model download was performed.
- Interactive WebUI sign-in, local arithmetic, disclosure, status, cancellation and session close passed after a narrow implicit-tool fix.
- Calendar/Gmail reads and local generation, synthetic file/Markdown actions and MCP transports passed. Owner-run Messages read/generation passed through both the native CLI and candidate broker/wrapper. Returned limit one bounded raw prefetch to three; the generated supporting quote matched source. Broad personal-answer factual accuracy was not independently audited. Real Browser Guard navigation/approval checks passed. The small model selected an unavailable sandbox browser in the chat test; reliable autonomous target selection is not established.
- The bounded signed-worker GPU lifecycle and isolated launchd restart/sweep now pass. Actual logout/reboot, production cutover and an interactive WebUI GPU conversation were not tested.
- Vitest 3.2.7 retains a development-only moderate advisory. Its vulnerable dev-server path is unused; no upstream same-major patch exists.
- Apache-2.0 covers Sanctum source; the full external dependency stack is not uniformly Apache-licensed.
- Existing gate jobs and approvals are process-local. Migration requires fresh sessions; history and File Steward undo records have no general importer.

- In the final Messages test, the model returned a separate JSON `draft` field but omitted the requested literal DRAFT marker inside it. The strict formatting assertion failed and is retained; source quoting and write rejection passed. Treat generated prose as a draft requiring review.
