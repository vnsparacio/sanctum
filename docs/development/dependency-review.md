# Dependency advisory review — 2026-09-11

The lockfile installs development dependency `vitest@3.2.7`, which requires exactly `@vitest/mocker@3.2.7`. Both audit entries describe one vulnerability: CVE-2026-84373 / GHSA-82fw-gwwq-j7x9, moderate severity.

The [upstream advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9) identifies redirect-mock file reads through the standalone Vite mocker/interceptor WebSocket registration path. Versions from 2.1.0 before 4.1.11 are affected; fixes ship in 4.1.11 and the fixed 5.0 release line. Upstream does not plan a 3.x backport.

All six candidate configurations use the Node environment. The runner executes `vitest run`; it enables no browser mode, UI/API server, standalone mocker/interceptor integration or network bind. Source inspection finds no registration of the vulnerable server path. The installed vulnerable code remains present, but that path is not reachable in the prescribed test workflow. Vitest is absent from the running gateway/model/host-broker call chain.

Disposition: retain the V1 pin and document a development-only exception. There is no upstream patch-level or same-major remediation. Forcing a newer mocker under Vitest 3 would break its exact internal dependency contract without establishing safety. A major runner migration solely to clear this advisory is outside V1 scope. Do not expose a Vitest/Vite test server or introduce browser/mock-server use with this pin. Review a supported major in post-V1 maintenance.

No dependency versions were changed for this disposition. Final V1 test results are in [acceptance](../history/v1/acceptance.md). An audit report with two moderate entries must not be described as vulnerability-free.

## V1.2 observability addition — 2026-09-19

The first gateway-only Splunk Observability Cloud slice pins `@splunk/otel`
4.11.0 and its manual API dependency `@opentelemetry/api` 1.9.1. Resource
construction uses `@opentelemetry/resources` 2.10.0. Offline in-memory tests
pin `@opentelemetry/context-async-hooks`, `@opentelemetry/sdk-metrics`, and
`@opentelemetry/sdk-trace-base` 2.10.0 as explicit development dependencies.
The Splunk package supports the repository's Node `>=22` runtime. Automatic
instrumentation, runtime metrics, logs, profiling, and remote configuration are
disabled; only manual allowlisted signals are used.

`npm audit` still reports the two documented moderate Vitest development-path
entries. No unrelated upgrade or forced audit fix was applied.
