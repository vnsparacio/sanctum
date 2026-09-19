"""Host-owned permanent retirement; historical storage is inspection-only.

No configuration value can authorize PRIVATE_80B inference. Empty historical
storage is never initialized or locked as a second inference lease store.
"""

import math
import sqlite3
from pathlib import Path

from common import Refused, strict_json

RETIRED = "private_80b_retired"


def historical_ownership(root):
    root = Path(root)
    state_path, db = root / "gpu.json", root / "control.sqlite"
    if state_path.is_symlink() or db.is_symlink():
        raise Refused("retired_ownership_unknown")
    state = strict_json(state_path.read_text()) if state_path.exists() else {}
    if type(state) is not dict:
        raise Refused("retired_ownership_unknown")
    leases = active = 0
    if db.exists():
        try:
            with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as c:
                leases, active = c.execute(
                    "select count(*),coalesce(sum(active),0) from leases"
                ).fetchone()
        except sqlite3.Error:
            raise Refused("retired_ownership_unknown") from None
    pending = bool(
        leases
        or active
        or any(state.get(k) for k in ("pod_id", "pod_name", "allocation_uncertain"))
        or (state.get("allocation_id") and not state.get("absent_confirmed_at"))
        or state.get("phase", "OFFLINE") not in ("OFFLINE", "RETIRED")
    )
    return {
        "leases": leases,
        "active_requests": active,
        "pending": pending,
        "confirmed": not pending
        and state.get("phase") == "RETIRED"
        and type(state.get("retired_confirmed_at")) in (int, float)
        and math.isfinite(state["retired_confirmed_at"])
        and state["retired_confirmed_at"] > 0,
    }


def require_reconciled(root, *, confirmed=False):
    facts = historical_ownership(root)
    if facts["leases"]:
        raise Refused("experiment_existing_leases")
    if facts["pending"] or (confirmed and not facts["confirmed"]):
        raise Refused("retired_ownership_unreconciled")
    return facts
