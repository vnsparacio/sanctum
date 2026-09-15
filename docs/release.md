# Release checklist and later publication commands

The Sanctum V1 release uses the [documented qualification exceptions](qualification.md) and [rename/publication checks](publication.md). The owner authorized a public repository and v1.0.0 release. The commands below describe the initial-publication procedure; do not rerun initialization or recreate an existing tag/release. Production migration remains separate.

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
