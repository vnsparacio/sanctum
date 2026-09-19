#!/usr/bin/env python3
"""
Phase 9A.4 persistent local session privacy state.

State is metadata-only and monotonic:
    CLEAN -> PERSONAL -> RESTRICTED

UNKNOWN is used for a session that has not been explicitly created by the trusted
local session lifecycle. UNKNOWN fails closed elsewhere.

Automatic downgrade is impossible. Returning to CLEAN requires an explicit RESET
operation representing a genuinely new/cleared context.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_RANK = {
    "UNKNOWN": -1,
    "CLEAN": 0,
    "PERSONAL": 1,
    "RESTRICTED": 2,
}

SESSION_RE = re.compile(r"^[A-Za-z0-9._:@+-]{1,200}$")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def validate_session_id(session_id: str) -> str:
    if not SESSION_RE.fullmatch(session_id):
        raise ValueError(
            "session id must be 1-200 chars using only " "letters, numbers, . _ : @ + -"
        )
    return session_id


class SessionStore:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_file = state_dir / "sessions.json"
        self.audit_file = state_dir / "audit.jsonl"
        self.lock_file = state_dir / ".lock"

    def ensure_storage(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state_dir, 0o700)

        if not self.state_file.exists():
            self._atomic_write(
                {
                    "schema": "hybrid-ai-session-state/v1",
                    "sessions": {},
                }
            )
        else:
            os.chmod(self.state_file, 0o600)

        if not self.audit_file.exists():
            fd = os.open(
                self.audit_file,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o600,
            )
            os.close(fd)
        else:
            os.chmod(self.audit_file, 0o600)

        if not self.lock_file.exists():
            fd = os.open(
                self.lock_file,
                os.O_WRONLY | os.O_CREAT,
                0o600,
            )
            os.close(fd)
        else:
            os.chmod(self.lock_file, 0o600)

    def _atomic_write(self, data: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".sessions.",
            suffix=".tmp",
            dir=self.state_dir,
            text=True,
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, self.state_file)
            os.chmod(self.state_file, 0o600)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

    def _load(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {
                "schema": "hybrid-ai-session-state/v1",
                "sessions": {},
            }
        with self.state_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("schema") != "hybrid-ai-session-state/v1":
            raise RuntimeError("unsupported or corrupted session-state schema")
        if not isinstance(data.get("sessions"), dict):
            raise RuntimeError("corrupted session-state store")
        return data

    def _append_audit(self, event: dict[str, Any]) -> None:
        # Deliberately metadata only. Never add prompt/tool contents here.
        safe = {
            "ts": event["ts"],
            "session_id": event["session_id"],
            "event": event["event"],
            "before": event.get("before"),
            "after": event.get("after"),
            "reason": event.get("reason"),
            "generation": event.get("generation"),
        }
        with self.audit_file.open("a", encoding="utf-8") as f:
            json.dump(safe, f, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(self.audit_file, 0o600)

    def _locked(self):
        self.ensure_storage()
        lock = self.lock_file.open("r+")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return lock

    def get(self, session_id: str) -> dict[str, Any]:
        validate_session_id(session_id)
        self.ensure_storage()
        data = self._load()
        rec = data["sessions"].get(session_id)
        if rec is None:
            return {
                "session_id": session_id,
                "privacy": "UNKNOWN",
                "generation": None,
                "created_at": None,
                "updated_at": None,
                "reason": "session has not been explicitly started",
            }
        return {"session_id": session_id, **rec}

    def start(self, session_id: str) -> dict[str, Any]:
        validate_session_id(session_id)
        lock = self._locked()
        try:
            data = self._load()
            if session_id in data["sessions"]:
                raise RuntimeError(
                    "session already exists; use reset only for a genuinely new context"
                )
            now = utc_now()
            rec = {
                "privacy": "CLEAN",
                "generation": 1,
                "created_at": now,
                "updated_at": now,
                "last_reason": "trusted local session start",
            }
            data["sessions"][session_id] = rec
            self._atomic_write(data)
            self._append_audit(
                {
                    "ts": now,
                    "session_id": session_id,
                    "event": "START",
                    "before": "UNKNOWN",
                    "after": "CLEAN",
                    "reason": "trusted local session start",
                    "generation": 1,
                }
            )
            return {"session_id": session_id, **rec}
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()

    def observe(
        self,
        session_id: str,
        observed_privacy: str,
        *,
        reason: str,
    ) -> dict[str, Any]:
        validate_session_id(session_id)
        if observed_privacy not in ("CLEAN", "PERSONAL", "RESTRICTED"):
            raise ValueError("observed privacy must be CLEAN, PERSONAL, or RESTRICTED")
        if not reason or len(reason) > 240:
            raise ValueError("reason must be 1-240 characters")

        lock = self._locked()
        try:
            data = self._load()
            rec = data["sessions"].get(session_id)
            if rec is None:
                raise RuntimeError(
                    "session is UNKNOWN; trusted lifecycle must start it before observation"
                )

            before = rec["privacy"]
            after = max(
                (before, observed_privacy),
                key=lambda s: STATE_RANK[s],
            )
            now = utc_now()

            rec["privacy"] = after
            rec["updated_at"] = now
            rec["last_reason"] = reason
            data["sessions"][session_id] = rec
            self._atomic_write(data)
            self._append_audit(
                {
                    "ts": now,
                    "session_id": session_id,
                    "event": "OBSERVE",
                    "before": before,
                    "after": after,
                    "reason": reason,
                    "generation": rec["generation"],
                }
            )
            return {
                "session_id": session_id,
                **rec,
                "changed": before != after,
                "observed": observed_privacy,
            }
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()

    def reset(self, session_id: str, *, reason: str) -> dict[str, Any]:
        validate_session_id(session_id)
        if reason != "new-context":
            raise ValueError(
                "reset requires exact reason 'new-context'; "
                "downgrade is not a routine operation"
            )

        lock = self._locked()
        try:
            data = self._load()
            rec = data["sessions"].get(session_id)
            if rec is None:
                raise RuntimeError("cannot reset unknown session; start it instead")

            before = rec["privacy"]
            now = utc_now()
            generation = int(rec["generation"]) + 1
            new_rec = {
                "privacy": "CLEAN",
                "generation": generation,
                "created_at": rec["created_at"],
                "updated_at": now,
                "last_reason": "explicit new-context reset",
            }
            data["sessions"][session_id] = new_rec
            self._atomic_write(data)
            self._append_audit(
                {
                    "ts": now,
                    "session_id": session_id,
                    "event": "RESET",
                    "before": before,
                    "after": "CLEAN",
                    "reason": "new-context",
                    "generation": generation,
                }
            )
            return {"session_id": session_id, **new_rec}
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()

    def list_sessions(self) -> list[dict[str, Any]]:
        self.ensure_storage()
        data = self._load()
        return [
            {"session_id": sid, **rec} for sid, rec in sorted(data["sessions"].items())
        ]


def default_state_dir() -> Path:
    return Path.home() / "Projects" / "hybrid-ai" / "router" / "state"


def human(rec: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Session:    {rec['session_id']}",
            f"Privacy:    {rec['privacy']}",
            f"Generation: {rec.get('generation') if rec.get('generation') is not None else '-'}",
            f"Updated:    {rec.get('updated_at') or '-'}",
            f"Reason:     {rec.get('last_reason') or rec.get('reason') or '-'}",
        ]
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description="Manage local privacy state for one AI session."
    )
    p.add_argument("--state-dir", default=str(default_state_dir()))
    sub = p.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start")
    p_start.add_argument("session_id")

    p_get = sub.add_parser("get")
    p_get.add_argument("session_id")

    p_obs = sub.add_parser("observe")
    p_obs.add_argument("session_id")
    p_obs.add_argument(
        "privacy",
        choices=("CLEAN", "PERSONAL", "RESTRICTED"),
    )
    p_obs.add_argument("--reason", required=True)

    p_reset = sub.add_parser("reset")
    p_reset.add_argument("session_id")
    p_reset.add_argument("--reason", required=True)

    sub.add_parser("list")

    args = p.parse_args()
    store = SessionStore(Path(args.state_dir))

    try:
        if args.command == "start":
            rec = store.start(args.session_id)
            print(human(rec))
        elif args.command == "get":
            rec = store.get(args.session_id)
            print(human(rec))
        elif args.command == "observe":
            rec = store.observe(
                args.session_id,
                args.privacy,
                reason=args.reason,
            )
            print(human(rec))
            print(f"Changed:    {'YES' if rec['changed'] else 'NO'}")
        elif args.command == "reset":
            rec = store.reset(args.session_id, reason=args.reason)
            print(human(rec))
        elif args.command == "list":
            sessions = store.list_sessions()
            if not sessions:
                print("No sessions.")
            for i, rec in enumerate(sessions):
                if i:
                    print()
                print(human(rec))
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    import sys

    raise SystemExit(main())
