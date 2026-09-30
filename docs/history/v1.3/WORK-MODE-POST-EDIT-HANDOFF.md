# Work Mode post-edit handoff repair

## Live observation

In the bounded MoodLog Lite lifecycle test, the configured private Qwen provider reached READY and returned four parsed Work Intents. The model listed and read the isolated workspace, then deleted its README. The following host decision had `POST_PATCH_TEST_REQUIRED` and exposed only `worktree_command`; the model returned `ESCALATION`, and the task ended `BLOCKED / MODEL_ESCALATION`. The exact model reason was not retained. No app implementation, test, evaluator, reviewer or browser check ran. Supported `/work end` cleanup removed the workspace and lease, provider-side inventory found no managed Pod or active private-lead request, and Sanctum stopped normally.

The trace establishes the capability handoff and terminal result. It does not prove why the model chose escalation. For a multi-file greenfield task, forcing a test immediately after the first edit prevents the model from completing the candidate before testing. In this run it could not create application files after the README deletion without first invoking the test command.

## Source change

After each successful edit, the next semantic surface retains the profile's permitted inspection, edit and command capabilities. `POST_PATCH_TEST_REQUIRED` continues to hide `FINAL` and require a post-edit test before completion. Edit recovery still hides `worktree_edit` until the required read. The model-facing system message describes the multi-file sequence. Successful explicit testing still triggers the host evaluator and optional reviewer; host authority, egress, workspace binding, budgets and cleanup are unchanged.

The owner-private ledger now adds one fixed `reasonCategory` to the existing escalation digest and concept flags. Categories are observational only, never routing or authority input. Raw model reason text remains excluded.

## Verification and limit

The signed-worker regression makes two synthetic file edits before one test, checks that both post-edit surfaces retain edit access while `FINAL` stays hidden, and confirms evaluation begins only after the test. Host-level tests cover post-edit continuation, unchanged completion gating and payload-free escalation categories. Runtime-readiness preparation now represents the post-edit continuation request. The older standalone test-only schema remains in offline preflight for compatibility; it is not selected by the ordinary post-edit task loop.

This is a source repair, not a claim of live Qwen coding success. A new full private-lead lifecycle test is required after review, owner merge, supported stopped-gateway installation and doctor verification. The prior provider and lease were fully released; no new GPU allocation was made for this source change.
