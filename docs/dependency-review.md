# Dependency advisory review — 2026-09-11

The lockfile installs development dependency `vitest@3.2.7`, which requires exactly `@vitest/mocker@3.2.7`. Both audit entries describe one vulnerability: CVE-2026-84373 / GHSA-82fw-gwwq-j7x9, moderate severity.

The [upstream advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9) identifies redirect-mock file reads through the standalone Vite mocker/interceptor WebSocket registration path. Versions from 2.1.0 before 4.1.11 are affected; fixes ship in 4.1.11 and the fixed 5.0 release line. Upstream does not plan a 3.x backport.

All six candidate configurations use the Node environment. The runner executes `vitest run`; it enables no browser mode, UI/API server, standalone mocker/interceptor integration or network bind. Source inspection finds no registration of the vulnerable server path. The installed vulnerable code remains present, but that path is not reachable in the prescribed test workflow. Vitest is absent from the running gateway/model/host-broker call chain.

Disposition: retain the V1 pin and document a development-only exception. There is no upstream patch-level or same-major remediation. Forcing a newer mocker under Vitest 3 would break its exact internal dependency contract without establishing safety. A major runner migration solely to clear this advisory is outside V1 scope. Do not expose a Vitest/Vite test server or introduce browser/mock-server use with this pin. Review a supported major in post-V1 maintenance.

No dependency versions were changed for this disposition. Final test results are in [acceptance](acceptance.md). An audit report with two moderate entries must not be described as vulnerability-free.
