# Release checklist and publication commands

## V1.1.0 release completion

V1.1.0 is a completed minor-release candidate. Its source version is `1.1.0`; the immutable V1.0.0 tag and release are not recreated or moved. The release-completion PR must merge into `v1.1-dev` before an owner creates the `v1.1.0` tag and GitHub release. Production migration remains separate.

Review [the V1.1 release record](../history/v1.1/V1.1-RELEASE-COMPLETION.md), [structured-editing evidence](../history/v1.1/project-3/PROJECT-3-STRUCTURED-EDITING.md), documented limitations, source audit and CI before tagging. Do not treat the completion PR itself as authorization to move `main`, delete private evidence, change a private runtime, or launch compute.

After the PR is merged and the intended release commit is verified, use an approved public Git identity and run:

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
