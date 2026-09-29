# Qwen Code snapshot handoff for Work Mode

Status: source contract implemented; the headless runner and `/work` engine selection are not yet implemented. This contract alone does not make the isolated Qwen Code proof a Sanctum Work Mode run.

The [fourth isolated MoodLog proof](../history/v1.3/WORK-MODE-QWEN-CODE-FOURTH-ISOLATED-POC.md) established that Qwen Code 0.24.6 can make the required edits without a human editing mid-run. Its two paths were separate:

1. **Model path:** Qwen Code in a pinned, networkless container called a Mac-owned stdio broker. The broker reached the existing private 122B vLLM route through a loopback tunnel. The Sanctum gateway did not expose an OpenAI-compatible model endpoint.
2. **Coding-tool path:** Qwen Code's headless loop and tools ran inside that container on a copied workspace. The container had no live Mac worktree mount, network, host shell, home, credentials, or Docker socket. The Mac enforced an outer run deadline, workload limits, provider lease, and GPU cleanup. Qwen Code's turn, tool, and wall limits were additional bounds, not an authorization boundary.

## Mac-owned handoff implemented here

The new signed `worktree_qwen_export` operation freezes a clean, task-bound Work Mode workspace under the private evidence directory. It requires a passing protection check and the original candidate digest, copies ordinary files without following links, excludes `.git`, and records the task, protection, and baseline identities. It returns fixed private `qwen-input` and `qwen-output` paths. It does not run a model or expose a caller-selected host path.

An isolated runner must **copy** `qwen-input` into the container, stop the container after the bounded headless run, and copy its final files into `qwen-output`. Neither directory may be mounted into the container. The runner must keep raw prompts, source bodies, model/tool trace, and private receipts outside Git. It must verify container exit and output-copy completion before requesting import.
The private input uses restrictive host file modes; the runner must set ownership and working-copy permissions inside the container before dropping to the non-root Qwen process. This setup step is part of the trusted runner and must be tested with the actual pinned image.

The signed `worktree_qwen_import` operation accepts only that fixed output for the same task. It rejects symlinks, special files, deleted files, new directories, `.git`, protected or disallowed paths, stale workspace state, oversized files or diffs, and an unchanged candidate. It builds a canonical patch and passes it through the existing Mac patch authority. The original candidate digest is checked again under the patch lock; a changed workspace fails closed. An attempt marker prevents replay. The receipt identifies the accepted output and patch digests, changed paths, workspace generation, and authority decision. Original file modes are preserved; new files use the patch authority's mode. No container output directly mutates the task worktree.

These operations are host-only worker routes requiring the existing owner Work Mode authorization. They are not model-visible capabilities. The task command, validation profile, protected oracle, evaluator, reviewer, receipt chain, and Human Review remain Sanctum responsibilities.

## Required next integration

Wire one reviewed Work Mode engine selection to a headless Qwen Code runner. It must use the existing task admission, private profile, budgets, and provider lifecycle. The Mac must own the image digest, stdio model broker, exact copy-in/copy-out, outer wall clock, retry count, workload cap, failure classification, and cleanup. Qwen Code settings and prompt text cannot grant host authority. After import, run the fixed ordinary and protected acceptance commands in Sanctum's pinned command runner; then use the existing evaluator, reviewer, receipt, and Human Review path. A Qwen final message alone is not completion.

Do not install this source as a live Work Mode engine until that runner and its failure-path contracts are complete. The approved prior paid window was used by the isolated proof; the next live test requires a separate owner-approved window, with no automatic retry.

## Local contract verification

`python -B -m unittest gate.tests.test_qwen_snapshot` exercises the export/import boundary with synthetic workspaces. It covers signed task identity, the authorized patch, protected paths, unsafe file types, deletion, structure, stale workspace, changed output, patch-lock races, and replay. The preserved MoodLog final files were also imported into a temporary synthetic task, then passed the pinned ordinary and four protected tests. That offline rehearsal used no model or GPU and does not establish a complete `/work` run.
