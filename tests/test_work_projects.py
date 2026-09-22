from __future__ import annotations

import copy
import unittest

from sanctum_agents.work_projects import (
    ProjectProfileError,
    parse_project_profiles,
)


def profile(
    project_id: str,
    repository: str,
    base_branch: str,
    operations: list[str],
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "repository": repository,
        "base_branch": base_branch,
        "validation_operations": operations,
        "private_config_refs": {
            "repository": f"{project_id}-repository",
            "validation": f"{project_id}-validation",
        },
    }


class WorkModeProjectProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = {
            "schema": "sanctum-work-mode-project-profiles/v1",
            "profiles": [
                profile(
                    "sanctum",
                    "vnsparacio/sanctum",
                    "v1.3-dev",
                    ["build", "test", "lint"],
                ),
                profile("widget", "synthetic/widget", "main", ["test"]),
            ],
        }

    def test_sanctum_and_non_sanctum_profiles_parse(self):
        profiles = parse_project_profiles(self.document)

        sanctum = profiles.select("sanctum")
        self.assertEqual("vnsparacio/sanctum", sanctum.repository)
        self.assertEqual("v1.3-dev", sanctum.base_branch)
        self.assertEqual(("build", "test", "lint"), sanctum.validation_operations)
        self.assertEqual("synthetic/widget", profiles.select("widget").repository)
        with self.assertRaises(TypeError):
            profiles.profiles["other"] = sanctum

    def test_unknown_or_input_shaped_project_ids_fail_closed(self):
        profiles = parse_project_profiles(self.document)

        for project_id in ("unknown", "/tmp/repository", "../sanctum", "SANCTUM"):
            with self.subTest(project_id=project_id):
                with self.assertRaises(ProjectProfileError):
                    profiles.select(project_id)

    def test_host_paths_fail_closed(self):
        for host_path in (
            "/private/project/sanctum",
            "../sanctum",
            "file:///private/sanctum",
        ):
            document = copy.deepcopy(self.document)
            document["profiles"][0]["repository"] = host_path
            with self.subTest(host_path=host_path):
                with self.assertRaises(ProjectProfileError):
                    parse_project_profiles(document)

    def test_unsafe_base_branches_fail_closed(self):
        for branch in (
            "-owner-selected-option",
            "refs/heads/main",
            "main..release",
            "feature//escape",
            "release@{1}",
            "main.lock",
        ):
            document = copy.deepcopy(self.document)
            document["profiles"][0]["base_branch"] = branch
            with self.subTest(branch=branch):
                with self.assertRaises(ProjectProfileError):
                    parse_project_profiles(document)

    def test_credential_bearing_fields_fail_closed_at_any_depth(self):
        additions = (
            (self.document, "token"),
            (self.document["profiles"][0], "apiKey"),
            (self.document["profiles"][0]["private_config_refs"], "password"),
        )
        for target, field in additions:
            document = copy.deepcopy(self.document)
            if target is self.document:
                selected = document
            elif target is self.document["profiles"][0]:
                selected = document["profiles"][0]
            else:
                selected = document["profiles"][0]["private_config_refs"]
            selected[field] = "synthetic-placeholder"
            with self.subTest(field=field):
                with self.assertRaisesRegex(ProjectProfileError, "credential-bearing"):
                    parse_project_profiles(document)

    def test_unreviewed_operations_and_duplicate_ids_fail_closed(self):
        document = copy.deepcopy(self.document)
        document["profiles"][0]["validation_operations"] = ["test", "shell"]
        with self.assertRaises(ProjectProfileError):
            parse_project_profiles(document)

        document = copy.deepcopy(self.document)
        document["profiles"].append(copy.deepcopy(document["profiles"][0]))
        with self.assertRaises(ProjectProfileError):
            parse_project_profiles(document)


if __name__ == "__main__":
    unittest.main()
