import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "splunk/sanctum_content"


def stanzas(path: Path) -> dict[str, dict[str, str]]:
    parsed: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = parsed.setdefault(line[1:-1], {})
            continue
        if current is None or "=" not in line:
            raise AssertionError(f"invalid conf line in {path}: {raw_line}")
        key, value = line.split("=", 1)
        current[key.strip()] = value.strip()
    return parsed


class SplunkContentAssets(unittest.TestCase):
    def test_jsonl_fixture_is_one_json_record_per_physical_line(self):
        fixture = ROOT / "tests/fixtures/splunk-content-events.jsonl"
        lines = fixture.read_text().splitlines()
        records = [json.loads(line) for line in lines]
        self.assertEqual(len(lines), 3)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["delivered_response"].count("\n"), 1)
        self.assertEqual(
            [record["schema_version"] for record in records],
            [
                "sanctum.ai-interaction/v1",
                "sanctum.ai-interaction/v1",
                "sanctum.quality-annotation/v1",
            ],
        )

    def test_props_keep_each_jsonl_line_as_one_event(self):
        props = stanzas(APP / "default/props.conf")
        self.assertEqual(
            set(props),
            {"sanctum:ai:interaction", "sanctum:quality:annotation"},
        )
        for values in props.values():
            self.assertEqual(values["SHOULD_LINEMERGE"], "false")
            self.assertEqual(values["LINE_BREAKER"], "([\\r\\n]+)")
            self.assertEqual(values["KV_MODE"], "json")
            self.assertEqual(values["INDEXED_EXTRACTIONS"], "none")

    def test_restricted_index_does_not_modify_operational_contract(self):
        indexes = stanzas(APP / "default/indexes.conf")
        self.assertEqual(set(indexes), {"sanctum_content"})
        self.assertNotIn("sanctum_ops", (APP / "default/indexes.conf").read_text())
        self.assertNotIn(
            "sanctum:runtime:event", (APP / "default/props.conf").read_text()
        )

    def test_saved_searches_cover_detail_quality_failures_and_correlation(self):
        searches = stanzas(APP / "default/savedsearches.conf")
        detail = searches["Sanctum Content - Recent Interaction Outcomes"]["search"]
        for field in (
            "user_query",
            "delivered_response",
            "outcome",
            "failure_stage",
            "failure_category",
            "failure_code",
            "model_provider",
            "latency_ms",
            "input_tokens",
            "output_tokens",
        ):
            self.assertIn(field, detail)
        self.assertIn("semantic_failure_category", searches["Sanctum Content - Quality Signals"]["search"])
        correlation = searches["Sanctum Content - Trace Correlation"]["search"]
        self.assertIn("index=sanctum_content", correlation)
        self.assertIn("index=sanctum_ops", correlation)
        self.assertIn("correlation.trace_id", correlation)
        self.assertIn("trace_id", correlation)
        for search in searches.values():
            self.assertEqual(search["enableSched"], "0")
            self.assertEqual(search["dispatchAs"], "user")

    def test_dashboard_is_valid_xml_and_uses_saved_searches(self):
        dashboard = APP / "default/data/ui/views/sanctum_content_overview.xml"
        root = ET.parse(dashboard).getroot()
        self.assertEqual(root.tag, "form")
        refs = {node.attrib["ref"] for node in root.findall(".//search[@ref]")}
        self.assertEqual(
            refs,
            {
                "Sanctum Content - Success Rate",
                "Sanctum Content - Failure Reasons",
                "Sanctum Content - Recent Interaction Outcomes",
            },
        )


if __name__ == "__main__":
    unittest.main()
