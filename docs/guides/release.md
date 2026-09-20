# Release checklist and publication commands

## V1.2.0 release completion and promotion

V1.2.0 is a backward-compatible release that preserves the Mac authority
model. Release work must not amend or redeploy the private runtime, alter the
legacy repository, add product scope, expose secrets or move existing tags.
Review the [V1.2 release record](../history/v1.2/V1.2-RELEASE-COMPLETION.md),
[current limitations](../current/limitations.md), agent-system evidence and
Splunk evidence before promotion.

The workflow has three human gates. Do not collapse them into one PR and do not
merge any PR automatically.

### 1. Complete the release on `v1.2-dev`

Fetch the canonical remote, require a clean checkout and branch from the exact
current integration tip:

```sh
git fetch --prune --tags origin
test -z "$(git status --porcelain)"
git rev-parse origin/v1.2-dev
git switch -c v1.2/project-release-completion --no-track origin/v1.2-dev
```

Set the root package and root lockfile package versions to `1.2.0`; update the
changelog, release record and current documentation; and refresh only the
intentional entries in `SOURCE-MANIFEST.json`. Do not rewrite V1/V1.1 history or
historical private-prefix names. Then run the complete release validation:

```sh
make deps
make format-check
make lint
make build
make test
make audit
make verify-source
make doctor PREFIX=/absolute/private/prefix
git diff --check
```

`doctor` is read-only. Never print or inspect credentials while validating the
private prefix. Inspect the complete diff and tracked-file inventory for
secrets, owner paths, runtime state, unrelated edits and unsupported claims.
Commit and push the release branch, then open a ready-for-review PR targeting
`v1.2-dev`. Its body must include the accepted release inventory, exact starting
commit, changed files, validation results, limitations and rollback. Stop for
owner review; do not merge.

### 2. Promote the reviewed release to `main`

After the owner confirms the release-completion PR is reviewed and merged,
fetch again and verify that its reviewed merge commit is the tip of
`origin/v1.2-dev`. Confirm every required CI check passed, all authoritative
release metadata says `1.2.0`, and no local/remote tag or GitHub release named
`v1.2.0` exists:

```sh
git fetch --prune --tags origin
git rev-parse origin/v1.2-dev
git status --short
git tag --list v1.2.0
git ls-remote --exit-code --tags origin refs/tags/v1.2.0
gh release view v1.2.0 --repo vnsparacio/sanctum
```

The final two absence checks are expected to return nonzero before publication.
Open a promotion PR from `v1.2-dev` into `main`. The promotion PR must contain
the already reviewed commits and no new edits. Stop again for owner review; do
not merge.

### 3. Tag and publish the reviewed `main` result

After the owner confirms the promotion PR is reviewed and merged, fetch once
more. Verify that `origin/main` contains the exact reviewed release tree and
identify the promotion merge commit that should receive the immutable tag.
Inspect the repository-local Git identity and require an approved public or
GitHub noreply email:

```sh
git fetch --prune --tags origin
git show --no-patch --format=fuller origin/main
git diff --exit-code origin/v1.2-dev^{tree} origin/main^{tree}
git config --get user.name
git config --get user.email
```

Prepare a V1.2-only release-notes file from the reviewed top section of
`CHANGELOG.md`. Stop and obtain final explicit owner approval for both the exact
40-character tag target and the complete notes. Only after that approval:

```sh
git tag -a v1.2.0 <APPROVED_COMMIT> -m "Sanctum v1.2.0"
git push origin refs/tags/v1.2.0
gh release create v1.2.0 --repo vnsparacio/sanctum --verify-tag \
  --title "Sanctum v1.2.0" --notes-file /absolute/path/to/reviewed-v1.2-notes.md
```

Push only the tag. Never move, delete or recreate it. Publication does not
modify the private runtime.

### Rollback

Before tag publication, rollback is a normal reviewed revert of the
release-completion or promotion PR; do not force-push integration or stable
history. After publication, the tag and GitHub release are immutable evidence:
fix a source problem in a later version rather than retagging. Runtime rollback
remains the separate stopped-gateway procedure in the [migration guide](migration.md).
Disable direct Splunk export through its documented private configuration
amendment if needed; preserve the existing Core spool/S3 path and already
ingested evidence. Preserve provider cleanup supervision and volumes whenever
GPU ownership is uncertain.

## V1.1.0 historical release completion

