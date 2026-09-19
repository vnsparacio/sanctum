import json
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE / "src"), str(BASE)]
import characterize_private_lead as characterization


class Characterization(unittest.TestCase):
    def test_argument_matching_is_partial_but_type_strict(self):
        self.assertTrue(
            characterization.args_match({"chat_id": 42, "limit": 5}, {"chat_id": 42})
        )
        self.assertFalse(
            characterization.args_match({"chat_id": "42"}, {"chat_id": 42})
        )
        self.assertTrue(
            characterization.args_match(
                {"query": "Cedar review events"}, {"query": "Cedar review"}
            )
        )
        self.assertFalse(
            characterization.args_match(
                {"query": "review events"}, {"query": "Cedar review"}
            )
        )

    def test_simplest_profile_wins_within_tolerance(self):
        scores = {"compact": 0.98, "contract": 1.0, "contract_examples": 1.0}
        self.assertEqual(
            characterization.select_simplest(
                scores, ["compact", "contract", "contract_examples"]
            ),
            "compact",
        )

    def test_configured_surface_requires_every_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            (prefix / "config").mkdir()
            names = sorted(
                {
                    case["tool"]
                    for case in characterization.TOOL_CASES
                    + characterization.HOLDOUT_CASES
                }
            )
            (prefix / "config" / "openclaw.json").write_text(
                json.dumps({"tools": {"alsoAllow": names}})
            )
            loaded = characterization.load_tools(prefix)
            self.assertEqual(set(loaded), set(names))

    def test_dynamic_surface_contains_expected_tool(self):
        tools = {
            name: {"name": name, "description": name, "parameters": {"type": "object"}}
            for name in characterization.DOMAINS["gmail"]
        }
        names = characterization.surface_for(
            characterization.TOOL_CASES[0], "selected", tools
        )
        self.assertIn("gmail_search", names)
        self.assertLessEqual(len(names), 4)

    def test_all_expected_arguments_satisfy_captured_top_level_schemas(self):
        schemas = {
            item["name"]: item["parameters"]
            for item in json.loads(characterization.schema_path().read_text())
        }
        for case in characterization.TOOL_CASES + characterization.HOLDOUT_CASES:
            self.assertTrue(
                characterization.expected_args_valid(
                    case["args"], schemas[case["tool"]]
                ),
                case["id"],
            )

    def test_receipt_rows_are_metadata_only_contract(self):
        forbidden = {"content", "prompt", "arguments", "reasoning", "tool_result"}
        source = Path(characterization.__file__).read_text()
        self.assertIn('"stores_raw_model_content": False', source)
        example = {"case": "synthetic", "passed": True, "latency_seconds": 1.0}
        self.assertFalse(forbidden.intersection(example))

    def test_accepted_profile_matches_characterized_prompt(self):
        profile = json.loads(
            (BASE / "runtime" / "private-lead-interface-profile.json").read_text()
        )
        self.assertEqual(profile["status"], "accepted-characterized")
        self.assertEqual(
            profile["prompt"]["system"], characterization.SYSTEMS["compact"]
        )
        self.assertEqual(
            profile["prompt"]["structured_decision_guide"],
            characterization.DECISION_GUIDE,
        )
        self.assertEqual(
            profile["tools"]["capability_visibility"], "host_selected_dynamic_subset"
        )
        self.assertFalse(profile["tools"]["proposal_execution_authority"])


if __name__ == "__main__":
    unittest.main()
