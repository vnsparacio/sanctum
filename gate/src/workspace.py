"""Mac-owned isolated Git worktrees and no-follow file operations for Work Mode."""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path, PurePosixPath

from common import Refused

GIT_ENV = {
    "PATH": "/usr/bin:/bin",
    "LANG": "C",
    "LC_ALL": "C",
    "HOME": "/nonexistent",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
}
GIT = ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-c", "diff.external="]
TASK = re.compile(r"^[a-f0-9]{32}$")


def _run(args, cwd=None, input=None, timeout=30):
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            env=GIT_ENV,
            check=True,
            capture_output=True,
            text=True,
            input=input,
            timeout=timeout,
        ).stdout.strip()
    except Exception:
        raise Refused("workspace_git_unavailable") from None


def _real_directory(value):
    p = Path(value)
    if not p.is_absolute() or p.is_symlink() or not p.is_dir():
        raise Refused("workspace_path")
    return p.resolve(strict=True)


def contained(root, candidate):
    root = _real_directory(root)
    candidate = Path(candidate)
    if not candidate.is_absolute() or ".." in candidate.parts:
        return False
    try:
        return candidate.resolve(strict=True).is_relative_to(root)
    except FileNotFoundError:
        try:
            return candidate.parent.resolve(strict=True).is_relative_to(root)
        except FileNotFoundError:
            return False


def _safe_relative(value, allow_empty=False):
    if (
        type(value) is not str
        or "\x00" in value
        or value.startswith("/")
        or "\\" in value
    ):
        raise Refused("workspace_relative_path")
    p = PurePosixPath(value or ".")
    if (not allow_empty and value in ("", ".")) or any(
        x in ("", "..") or x.lower() == ".git" for x in p.parts
    ):
        raise Refused("workspace_relative_path")
    return p


def resolve_entry(root, relative, must_exist=True):
    base = _real_directory(root)
    rel = _safe_relative(relative)
    current = base
    for part in rel.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            info = os.lstat(current)
            if stat.S_ISLNK(info.st_mode) or (
                stat.S_ISREG(info.st_mode) and info.st_nlink > 1
            ):
                raise Refused("workspace_link")
        elif must_exist:
            raise Refused("workspace_missing")
    try:
        parent = current.parent.resolve(strict=True)
    except FileNotFoundError:
        raise Refused("workspace_missing") from None
    if not parent.is_relative_to(base):
        raise Refused("workspace_containment")
    if must_exist and not current.resolve(strict=True).is_relative_to(base):
        raise Refused("workspace_containment")
    return current


