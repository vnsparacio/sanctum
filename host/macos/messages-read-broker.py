#!/usr/bin/env python3

import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.parse
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from socketserver import UnixStreamServer

SOCKET_PATH = str(
    Path(os.environ.get("VINCEAI_CACHE_DIR", Path.home() / ".cache/vinceai"))
    / "messages-read.sock"
)

BROKER = str(Path(__file__).with_name("ai-imsg-read"))
MESSAGE_DB = Path.home() / "Library/Messages/chat.db"
E164_PHONE = re.compile(r"\+[1-9][0-9]{7,14}\Z")
APPLE_EPOCH_SECONDS = 978307200


def run_broker(args):
    result = subprocess.run(
        [BROKER, *args],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or f"ai-imsg-read exited {result.returncode}"
        )

    # imsg JSON output is JSON Lines: one object per line.
    records = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        records.append(json.loads(line))

    return records


def keep_fields(record, fields):
    return {field: record[field] for field in fields if field in record}


def sanitize_chats(records):
    fields = (
        "id",
        "contact_name",
        "display_name",
        "participants",
        "is_group",
        "service",
        "last_message_at",
        "unread_count",
    )
    return [keep_fields(record, fields) for record in records]


def sanitize_messages(records):
    fields = (
        "chat_id",
        "chat_name",
        "sender",
        "text",
        "created_at",
        "is_from_me",
        "participants",
        "content_unavailable",
        "text_truncated",
    )
    return [keep_fields(record, fields) for record in records]


def apple_message_time(value):
    """Convert the Messages database's Apple-epoch seconds or subsecond ticks."""
    if not isinstance(value, int):
        return None
    magnitude = abs(value)
    divisor = (
        1_000_000_000
        if magnitude >= 10**17
        else 1_000_000 if magnitude >= 10**14 else 1_000 if magnitude >= 10**11 else 1
    )
    try:
        return (
            datetime.fromtimestamp(APPLE_EPOCH_SECONDS + value / divisor, UTC)
            .isoformat()
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        return None


def sender_history(sender, limit, database=MESSAGE_DB):
    """Read only inbound, ordinary messages from one exact E.164 sender."""
    if not E164_PHONE.fullmatch(sender):
        raise ValueError("sender must be an exact E.164 phone number")
    if not 1 <= limit <= 12:
        raise ValueError("invalid sender history limit")
    started = time.monotonic()
    uri = "file:" + urllib.parse.quote(str(database)) + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=2) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.set_progress_handler(
            lambda: int(time.monotonic() - started > 10), 1000
        )
        rows = connection.execute(
            """
            SELECT message.text, message.date
            FROM message JOIN handle ON handle.ROWID = message.handle_id
            WHERE handle.id = ? AND message.is_from_me = 0
              AND COALESCE(message.is_system_message, 0) = 0
              AND COALESCE(message.is_service_message, 0) = 0
              AND (COALESCE(message.is_empty, 0) = 0
                   OR COALESCE(message.cache_has_attachments, 0) != 0)
              AND COALESCE(message.associated_message_type, 0) = 0
              AND COALESCE(message.date_retracted, 0) = 0
            ORDER BY message.date DESC, message.ROWID DESC
            LIMIT ?
            """,
            (sender, limit),
        ).fetchall()
    records = []
    for body, date in rows:
        timestamp = apple_message_time(date)
        truncated = isinstance(body, str) and len(body) > 2000
        if truncated:
            text = body[:1970] + "\n[message text truncated]"
        else:
            text = body if isinstance(body, str) and body else None
        records.append(
            {
                "sender": sender,
                "text": text,
                "created_at": timestamp,
                "content_unavailable": text is None,
                "text_truncated": truncated,
            }
        )
    return records


def integer(value, default, minimum, maximum):
    if value is None:
        value = default

    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError("invalid integer")

    if value < minimum:
        raise ValueError("value below minimum")

    return min(value, maximum)


class Handler(BaseHTTPRequestHandler):

    server_version = "HybridAIMessagesRead/0.1"

    def log_message(self, format, *args):
        # Avoid logging queries/message metadata by default.
        return

    def reply(self, status, payload):
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # Read-only API: reject every POST.
        self.reply(
            405,
            {"ok": False, "error": "read-only broker"},
        )

    def do_PUT(self):
        self.do_POST()

    def do_PATCH(self):
        self.do_POST()

    def do_DELETE(self):
        self.do_POST()

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(
                parsed.query,
                keep_blank_values=True,
            )

            if parsed.path == "/health":
                self.reply(
                    200,
                    {
                        "ok": True,
                        "service": "messages-read-broker",
                        "mode": "read-only",
                    },
                )
                return

            if parsed.path == "/chats":
                limit = integer(
                    params.get("limit", ["5"])[0],
                    5,
                    1,
                    10,
                )

                records = sanitize_chats(run_broker(["chats", str(limit)]))

                self.reply(
                    200,
                    {"ok": True, "records": records},
                )
                return

            if parsed.path == "/history":
                chat_id = params.get("chat_id", [""])[0]

                if not chat_id.isdigit():
                    raise ValueError("chat_id must be numeric")

                limit = integer(
                    params.get("limit", ["6"])[0],
                    6,
                    1,
                    12,
                )

                records = sanitize_messages(
                    run_broker(["history", chat_id, str(limit)])
                )

                self.reply(
                    200,
                    {"ok": True, "records": records},
                )
                return

            if parsed.path == "/search":
                query = params.get("q", [""])[0]

                if not query:
                    raise ValueError("search query required")

                if len(query) > 200:
                    raise ValueError("search query too long")

                limit = integer(
                    params.get("limit", ["5"])[0],
                    5,
                    1,
                    8,
                )

                records = sanitize_messages(run_broker(["search", query, str(limit)]))

                self.reply(
                    200,
                    {"ok": True, "records": records},
                )
                return

            if parsed.path == "/sender-history":
                sender = params.get("sender", [""])[0]
                limit = integer(params.get("limit", ["10"])[0], 10, 1, 12)
                self.reply(
                    200,
                    {"ok": True, "records": sender_history(sender, limit)},
                )
                return

            self.reply(
                404,
                {"ok": False, "error": "not found"},
            )

        except ValueError as exc:
            self.reply(
                400,
                {"ok": False, "error": str(exc)},
            )

        except Exception:
            # Do not expose raw command/database details.
            self.reply(
                500,
                {"ok": False, "error": "broker failure"},
            )


class Server(UnixStreamServer):
    allow_reuse_address = True


def main():
    os.umask(0o077)
    Path(SOCKET_PATH).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.path.lexists(SOCKET_PATH):
        raise SystemExit("Socket already exists; inspect ownership before restart")

    server = Server(SOCKET_PATH, Handler)

    # User only.
    os.chmod(SOCKET_PATH, 0o600)

    print("Messages read broker listening on:")
    print(SOCKET_PATH)
    print("Mode: READ ONLY")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)


if __name__ == "__main__":
    main()
