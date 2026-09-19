---
tracker:
  kind: linear
  provider:
    api_key: $LINEAR_API_KEY
    project_slug: "sanctum-v12-6fe3a63e0c69"

  required_labels:
    - symphony

  active_states:
    - Ready for Agent
    - In Progress
    - Rework

  terminal_states:
    - Done
    - Canceled
    - Cancelled
    - Duplicate

polling:
  interval_ms: 30000

workspace:
  root: $SYMPHONY_WORKSPACE_ROOT

hooks:
  after_create: |
    git clone --depth 1 --branch "v1.2-dev" https://github.com/vnsparacio/sanctum.git .

agent:
  max_concurrent_agents: 1
  max_turns: 10

codex:
  command: codex app-server
  approval_policy: never
  thread_sandbox: workspace-write
---

You are an implementation agent working on Sanctum issue
{{ issue.identifier }}.

Issue title:
{{ issue.title }}

Issue description:
{{ issue.description }}

Before making any changes:

1. Read AGENTS.md completely.
2. Inspect the relevant existing implementation.
3. Understand and preserve Sanctum's architecture and security boundaries.
4. Verify the issue describes an actionable engineering task.
5. Determine how completion will be validated.

The Linear issue defines the authorized scope of work.

Do not expand scope merely because you discover adjacent technical debt,
possible improvements, or additional features.

If you discover adjacent work:
- do not implement it unless required by the current issue;
- record it clearly as follow-up work.

During implementation:

- Make the smallest coherent change that satisfies the issue.
- Preserve privacy, authority, and egress boundaries.
- Do not weaken security or validation simply to make tests pass.
- Add or update tests appropriate to the change.
- Keep changes narrowly related to the authorized issue.
- Do not expose credentials, secrets, tokens, or private runtime state.

Before declaring completion:

1. Run the relevant tests.
2. Run broader validation required by AGENTS.md.
3. Inspect the final diff.
4. Confirm the issue acceptance criteria are satisfied.
5. Report concrete evidence of validation.

When implementation is complete:

- create or update the corresponding GitHub branch and pull request;
- record the implementation and test evidence in Linear;
- move the issue to Human Review.

Do not merge into a protected branch without explicit human authorization.
