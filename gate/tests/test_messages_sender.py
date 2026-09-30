"""Synthetic-only contracts for exact inbound Messages sender lookup."""

import importlib.util
import json
import socket
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "messages_read_broker", ROOT / "host/macos/messages-read-broker.py"
)
BROKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BROKER)


class SenderHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / "chat.db"
        with sqlite3.connect(self.database) as connection:
            connection.executescript("""
                CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT NOT NULL);
                CREATE TABLE message (
                    ROWID INTEGER PRIMARY KEY, handle_id INTEGER, text TEXT,
                    attributedBody BLOB,
                    date INTEGER, is_from_me INTEGER, is_system_message INTEGER,
                    is_service_message INTEGER, is_empty INTEGER,
                    associated_message_type INTEGER, date_retracted INTEGER,
                    cache_has_attachments INTEGER
                );
                CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
                """)
            connection.executemany(
                "INSERT INTO handle (ROWID,id) VALUES (?,?)",
                [(1, "+14155550111"), (2, "+14155550112"), (3, "+14155550111")],
            )
            for index in range(14):
                connection.execute(
                    "INSERT INTO message (handle_id,text,date,is_from_me) VALUES (?,?,?,0)",
                    (
                        1 if index % 2 else 3,
                        f"target {index}",
                        (800_000_000 + index) * 10**9,
                    ),
                )
            connection.executemany(
                """
                INSERT INTO message
                    (handle_id,text,date,is_from_me,is_system_message,associated_message_type)
                VALUES (?,?,?,?,?,?)
                """,
                [
                    (2, "mentions +14155550111", 900_000_000 * 10**9, 0, 0, 0),
                    (1, "outgoing", 901_000_000 * 10**9, 1, 0, 0),
                    (1, "reaction", 902_000_000 * 10**9, 0, 0, 2000),
                    (1, "system", 903_000_000 * 10**9, 0, 1, 0),
                ],
            )

    def test_last_ten_are_only_inbound_exact_sender_across_handle_rows(self):
        records = BROKER.sender_history("+14155550111", 10, self.database)
        self.assertEqual(
            [row["text"] for row in records], [f"target {n}" for n in range(13, 3, -1)]
        )
        self.assertTrue(all(row["sender"] == "+14155550111" for row in records))
        self.assertTrue(all(row["created_at"].endswith("Z") for row in records))
        self.assertTrue(all(not row["content_unavailable"] for row in records))

    def test_unknown_and_invalid_senders_do_not_broaden_lookup(self):
        self.assertEqual(BROKER.sender_history("+14155559999", 10, self.database), [])
        for sender in ("14155550111", "+1415555", "+14155550111 OR 1=1"):
            with self.subTest(sender=sender), self.assertRaises(ValueError):
                BROKER.sender_history(sender, 10, self.database)
        with self.assertRaises(ValueError):
            BROKER.sender_history("+14155550111", 13, self.database)

    def test_unavailable_and_long_text_are_explicit(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """INSERT INTO message
                   (handle_id,text,date,is_from_me,is_empty,cache_has_attachments)
                   VALUES (1,NULL,?,0,1,1)""",
                (910_000_000 * 10**9,),
            )
            connection.execute(
                "INSERT INTO message (handle_id,text,date,is_from_me) VALUES (1,?,?,0)",
                ("x" * 3000, 911_000_000 * 10**9),
            )
        records = BROKER.sender_history("+14155550111", 2, self.database)
        self.assertTrue(records[0]["text_truncated"])
        self.assertIn("[message text truncated]", records[0]["text"])
        self.assertTrue(records[1]["content_unavailable"])
        self.assertIsNone(records[1]["text"])

    def test_recovers_attributed_body_only_for_exact_sender_and_message(self):
        with sqlite3.connect(self.database) as connection:
            cursor = connection.execute(
                """INSERT INTO message
                   (handle_id,text,attributedBody,date,is_from_me)
                   VALUES (1,NULL,?, ?,0)""",
                (b"synthetic attributed body", 912_000_000 * 10**9),
            )
            message_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO chat_message_join (chat_id,message_id) VALUES (?,?)",
                (31, message_id),
            )
        decoded = {
            "id": message_id,
            "sender": "+14155550111",
            "is_from_me": False,
            "text": "decoded synthetic text",
        }
        with patch.object(BROKER, "run_broker", return_value=[decoded]) as run:
            records = BROKER.sender_history("+14155550111", 1, self.database)
        self.assertEqual(records[0]["text"], "decoded synthetic text")
        self.assertFalse(records[0]["content_unavailable"])
        args = run.call_args.args[0]
        self.assertEqual(args[0:2], ["history-window", "31"])
        self.assertEqual(run.call_args.kwargs["timeout"], 5)

        for invalid in (
            {**decoded, "id": message_id + 1},
            {**decoded, "sender": "+14155550112"},
            {**decoded, "is_from_me": True},
        ):
            with (
                self.subTest(invalid=invalid),
                patch.object(BROKER, "run_broker", return_value=[invalid]),
            ):
                records = BROKER.sender_history("+14155550111", 1, self.database)
            self.assertIsNone(records[0]["text"])
            self.assertTrue(records[0]["content_unavailable"])

    def test_apple_epoch_units(self):
        for factor in (1, 1000, 1_000_000, 1_000_000_000):
            self.assertEqual(
                BROKER.apple_message_time(800_000_000 * factor),
                "2026-05-09T06:13:20Z",
            )

    def test_read_only_http_route_uses_bounded_sender_lookup(self):
        socket_path = Path(self.temporary.name) / "messages.sock"
        original = BROKER.sender_history
        with patch.object(
            BROKER,
            "sender_history",
            side_effect=lambda sender, limit: original(sender, limit, self.database),
        ):
            with BROKER.Server(str(socket_path), BROKER.Handler) as server:
                thread = threading.Thread(target=server.handle_request, daemon=True)
                thread.start()
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.connect(str(socket_path))
                    client.sendall(
                        b"GET /sender-history?sender=%2B14155550111&limit=10 HTTP/1.1\r\n"
                        b"Host: localhost\r\nConnection: close\r\n\r\n"
                    )
                    response = b""
                    while chunk := client.recv(8192):
                        response += chunk
                thread.join(timeout=2)
        headers, body = response.split(b"\r\n\r\n", 1)
        self.assertIn(b"200", headers.splitlines()[0])
        payload = json.loads(body)
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["records"]), 10)


if __name__ == "__main__":
    unittest.main()
