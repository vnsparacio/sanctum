"""Synthetic contract tests for bounded, chronological calendar reads."""

import importlib.util
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BROKER = Path(__file__).resolve().parents[1] / "host/macos/calendar-read-broker.py"
spec = importlib.util.spec_from_file_location("calendar_read_broker", BROKER)
broker = importlib.util.module_from_spec(spec)
previous_umask = os.umask(0o077)
try:
    spec.loader.exec_module(broker)
finally:
    os.umask(previous_umask)


class CalendarReadBrokerTests(unittest.TestCase):
    def test_date_only_event_is_explicitly_all_day(self):
        self.assertTrue(
            broker.compact_event({"start": {"date": "2026-09-25"}})["allDay"]
        )
        self.assertNotIn(
            "allDay", broker.compact_event({"startLocal": "2026-09-25T07:00:00-07:00"})
        )

    def test_explicit_instant_excludes_past_and_sorts_future(self):
        events = [
            {"startLocal": "2026-09-25T16:00:00-07:00"},
            {"startLocal": "2026-09-23T19:00:00-07:00"},
            {"startLocal": "2026-09-25T07:30:00-07:00"},
            {"start": {"date": "2026-09-25"}},
        ]
        result = broker.future_events(events, "2026-09-24T12:00:00Z", 2)
        self.assertEqual(result, [events[3], events[2]])

    def test_relative_window_does_not_apply_instant_filter(self):
        events = [{"start": {"date": "2026-09-24"}}]
        self.assertEqual(broker.future_events(events, "today", 1), events)

    def test_provider_cap_survives_instant_filter(self):
        past = [{"startLocal": "2026-09-23T09:00:00-07:00"}] * 18
        future = [{"startLocal": "2026-09-25T09:00:00-07:00"}] * 2
        rows, reached = broker.bounded_agenda(
            past + future, "2026-09-25T00:00:00-07:00", 20, 20
        )
        self.assertEqual(len(rows), 2)
        self.assertTrue(reached)

    def test_wrapper_raw_cap_is_separate_from_compact_response_cap(self):
        payload = json.dumps([{"description": "x" * (100 * 1024)}])
        with patch.object(
            broker.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout=payload),
        ):
            self.assertEqual(
                broker.run_wrapper(["events"])[0]["description"], "x" * (100 * 1024)
            )
        oversized = json.dumps([{"description": "x" * (257 * 1024)}])
        with patch.object(
            broker.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout=oversized),
        ):
            with self.assertRaisesRegex(RuntimeError, "size cap"):
                broker.run_wrapper(["events"])


if __name__ == "__main__":
    unittest.main()