V1.1.0 is a completed historical release. Its source version is `1.1.0`; the immutable V1.0.0 and V1.1.0 tags and releases are not recreated or moved. The retained commands below document the convention that was followed. Production migration remains separate.

Review [the V1.1 release record](../history/v1.1/V1.1-RELEASE-COMPLETION.md), [structured-editing evidence](../history/v1.1/project-3/PROJECT-3-STRUCTURED-EDITING.md), documented limitations, source audit and CI before tagging. Do not treat the completion PR itself as authorization to move `main`, delete private evidence, change a private runtime, or launch compute.

The historical procedure required an approved public Git identity and the following commands after review. Do not rerun them for V1.2:

```sh
git checkout v1.1-dev
git pull --ff-only origin v1.1-dev
git status --short
git show --no-patch --format=fuller HEAD
make deps
make build
make test
make audit
git tag -a v1.1.0 -m "Sanctum v1.1.0"
git push origin v1.1.0
gh release create v1.1.0 --repo vnsparacio/sanctum --verify-tag \
  --title "Sanctum v1.1.0" --notes-file CHANGELOG.md
```

Stop if the checkout is dirty, `v1.1-dev` differs from the reviewed PR merge commit, a tag already exists, or any validation fails. The tag/release are owner-controlled publication actions; they are intentionally not created by this source-change PR.

## V1.0.0 historical initial publication

The following retained procedure describes the already-completed initial V1.0.0 publication. Do not rerun initialization or recreate its tag/release.

1. Review the documented qualification exceptions and final source audit. Disk recovery, janitor/GPU cleanup, interactive WebUI and bounded personal/tool checks now have fresh evidence.
2. Confirm the source-only inventory and external license scope. Preserve the documented Vitest exception; do not call the dependency tree vulnerability-free.
3. Inspect the configured Git author locally. Use an approved public identity or the authenticated account’s GitHub noreply address. Prefer repository-local configuration; never publish a private address or change global identity automatically.
4. Confirm the proposed release notes in CHANGELOG.md and the exact GitHub repository. Enable private vulnerability reporting before announcing the release.

From the reviewed repository source root, first inspect identity:

```sh
git config --get user.name
git config --get user.email
```

If either is absent or private, stop and configure an approved public identity yourself. After intentional review, update only release metadata and its manifest entries:

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
import importlib.util, json, hashlib
root = Path.cwd()
spec = importlib.util.spec_from_file_location('op', root/'scripts/release_operator.py')
op = importlib.util.module_from_spec(spec); spec.loader.exec_module(op)
op.verify()
manifest = json.loads((root/'SOURCE-MANIFEST.json').read_text())
for name in ['package.json', 'package-lock.json']:
    path = root/name; value = json.loads(path.read_text())
    value['version'] = '1.0.0'
    if name == 'package-lock.json': value['packages']['']['version'] = '1.0.0'
    path.write_text(json.dumps(value, indent=2)+'\n')
    manifest[name] = hashlib.sha256(path.read_bytes()).hexdigest()
(root/'SOURCE-MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
PY
make build
make test
make audit
git init -b main
git add -- .
git diff --cached --stat
git diff --cached --check
git ls-files
```

Inspect the staged list and complete the contextual secret/private-data review. Ignoring a file does not remove it if it was already tracked. Do not include node_modules, .venv, .local, compiled dist, logs, credentials, model weights or raw state. After review:

```sh
git commit -m "Release Sanctum v1.0.0 source"
git tag -a v1.0.0 -m "Sanctum v1.0.0"
```

Only after explicit approval for the exact public repository, set its owner/name and run:

```sh
: "${SANCTUM_GITHUB_REPOSITORY:?Set the approved OWNER/REPOSITORY first}"
gh repo create "$SANCTUM_GITHUB_REPOSITORY" --public --description "Mac-owned personal AI authority with bounded local tools and replaceable reasoning"
git remote add origin "git@github.com:${SANCTUM_GITHUB_REPOSITORY}.git"
git push -u origin main
git push origin v1.0.0
gh api --method PUT "repos/${SANCTUM_GITHUB_REPOSITORY}/private-vulnerability-reporting"
gh release create v1.0.0 --repo "$SANCTUM_GITHUB_REPOSITORY" --verify-tag --title "Sanctum v1.0.0" --notes-file CHANGELOG.md
```

If private reporting cannot be enabled, do not announce the security reporting channel as operational. A source release is not a production cutover. Follow [migration and rollback](migration.md) separately.
