#!/usr/bin/env python3
"""
Read-only Google Calendar broker for Hybrid Personal AI.

Security properties:
- fixed Unix socket
- GET-only HTTP surface
- fixed ai-calendar-read wrapper
- bounded inputs / bounded output
- no shell=True
- no Calendar write endpoints
- no Calendar content logged
"""

from __future__ import annotations

import json
import os
import socketserver
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

HOME = Path.home()
WRAPPER = Path(__file__).with_name("ai-calendar-read")
SOCKET_PATH = (
    Path(os.environ.get("VINCEAI_CACHE_DIR", HOME / ".cache/vinceai"))
    / "calendar-read.sock"
)

MAX_RESPONSE_BYTES = 96 * 1024
SUBPROCESS_TIMEOUT = 20

os.umask(0o077)


def bounded_int(raw: str | None, default: int, low: int, high: int) -> int:
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("invalid integer") from exc
    if not (low <= value <= high):
        raise ValueError("integer outside allowed range")
    return value


def bounded_text(
    raw: str | None,
    default: str,
    maximum: int,
    *,
    required: bool = False,
) -> str:
    value = default if raw is None else raw
    if required and not value:
        raise ValueError("required value missing")
    if len(value) > maximum or "\n" in value or "\r" in value:
        raise ValueError("invalid text parameter")
    return value


def first(qs: dict[str, list[str]], key: str) -> str | None:
    values = qs.get(key)
    return values[0] if values else None


