import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from schema import validate
from source_policy import decide, minimize_query


def packet(prompt="Rewrite this supplied paragraph."):
    return {
        "scope": "a" * 32,
        "revision": 2,
        "prompt": prompt,
        "attachment_summary": {"count": 0},
    }


def audit(kind="NONE", reasons=None):
    return {
        "urgency": "ABSENT",
        "stakes": "NORMAL",
        "domains": ["other_unknown"],
        "request_role": "explanation",
        "uncertainty": [],
        "quality": {
            "recommended_tier": "LOCAL_4B",
            "reason_codes": ["ROUTINE_LANGUAGE"],
        },
        "source_need": {
            "classification": kind,
            "reason_codes": reasons or ["DETERMINISTIC_OR_SELF_CONTAINED"],
        },
        "context_need": {
            "classification": {"attachments": "NONE", "prior_context": "NONE"},
            "answer": {"attachments": "NONE", "prior_context": "NONE"},
        },
        "needs_local_tools": False,
    }


class SourcePolicyTests(unittest.TestCase):
    def test_none_for_self_contained(self):
        self.assertEqual(decide(packet(), validate(audit())).need, "NONE")

    def test_current_upgrades_advice(self):
        d = decide(packet("What is the current API pricing?"), validate(audit()))
        self.assertEqual((d.need, d.query_mode), ("WEB_REQUIRED", "PUBLIC_GENERALIZED"))

    def test_required_needs_external_reason(self):
        with self.assertRaises(Exception):
            validate(audit("WEB_REQUIRED", ["TRANSFORMATION_ONLY"]))
        with self.assertRaises(Exception):
            validate(audit("WEB_HELPFUL", ["TRANSFORMATION_ONLY"]))

    def test_private_query_is_generalized_or_paused(self):
        d = minimize_query(
            "Bob said yesterday his left calf is swollen; what causes persistent unilateral calf swelling?"
        )
        self.assertEqual(d.sensitivity, "PUBLIC")
        self.assertNotIn("Bob", d.query)

    def test_private_only_query_needs_approval(self):
        d = minimize_query("My wife said secret 123456789 is broken")
        self.assertEqual(d.mode, "EXACT_APPROVAL_REQUIRED")

    def test_personal_source_terms_and_codenames_never_enter_public_query(self):
        for prompt in [
            "My Gmail says Project Kestrel closes Friday; what is the latest law?",
            "Tool output shows AcmeMerger deadline 2026-10-01; check current rules",
            "My calendar appointment with Dr Rivera needs current guidance",
        ]:
            d = minimize_query(prompt)
            self.assertNotIn("kestrel", d.query.lower())
            self.assertNotIn("acmemerger", d.query.lower())
            self.assertNotIn("rivera", d.query.lower())
            self.assertIn(d.mode, ("PUBLIC_GENERALIZED", "EXACT_APPROVAL_REQUIRED"))

    def test_schema_rejects_extra_source_field(self):
        a = audit()
        a["source_need"]["authority"] = "ALLOW"
        with self.assertRaises(Exception):
            validate(a)
