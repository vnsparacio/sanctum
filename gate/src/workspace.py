"""Owner-selected isolated Git worktrees for Work Mode; never model-addressable."""
from pathlib import Path
import os
import subprocess
from common import Refused, canonical

def _run(args, cwd=None):
    try:
        return subprocess.run(args, cwd=cwd, env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'}, check=True, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        raise Refused('workspace_git_unavailable') from None

def _real_directory(value):
    p=Path(value)
    if not p.is_absolute() or p.is_symlink() or not p.is_dir(): raise Refused('workspace_path')
    return p.resolve(strict=True)

def contained(root, candidate):
    root=_real_directory(root); candidate=Path(candidate)
    if not candidate.is_absolute() or '..' in candidate.parts: return False
    try: return candidate.resolve(strict=True).is_relative_to(root)
    except FileNotFoundError: return candidate.parent.resolve(strict=True).is_relative_to(root)

def create_worktree(repository, staging_root, name):
    """Create one detached worktree from a clean canonical checkout.

    `repository`, `staging_root`, and `name` are supplied by trusted owner
    configuration.  The model receives only the resulting opaque workspace
    identity, never any of these host paths.
    """
    source=_real_directory(repository); staging=_real_directory(staging_root)
    if type(name) is not str or not name or '/' in name or '\\' in name or name in {'.','..'}: raise Refused('workspace_name')
    top=Path(_run(['/usr/bin/git','rev-parse','--show-toplevel'],source))
    if top!=source: raise Refused('workspace_not_repository_root')
    if _run(['/usr/bin/git','status','--porcelain'],source): raise Refused('workspace_source_dirty')
    target=staging/name
    if target.exists() or target.is_symlink() or not contained(staging,target): raise Refused('workspace_target')
    base=_run(['/usr/bin/git','rev-parse','HEAD'],source)
    _run(['/usr/bin/git','worktree','add','--detach',str(target),base],source)
    try:
        root=_real_directory(target)
        if root!=target.resolve() or not contained(staging,root): raise Refused('workspace_containment')
        common=_run(['/usr/bin/git','rev-parse','--git-common-dir'],root)
        if not common: raise Refused('workspace_git_identity')
        return {'workspace_id':name,'root':str(root),'base_commit':base,'git_common_dir':common,'initial_status':_run(['/usr/bin/git','status','--porcelain'],root)}
    except Exception:
        # Cleanup is intentionally delegated to owner review; a failed check
        # must remain visible rather than deleting an uncertain worktree.
        raise Refused('workspace_verification') from None