def run_wrapper(args: list[str]) -> Any:
    proc = subprocess.run(
        [str(WRAPPER), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
        check=False,
        env={
            **os.environ,
            "PATH": os.environ.get(
                "PATH", "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
            ),
        },
    )
    if proc.returncode != 0:
        # Do not forward raw stderr because it can contain provider/account details.
        raise RuntimeError(f"calendar wrapper failed rc={proc.returncode}")

    encoded = proc.stdout.encode("utf-8", errors="replace")
    if len(encoded) > MAX_RESPONSE_BYTES:
        raise RuntimeError("calendar response exceeded size cap")

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("calendar wrapper returned invalid JSON") from exc


def primary(payload: Any) -> Any:
    """
    Tolerate gog result envelopes while preferring --results-only output.
    """
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return payload

    for key in ("data", "events", "items", "calendars", "result", "results"):
        if key in payload:
            candidate = payload[key]
            if isinstance(candidate, dict):
                nested = primary(candidate)
                if nested is not candidate:
                    return nested
            return candidate
    return payload


def pick(d: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in d and d[name] not in (None, ""):
            return d[name]
    return None


def compact_calendar(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"value": str(item)[:500]}
    out = {
        "id": pick(item, "id", "calendarId"),
        "summary": pick(item, "summary", "name"),
        "primary": pick(item, "primary"),
        "selected": pick(item, "selected"),
        "timeZone": pick(item, "timeZone", "timezone"),
        "accessRole": pick(item, "accessRole"),
    }
    return {k: v for k, v in out.items() if v is not None}


def event_time(item: dict[str, Any], side: str) -> Any:
    local_key = f"{side}Local"
    if local_key in item and item[local_key] not in (None, ""):
        return item[local_key]
    value = item.get(side)
    if isinstance(value, dict):
        return value.get("dateTime") or value.get("date")
    return value


def compact_event(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"value": str(item)[:1000]}

    attendees = item.get("attendees")
    attendee_count = len(attendees) if isinstance(attendees, list) else None

    out = {
        "calendarId": pick(item, "calendarId", "calendar_id", "calendar"),
        "id": pick(item, "id", "eventId"),
        "summary": pick(item, "summary", "title"),
        "start": event_time(item, "start"),
        "end": event_time(item, "end"),
        "startDayOfWeek": pick(item, "startDayOfWeek"),
        "endDayOfWeek": pick(item, "endDayOfWeek"),
        "timeZone": pick(item, "timezone", "timeZone", "eventTimezone"),
        "location": pick(item, "location"),
        "status": pick(item, "status"),
        "allDay": pick(item, "allDay"),
        "attendeeCount": attendee_count,
    }
    return {k: v for k, v in out.items() if v is not None}


def compact_event_detail(payload: Any) -> dict[str, Any]:
    item = primary(payload)
    if not isinstance(item, dict):
        return {"value": str(item)[:4000]}

    # Keep detail bounded. gog --wrap-untrusted is used for this call, so
    # free-form fetched strings retain provider-side untrusted markers too.
    attendees_out: list[dict[str, Any]] = []
    attendees = item.get("attendees")
    if isinstance(attendees, list):
        for attendee in attendees[:20]:
            if isinstance(attendee, dict):
                a = {
                    "email": pick(attendee, "email"),
                    "displayName": pick(attendee, "displayName", "name"),
                    "responseStatus": pick(attendee, "responseStatus", "status"),
                    "self": pick(attendee, "self"),
                }
                attendees_out.append({k: v for k, v in a.items() if v is not None})

    organizer = item.get("organizer")
    organizer_out: Any = organizer
    if isinstance(organizer, dict):
        organizer_out = {
            k: v
            for k, v in {
                "email": pick(organizer, "email"),
                "displayName": pick(organizer, "displayName", "name"),
                "self": pick(organizer, "self"),
            }.items()
            if v is not None
        }

    out = compact_event(item)
    out.update(
        {
            "description": pick(item, "description"),
            "htmlLink": pick(item, "htmlLink"),
            "organizer": organizer_out,
            "attendees": attendees_out or None,
            "recurrence": pick(item, "recurrence"),
            "conferenceData": pick(item, "conferenceData"),
        }
    )
    return {k: v for k, v in out.items() if v is not None}


class UnixHTTPServer(socketserver.UnixStreamServer):
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = "CalendarReadBroker/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        # Never log URL/query strings because Calendar searches are personal data.
        sys.stderr.write(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"calendar-read-broker request status={args[1] if len(args) > 1 else '?'}\n"
        )

    def send_json(self, status: int, value: Any) -> None:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        if len(raw) > MAX_RESPONSE_BYTES:
            status = 500
            raw = b'{"ok":false,"error":"broker response exceeded cap"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query, keep_blank_values=False)

            if parsed.path == "/health":
                self.send_json(
                    200,
                    {
                        "ok": True,
                        "service": "calendar-read-broker",
                        "mode": "read-only",
                        "content_is_untrusted": True,
                    },
                )
                return

            if parsed.path == "/calendars":
                limit = bounded_int(first(qs, "limit"), 20, 1, 30)
                payload = primary(run_wrapper(["calendars", str(limit)]))
                values = payload if isinstance(payload, list) else [payload]
                self.send_json(
                    200,
                    {
                        "ok": True,
                        "untrusted": True,
                        "source": "google_calendar",
                        "content_is_untrusted": True,
                        "data": [compact_calendar(v) for v in values[:limit]],
                    },
                )
                return

            if parsed.path in ("/events", "/search"):
                calendar = bounded_text(first(qs, "calendar"), "all", 200)
                from_value = bounded_text(first(qs, "from"), "today", 80)
                to_value = bounded_text(first(qs, "to"), "-", 80)
                default_days = 90 if parsed.path == "/search" else 1
                days = bounded_int(first(qs, "days"), default_days, 1, 365)
                limit = bounded_int(first(qs, "limit"), 12, 1, 20)
                query = "-"
                if parsed.path == "/search":
                    query = bounded_text(first(qs, "q"), "", 200, required=True)

                payload = primary(
                    run_wrapper(
                        [
                            "events",
                            calendar,
                            from_value,
                            to_value,
                            str(days),
                            str(limit),
                            query,
                        ]
                    )
                )
                values = payload if isinstance(payload, list) else [payload]
                self.send_json(
                    200,
                    {
                        "ok": True,
                        "untrusted": True,
                        "source": "google_calendar",
                        "content_is_untrusted": True,
                        "data": [compact_event(v) for v in values[:limit]],
                    },
                )
                return

            if parsed.path == "/event":
                calendar_id = bounded_text(
                    first(qs, "calendar_id"), "", 300, required=True
                )
                event_id = bounded_text(first(qs, "event_id"), "", 600, required=True)
                payload = run_wrapper(["event", calendar_id, event_id])
                self.send_json(
                    200,
                    {
                        "ok": True,
                        "untrusted": True,
                        "source": "google_calendar",
                        "content_is_untrusted": True,
                        "data": compact_event_detail(payload),
                    },
                )
                return

            self.send_json(404, {"ok": False, "error": "not found"})

        except ValueError:
            self.send_json(400, {"ok": False, "error": "invalid bounded request"})
        except subprocess.TimeoutExpired:
            self.send_json(504, {"ok": False, "error": "calendar provider timed out"})
        except Exception as exc:
            # Log only exception class; never provider data or request content.
            sys.stderr.write(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"calendar-read-broker internal_error={type(exc).__name__}\n"
            )
            self.send_json(
                502, {"ok": False, "error": "calendar read backend unavailable"}
            )

    def do_POST(self) -> None:
        self.send_json(405, {"ok": False, "error": "read-only broker"})

    def do_PUT(self) -> None:
        self.send_json(405, {"ok": False, "error": "read-only broker"})

    def do_PATCH(self) -> None:
        self.send_json(405, {"ok": False, "error": "read-only broker"})

    def do_DELETE(self) -> None:
        self.send_json(405, {"ok": False, "error": "read-only broker"})


def main() -> int:
    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(SOCKET_PATH.parent, 0o700)

    # Lifecycle helper is responsible for proving a socket stale before startup.
    if SOCKET_PATH.exists():
        print(
            "refusing to unlink existing socket; use calendar-read-control",
            file=sys.stderr,
        )
        return 2

    server = UnixHTTPServer(str(SOCKET_PATH), Handler)
    os.chmod(SOCKET_PATH, 0o600)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        try:
            SOCKET_PATH.unlink()
        except FileNotFoundError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
