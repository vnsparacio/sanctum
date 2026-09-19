"""Targeted parser regressions through production backend HTTP construction."""

import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
from backends import PrivateLeadBackend
from common import Refused, canonical


def propose(text, metadata=None):
    schema = {"type": "object"}
    intent = {
        "version": "sanctum-work-intent/v1",
        "dialect": "vllm-0.20.1-outlines",
        "schema": schema,
        "schemaDigest": hashlib.sha256(canonical(schema).encode()).hexdigest(),
        "semanticSchemaDigest": "a" * 64,
    }
    wire = ("data: " + metadata + "\n\n") if metadata else ""
    wire += (
        "data: "
        + json.dumps(
            {"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]}
        )
        + "\n\ndata: [DONE]\n\n"
    )
    backend = PrivateLeadBackend(json.loads((BASE / "SETTINGS.json").read_text()))
    with (
        patch.object(backend, "health_check"),
        patch("backends.urllib.request.build_opener") as opener,
    ):
        opener.return_value.open.return_value = io.BytesIO(wire.encode())
        return backend.propose(
            {"system": "synthetic", "request": {"state": {"workIntent": intent}}}
        )


class TargetedParser(unittest.TestCase):
    def test_R2_overflow_and_literal_nonfinite_reject_before_recognition(self):
        for number in ("1e400", "-1e400", "NaN", "Infinity", "-Infinity"):
            for text in (
                number,
                '{"kind":"TOOL_PROPOSAL","capability":"worktree_read","arguments":{"path":"index.js","max_chars":'
                + number
                + "}}",
                '{"kind":"ESCALATION","reason":"A","INJECTED_PRIVATE_KEY":[{"nested":['
                + number
                + "]}]}",
            ):
                with self.subTest(number=number, nested=text.startswith("{")):
                    with self.assertRaises(Refused) as caught:
                        propose(text)
                    self.assertEqual(
                        str(caught.exception), "private_lead_result_schema"
                    )
                    self.assertEqual(caught.exception.diagnostic["stage"], "JSON_PARSE")
                    self.assertEqual(
                        caught.exception.diagnostic["keyword"], "nonfinite"
                    )
                    self.assertNotIn(
                        "INJECTED_PRIVATE", json.dumps(caught.exception.diagnostic)
                    )

    def test_R2_finite_numbers_are_preserved_not_coerced(self):
        for number in ("1", "-2", "1.25", "1e308", "-1e308", "0", "-0.0", "1e-400"):
            value = {
                "kind": "TOOL_PROPOSAL",
                "capability": "worktree_read",
                "arguments": {"path": "index.js", "max_chars": json.loads(number)},
            }
            self.assertEqual(propose(json.dumps(value))["result"], value)

    def test_R2_duplicate_keys_remain_separate(self):
        with self.assertRaises(Refused) as caught:
            propose('{"kind":"ESCALATION","reason":"A","reason":"B"}')
        self.assertEqual(caught.exception.diagnostic["keyword"], "duplicateKey")

    def test_R2_nonfinite_event_metadata_is_not_a_retryable_result(self):
        for number in ("1e400", "-1e400", "NaN", "Infinity", "-Infinity"):
            with self.subTest(number=number):
                with self.assertRaises(Refused) as caught:
                    propose(
                        '{"kind":"ESCALATION","reason":"A"}',
                        '{"choices":[],"usage":{"nested":[' + number + "]}}",
                    )
                self.assertEqual(str(caught.exception), "answer_incomplete")
                self.assertEqual(caught.exception.diagnostic["stage"], "STREAM")
                self.assertEqual(caught.exception.diagnostic["keyword"], "nonfinite")

    def test_R2_finite_event_metadata_remains_valid(self):
        self.assertEqual(
            propose(
                '{"kind":"ESCALATION","reason":"A"}',
                '{"choices":[],"usage":{"prompt_tokens":8,"completion_tokens":3}}',
            )["telemetry"]["prompt_tokens"],
            8,
        )


if __name__ == "__main__":
    unittest.main()
