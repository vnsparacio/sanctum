import unittest
from pathlib import Path

from scripts.codex_token_baseline import (
    TokenMeterError,
    collect_baseline,
    markdown_report,
    validate_base_url,
)


class TokenBaselineTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path("/private/symphony-workspaces").resolve(strict=False)
        self.responses = {
            "/health": {
                "ok": True,
                "state_ready": True,
                "source_clients": {"codex": 4},
                "runtime_adapter_failures": [],
            },
            "/logs": {
                "generated_at": 123,
                "total_sessions": 4,
                "sessions": [
                    {
                        "id": "session-safe-1",
                        "client": "codex",
                        "project": str(self.workspace / "TTE-49"),
                        "title": "private title must not escape",
                        "start": "2026-09-20 10:00",
                        "last": "2026-09-20 10:10",
                        "wall_duration_s": 600,
                        "turns": 3,
                        "tokens": 110,
                        "input_tokens": 100,
                        "output_tokens": 10,
                        "usage_basis": "reported",
                        "models": ["gpt-test"],
                        "context": {"latest": 80, "latest_pct": 0.4},
                        "model_stats": [
                            {
                                "cache_read_tokens": 60,
                                "reasoning_tokens": 4,
                                "executions": 3,
                            }
                        ],
                    },
                    {
                        "id": "session-safe-2",
                        "client": "codex",
                        "project": str(self.workspace / "TTE-49"),
                        "start": "2026-09-20 10:20",
                        "last": "2026-09-20 10:25",
                        "wall_duration_s": 300,
                        "turns": 2,
                        "tokens": 55,
                        "input_tokens": 50,
                        "output_tokens": 5,
                        "usage_basis": "reported",
                        "models": ["gpt-test"],
                        "context": {"latest": 100, "latest_pct": 0.5},
                        "model_stats": [
                            {
                                "cache_read_tokens": 30,
                                "reasoning_tokens": 2,
                                "executions": 2,
                            }
                        ],
                    },
                    {
                        "id": "outside",
                        "client": "codex",
                        "project": "/private/unrelated/TTE-50",
                    },
                    {
                        "id": "other-runtime",
                        "client": "claude",
                        "project": str(self.workspace / "TTE-51"),
                    },
                ],
            },
            "/session?id=session-safe-1": {
                "tools": {
                    "total_calls": 2,
                    "total_errors": 1,
                    "total_output_tokens": 20,
                },
                "subagent_turns": 0,
                "trace_truncated": False,
                "user_message": "private prompt must not escape",
            },
            "/session?id=session-safe-2": {
                "tools": {
                    "total_calls": 1,
                    "total_errors": 0,
                    "total_output_tokens": 10,
                },
                "subagent_turns": 0,
                "trace_truncated": True,
            },
        }

    def fetch(self, _base, path):
        return self.responses[path]

    def test_collects_issue_aggregates_without_content_or_paths(self):
        baseline = collect_baseline(
            "http://127.0.0.1:8722",
            self.workspace,
            {"TTE-49"},
            fetcher=self.fetch,
        )
        self.assertEqual(1, baseline["matched_issues"])
        row = baseline["issues"][0]
        self.assertEqual(2, row["sessions"])
        self.assertEqual(1, row["session_restarts"])
        self.assertEqual(165, row["total_tokens"])
        self.assertEqual(90, row["cached_input_tokens"])
        self.assertEqual(60.0, row["cache_percent"])
        self.assertEqual(3, row["tool_calls"])
        self.assertEqual(1, row["tool_errors"])
        self.assertEqual(100.0, row["peak_context_tokens"])
        self.assertEqual(50.0, row["peak_context_percent"])
        self.assertEqual(1, row["truncated_sessions"])
        rendered = str(baseline)
        self.assertNotIn("session-safe", rendered)
        self.assertNotIn("private prompt", rendered)
        self.assertNotIn(str(self.workspace), rendered)

    def test_unavailable_metrics_remain_unavailable(self):
        session = self.responses["/logs"]["sessions"][0]
        session["model_stats"] = []
        self.responses["/logs"]["sessions"] = [session]
        self.responses["/session?id=session-safe-1"]["tools"] = {}
        row = collect_baseline(
            "http://localhost:8722", self.workspace, fetcher=self.fetch
        )["issues"][0]
        self.assertIsNone(row["cached_input_tokens"])
        self.assertIsNone(row["reasoning_tokens"])
        self.assertIsNone(row["tool_calls"])

    def test_rejects_non_loopback_or_unready_sources(self):
        self.assertEqual("http://[::1]:8722", validate_base_url("http://[::1]:8722"))
        for value in (
            "https://127.0.0.1:8722",
            "http://example.com:8722",
            "http://127.0.0.1",
            "http://user@127.0.0.1:8722",
        ):
            with self.subTest(value=value), self.assertRaises(TokenMeterError):
                validate_base_url(value)
        self.responses["/health"]["state_ready"] = False
        with self.assertRaisesRegex(TokenMeterError, "not ready"):
            collect_baseline(
                "http://127.0.0.1:8722", self.workspace, fetcher=self.fetch
            )

    def test_markdown_marks_unavailable_values(self):
        rendered = markdown_report(
            {
                "issues": [
                    {
                        "issue": "TTE-49",
                        "sessions": 1,
                        "total_tokens": None,
                        "input_tokens": None,
                        "cached_input_tokens": None,
                        "output_tokens": None,
                        "turns": 1,
                        "tool_calls": None,
                        "peak_context_tokens": None,
                    }
                ]
            }
        )
        self.assertIn("unavailable", rendered)


if __name__ == "__main__":
    unittest.main()
