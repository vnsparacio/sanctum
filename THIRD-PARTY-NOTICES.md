# Third-party dependencies and distribution scope

The Apache-2.0 grant in LICENSE covers Sanctum source and documentation. It does not relicense external packages, model weights, containers, or services.

This release is source-only: node_modules, Python environments, generated plugin builds, model weights, runtime state and container layers are excluded. Review of the included source found no separately licensed vendored implementation or conflicting copyright notice. The npm lockfile and installed package metadata were reviewed before applying Apache-2.0 to this source distribution.

| Dependency | Observed license / treatment |
|---|---|
| OpenClaw 2026.8.1; TypeBox; Ajv; Vitest | MIT; installed separately, retain upstream notices |
| TypeScript | Apache-2.0 |
| MLX, mlx-metal, mlx-lm | MIT; separately installed Apple Silicon environment |
| Pillow; pypdf; imageio-ffmpeg | MIT-CMU; BSD-3-Clause; BSD-2-Clause metadata respectively; separately installed. FFmpeg binaries carry their own obligations |
| Open WebUI 0.11.1 | Open WebUI License, including branding requirements; separately installed and unmodified. Its branding is retained |
| OpenClaw’s Anthropic Agent SDK and platform CLI dependency | Proprietary Anthropic terms; not used by the candidate’s enabled model/tool paths and not included in the source archive |
| Remaining npm transitive packages | Lockfile includes MIT, ISC, BSD, Apache, MPL-2.0, BlueOak, Unlicense, 0BSD and dual-license expressions; their original licenses remain applicable |
| Models and MCP/container images | External downloads; each retains its own upstream license and notices |

Sources: [Open WebUI license](https://github.com/open-webui/open-webui/blob/v0.11.1/LICENSE), [Anthropic terms and distribution conditions](https://code.claude.com/docs/en/legal-and-compliance), and each pinned installed package’s metadata/license files. The Anthropic components must not be described as Apache-licensed or generally redistributable. This source license decision does not certify an all-open-source dependency stack.

No license conflict was found preventing Apache-2.0 for the included Sanctum source. Bundling dependencies, Python environments, FFmpeg, model weights or a complete runtime image is outside this conclusion and requires a separate redistribution review. A root Apache license alone does not satisfy those obligations.
