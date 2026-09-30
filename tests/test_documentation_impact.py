import unittest

from scripts.check_documentation_impact import (
    check_documentation_impact,
    documentation_section,
    is_behavior_or_configuration,
    is_documentation,
)


class DocumentationImpactTests(unittest.TestCase):
    def test_every_pull_request_requires_exact_section(self):
        self.assertTrue(check_documentation_impact(["NOTICE"], "## Summary\nText"))
        duplicate = (
            "## Documentation impact\nNone: This changes notices only.\n\n"
            "## Documentation impact\nNone: This changes notices only."
        )
        self.assertIsNone(documentation_section(duplicate))

    def test_documented_behavior_change_passes(self):
        body = "## Documentation impact\nUpdated: Added the new startup procedure."
        self.assertEqual(
            [],
            check_documentation_impact(
                ["gate/plugin/core.mjs", "docs/guides/quickstart.md"], body
            ),
        )

    def test_behavior_change_accepts_only_justified_none_without_docs(self):
        justified = (
            "## Documentation impact\n"
            "None: Refactors an internal parser without changing behavior."
        )
        self.assertEqual(
            [], check_documentation_impact(["scripts/internal_parser.py"], justified)
        )
        vague = "## Documentation impact\nNone: N/A"
        self.assertTrue(
            check_documentation_impact(["scripts/internal_parser.py"], vague)
        )
        unsupported = (
            "## Documentation impact\n"
            "Updated: Behavior changed but this PR contains no documentation."
        )
        self.assertTrue(
            check_documentation_impact(["scripts/internal_parser.py"], unsupported)
        )

    def test_updated_declaration_requires_documentation_file(self):
        body = "## Documentation impact\nUpdated: Explained the change for operators."
        self.assertTrue(check_documentation_impact(["NOTICE"], body))
        self.assertEqual([], check_documentation_impact(["README.md", "NOTICE"], body))

    def test_path_classification_covers_product_surfaces(self):
        for path in (
            "gate/plugin/core.mjs",
            "config/agents.json",
            ".github/workflows/ci.yml",
            "Makefile",
            "WORKFLOW.md",
        ):
            self.assertTrue(is_behavior_or_configuration(path), path)
        self.assertFalse(is_behavior_or_configuration("tests/test_release.py"))
        self.assertTrue(is_documentation("README.md"))
        self.assertTrue(is_documentation("docs/guides/quickstart.md"))
        self.assertFalse(is_documentation("CONTRIBUTING.md"))


if __name__ == "__main__":
    unittest.main()