def _create_sparse(staging, name, disk_bytes):
    if (
        os.uname().sysname != "Darwin"
        or type(disk_bytes) is not int
        or not 512 * 1024 * 1024 <= disk_bytes <= 8 * 1024**3
    ):
        raise Refused("workspace_disk_profile")
    image = staging / (name + ".sparsebundle")
    mount = staging / (name + "-mount")
    if image.exists() or mount.exists() or image.is_symlink() or mount.is_symlink():
        raise Refused("workspace_target")
    mount.mkdir(mode=0o700)
    try:
        subprocess.run(
            [
                "/usr/bin/hdiutil",
                "create",
                "-size",
                str(disk_bytes),
                "-type",
                "SPARSEBUNDLE",
                "-fs",
                "APFS",
                "-volname",
                "SanctumWork-" + name,
                str(image),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        subprocess.run(
            [
                "/usr/bin/hdiutil",
                "attach",
                str(image),
                "-nobrowse",
                "-mountpoint",
                str(mount),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return image, _real_directory(mount)
    except Exception:
        try:
            subprocess.run(
                ["/usr/bin/hdiutil", "detach", str(mount), "-force"],
                capture_output=True,
                timeout=30,
            )
        except Exception:
            pass
        raise Refused("workspace_disk_unavailable") from None


def create_worktree(repository, staging_root, name, disk_bytes=None):
    """Create a detached worktree; trusted configuration supplies all host paths."""
    source = _real_directory(repository)
    staging = _real_directory(staging_root)
    if type(name) is not str or not (
        TASK.fullmatch(name) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name)
    ):
        raise Refused("workspace_name")
    top = Path(_run(GIT + ["rev-parse", "--show-toplevel"], source))
    if top != source:
        raise Refused("workspace_not_repository_root")
    if _run(GIT + ["status", "--porcelain"], source):
        raise Refused("workspace_source_dirty")
    image = mount = None
    target = staging / name
    if disk_bytes is not None:
        image, mount = _create_sparse(staging, name, disk_bytes)
        target = mount / "worktree"
    if (
        target.exists()
        or target.is_symlink()
        or not contained(mount or staging, target)
    ):
        raise Refused("workspace_target")
    base = _run(GIT + ["rev-parse", "HEAD"], source)
    _run(GIT + ["worktree", "add", "--detach", str(target), base], source)
    try:
        root = _real_directory(target)
        if root != target.resolve() or not contained(mount or staging, root):
            raise Refused("workspace_containment")
        common = _run(GIT + ["rev-parse", "--git-common-dir"], root)
        if not common:
            raise Refused("workspace_git_identity")
        return {
            "workspace_id": name,
            "root": str(root),
            "base_commit": base,
            "git_common_dir": common,
            "initial_status": _run(GIT + ["status", "--porcelain"], root),
            "disk_image": str(image) if image else None,
            "mountpoint": str(mount) if mount else None,
            "disk_bytes": disk_bytes,
        }
    except Exception:
        raise Refused("workspace_verification") from None


def list_entries(root, relative="", max_entries=100):
    if type(max_entries) is not int or not 1 <= max_entries <= 200:
        raise Refused("workspace_list_limit")
    base = _real_directory(root)
    directory = base if relative in ("", ".") else resolve_entry(base, relative)
    if not directory.is_dir():
        raise Refused("workspace_not_directory")
    rows = []
    for item in sorted(directory.iterdir(), key=lambda p: p.name):
        if item.name == ".git":
            continue
        info = os.lstat(item)
        if stat.S_ISLNK(info.st_mode) or (
            stat.S_ISREG(info.st_mode) and info.st_nlink > 1
        ):
            continue
        rows.append(
            {
                "path": str(item.relative_to(base)),
                "kind": "directory" if stat.S_ISDIR(info.st_mode) else "file",
                "size": info.st_size,
            }
        )
        if len(rows) >= max_entries:
            break
    return {"entries": rows, "truncated": len(rows) >= max_entries}


def read_text(root, relative, max_chars=12000):
    if type(max_chars) is not int or not 1 <= max_chars <= 24000:
        raise Refused("workspace_read_limit")
    path = resolve_entry(root, relative)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
        raise Refused("workspace_not_regular")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise Refused("workspace_binary")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("workspace_encoding") from None
    return {
        "path": relative,
        "text": text[:max_chars],
        "truncated": len(text) > max_chars,
        "size": len(raw),
    }


def apply_patch(root, patch):
    if (
        type(patch) is not str
        or not patch
        or len(patch.encode()) > 48000
        or "\x00" in patch
    ):
        raise Refused("workspace_patch_limit")
    if re.search(r"(?m)^(?:new file mode|old mode|new mode) 120000$", patch):
        raise Refused("workspace_symlink_patch")
    names = []
    for _, name in re.findall(r"(?m)^(---|\+\+\+) (?:[ab]/)?([^\t\n]+)", patch):
        if name == "/dev/null":
            continue
        rel = _safe_relative(name)
        names.append(str(rel))
        candidate = Path(root) / rel
        if candidate.exists() or candidate.is_symlink():
            resolve_entry(root, str(rel))
        elif str(rel.parent) != ".":
            resolve_entry(root, str(rel.parent))
    if not names:
        raise Refused("workspace_patch_shape")
    # Model-authored unified diffs often carry stale hunk line counts even
    # when their context is exact.  Git's --recount safely derives those
    # counts from the hunk body.  A context mismatch is an ordinary rejected
    # proposal, not a loss of the worktree's Git identity; keep the two cases
    # distinct so the reasoner can inspect and repair instead of looping on a
    # false WORKSPACE_GIT_UNAVAILABLE signal.
    try:
        checked = subprocess.run(
            GIT + ["apply", "--check", "--recount", "--whitespace=nowarn", "-"],
            cwd=root,
            env=GIT_ENV,
            capture_output=True,
            text=True,
            input=patch,
            timeout=30,
        )
    except Exception:
        raise Refused("workspace_git_unavailable") from None
    if checked.returncode:
        diagnostic = (
            (
                checked.stderr
                or checked.stdout
                or "Patch context did not match the current workspace."
            )
            .replace(str(root), "<workspace>")
            .replace("\x00", "")[-4000:]
        )
        return {
            "ok": False,
            "code": "WORKSPACE_PATCH_REJECTED",
            "diagnostic": diagnostic,
            "executionState": "NOT_STARTED",
        }
    try:
        applied = subprocess.run(
            GIT + ["apply", "--recount", "--whitespace=nowarn", "-"],
            cwd=root,
            env=GIT_ENV,
            capture_output=True,
            text=True,
            input=patch,
            timeout=30,
        )
    except Exception:
        raise Refused("workspace_git_unavailable") from None
    if applied.returncode:
        raise Refused("workspace_git_unavailable")
    diff = _run(GIT + ["diff", "--no-ext-diff", "--binary", "--"], root)
    import hashlib

    return {
        "ok": True,
        "changed": sorted(set(names)),
        "diff_digest": hashlib.sha256(diff.encode()).hexdigest(),
        "executionState": "COMPLETED",
    }


def inspect_worktree(root, operation):
    """Fixed host Git inspection. It never invokes repository scripts or hooks."""
    root = _real_directory(root)
    if operation == "status":
        output = _run(GIT + ["status", "--porcelain=v1", "--untracked-files=all"], root)
    elif operation == "diff":
        try:
            tracked = subprocess.run(
                GIT + ["diff", "--no-ext-diff", "--no-textconv", "--binary", "--"],
                cwd=root,
                env=GIT_ENV,
                check=True,
                capture_output=True,
                timeout=30,
            ).stdout
            listed = subprocess.run(
                GIT + ["ls-files", "--others", "--exclude-standard", "-z", "--"],
                cwd=root,
                env=GIT_ENV,
                check=True,
                capture_output=True,
                timeout=30,
            ).stdout
            additions = []
            for raw_name in sorted(name for name in listed.split(b"\0") if name):
                relative = raw_name.decode("utf-8")
                path = resolve_entry(root, relative)
                info = os.lstat(path)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise Refused("workspace_link")
                rendered = subprocess.run(
                    GIT
                    + [
                        "diff",
                        "--no-index",
                        "--no-ext-diff",
                        "--no-textconv",
                        "--binary",
                        "--",
                        "/dev/null",
                        relative,
                    ],
                    cwd=root,
                    env=GIT_ENV,
                    capture_output=True,
                    timeout=30,
                )
                if rendered.returncode != 1 or not rendered.stdout:
                    raise Refused("workspace_git_unavailable")
                additions.append(rendered.stdout)
            output = (tracked + b"".join(additions)).decode("utf-8").rstrip("\n")
        except Refused:
            raise
        except Exception:
            raise Refused("workspace_git_unavailable") from None
    else:
        raise Refused("workspace_inspection_operation")
    raw = output.encode()
    if len(raw) > 65536:
        raise Refused("workspace_inspection_limit")
    import hashlib

    return {
        "ok": True,
        "code": "OK",
        "executionState": "COMPLETED",
        "output": output,
        "output_digest": hashlib.sha256(raw).hexdigest(),
        "output_bytes": len(raw),
        "elapsed_ms": 0,
        "runner": {"kind": "HOST_FIXED_GIT"},
        "limits": {"output_bytes": 65536},
        "container_absent": True,
    }


def cleanup_worktree(repository, workspace):
    source = _real_directory(repository)
    root_path = Path(workspace["root"])
    mount = workspace.get("mountpoint")
    image = workspace.get("disk_image")
    if root_path.exists() or root_path.is_symlink():
        root = _real_directory(root_path)
        _run(GIT + ["worktree", "remove", "--force", str(root)], source, timeout=60)
    elif not mount or root_path != Path(mount) / "worktree":
        raise Refused("workspace_cleanup_scope")
    else:
        # A prior cleanup may have removed the registered worktree before a
        # busy sparse image refused to detach. Pruning is fixed and idempotent.
        _run(GIT + ["worktree", "prune", "--expire", "now"], source, timeout=60)
    if mount:
        staging = Path(mount).parent.resolve(strict=True)
        mp = Path(mount).resolve(strict=True)
        if not mp.is_relative_to(staging):
            raise Refused("workspace_cleanup_scope")
        try:
            subprocess.run(
                ["/usr/bin/hdiutil", "detach", str(mp)],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except Exception:
            try:
                subprocess.run(
                    ["/usr/bin/hdiutil", "detach", "-force", str(mp)],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            except Exception:
                raise Refused("workspace_cleanup_uncertain") from None
        Path(mp).rmdir()
    if image:
        target = Path(image)
        if target.is_symlink() or target.parent.resolve(strict=True) != (
            Path(mount).parent.resolve(strict=True)
            if mount
            else target.parent.resolve(strict=True)
        ):
            raise Refused("workspace_cleanup_scope")
        shutil.rmtree(target)
    return {"cleaned": True}
