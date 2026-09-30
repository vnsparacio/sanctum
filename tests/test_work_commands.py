from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

from sanctum_agents.work_commands import (
    CONTAINER_ENVIRONMENT,
    IsolatedCommandRunner,
    OciRunnerProfile,
    WorkCommandError,
    command_request,
    parse_command_request,
)
from sanctum_agents.work_workspaces import TaskWorkspace


class IsolatedCommandRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.workspaces = self.root / "workspaces"
        self.workspaces.mkdir()
        self.workspace_root = self.workspaces / "TASK-1"
        self.workspace_root.mkdir()
        (self.workspace_root / "src").mkdir()
        self.runtime = self.root / "docker"
        self.runtime.write_text("synthetic OCI runtime\n")
        self.runtime.chmod(0o700)
        self.image = "sha256:" + "a" * 64
        self.invocations: list[tuple[list[str], dict[str, str]]] = []

        def invoke(arguments: list[str], environment: Mapping[str, str]):
            self.invocations.append((arguments, dict(environment)))
            if arguments[1:3] == ["image", "inspect"]:
                return subprocess.CompletedProcess(arguments, 0, self.image + "\n", "")
            return subprocess.CompletedProcess(
                arguments, 0, "representative pass\n", ""
            )

        self.runner = IsolatedCommandRunner(
            {
                "widget-validation": OciRunnerProfile(
                    runtime=self.runtime,
                    runtime_host="unix:///synthetic/docker.sock",
                    image=self.image,
                    runner_user="1000:1000",
                    operations={
                        "test": ("python", "-m", "unittest"),
                        "lint": ("ruff", "check", "."),
                    },
                )
            },
            self.workspaces,
            invoke=invoke,
        )
        self.workspace = TaskWorkspace(
            project_id="widget",
            task_id="TASK-1",
            root=self.workspace_root,
            repository="synthetic/widget",
            base_branch="main",
            base_commit="a" * 40,
            resumed=False,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_request_contract_is_complete_and_fixed(self):
        request = command_request("test", "src")
        parsed = parse_command_request(request)
        self.assertEqual("test", parsed.operation)
        self.assertEqual("src", parsed.cwd)

        mutations = {
            "missing_policy": lambda value: value.pop("credentials"),
            "extra_field": lambda value: value.update({"argv": ["sh"]}),
            "network": lambda value: value.update({"network": "host"}),
            "mount": lambda value: value["mounts"].append("home:rw"),
            "environment": lambda value: value["environment"].update(
                {"TOKEN": "synthetic"}
            ),
            "credentials": lambda value: value.update({"credentials": "inherit"}),
            "host_cwd": lambda value: value.update({"cwd": "/Users/owner"}),
            "traversal": lambda value: value.update({"cwd": "../private"}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                changed = copy.deepcopy(request)
                mutate(changed)
                with self.assertRaises(WorkCommandError):
                    parse_command_request(changed)

    def test_reviewed_repository_command_uses_only_fixed_oci_authority(self):
        os.environ["TEST_SECRET"] = "must-not-enter-runner"
        try:
            result = self.runner.run(
                "widget-validation", self.workspace, command_request("test", "src")
            )
        finally:
            os.environ.pop("TEST_SECRET", None)

        self.assertTrue(result["ok"])
        self.assertEqual("representative pass\n", result["stdout"])
        arguments, host_environment = self.invocations[-1]
        self.assertEqual(
            {
                "PATH": "/usr/bin:/bin",
                "LANG": "C",
                "LC_ALL": "C",
                "HOME": "/nonexistent",
                "DOCKER_HOST": "unix:///synthetic/docker.sock",
            },
            host_environment,
        )
        self.assertNotIn("TEST_SECRET", host_environment)
        self.assertEqual("run", arguments[1])
        self.assertIn("none", arguments)
        self.assertIn("no-new-privileges", arguments)
        self.assertIn("/tmp:rw,nosuid,nodev,noexec", arguments)
        self.assertIn("/workspace/src", arguments)
        mount = arguments[arguments.index("--mount") + 1]
        self.assertEqual(
            f"type=bind,source={self.workspace_root},destination=/workspace", mount
        )
        self.assertEqual(self.image, arguments[-4])
        self.assertEqual(["python", "-m", "unittest"], arguments[-3:])
        for name, value in CONTAINER_ENVIRONMENT.items():
            self.assertIn(f"{name}={value}", arguments)
        rendered = "\n".join(arguments)
        self.assertNotIn(str(Path.home()), rendered)
        self.assertNotIn("Keychains", rendered)
        self.assertNotIn("docker.sock:/", rendered)

    def test_unreviewed_operations_and_cwd_aliases_never_launch(self):
        with self.assertRaisesRegex(WorkCommandError, "not reviewed"):
            self.runner.run(
                "widget-validation", self.workspace, command_request("build")
            )
        self.assertEqual([], self.invocations)

        outside = TaskWorkspace(
            "widget",
            "private",
            self.root,
            "synthetic/widget",
            "main",
            "a" * 40,
            False,
        )
        with self.assertRaisesRegex(WorkCommandError, "approved task root"):
            self.runner.run("widget-validation", outside, command_request("test"))
        self.assertEqual([], self.invocations)

        (self.workspace_root / "alias").symlink_to(self.workspace_root / "src")
        with self.assertRaisesRegex(WorkCommandError, "symlinks"):
            self.runner.run(
                "widget-validation", self.workspace, command_request("test", "alias")
            )
        self.assertEqual([], self.invocations)

    def test_image_identity_and_profile_authority_fail_closed(self):
        def wrong_image(arguments: list[str], _environment: Mapping[str, str]):
            return subprocess.CompletedProcess(
                arguments, 0, "sha256:" + "b" * 64 + "\n", ""
            )

        runner = IsolatedCommandRunner(
            self.runner.profiles, self.workspaces, invoke=wrong_image
        )
        with self.assertRaisesRegex(WorkCommandError, "image identity"):
            runner.run("widget-validation", self.workspace, command_request("test"))
        with self.assertRaisesRegex(WorkCommandError, "profile is unavailable"):
            self.runner.run("other", self.workspace, command_request("test"))


class LiveOciContainmentTests(unittest.TestCase):
    def test_cached_runner_denies_host_authority_and_ambient_network(self):
        runtime_name = shutil.which("docker")
        if not runtime_name:
            self.skipTest("Docker CLI unavailable")
        runtime = Path(runtime_name).resolve()
        try:
            subprocess.run(
                [str(runtime), "version"], check=True, capture_output=True, timeout=10
            )
            image = subprocess.run(
                [
                    str(runtime),
                    "image",
                    "inspect",
                    "--format",
                    "{{.Id}}",
                    "sanctum-work-runner:project3g",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            context = json.loads(
                subprocess.run(
                    [str(runtime), "context", "inspect"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).stdout
            )
            runtime_host = context[0]["Endpoints"]["docker"]["Host"]
        except Exception:
            self.skipTest("cached reviewed OCI runner unavailable")
        if not runtime_host.startswith("unix://"):
            self.skipTest("Docker context is not a local socket")

        with tempfile.TemporaryDirectory() as temporary:
            workspaces = Path(temporary).resolve() / "workspaces"
            workspaces.mkdir()
            root = workspaces / "TASK-LIVE"
            root.mkdir()
            script = root / "containment.mjs"
            host_home = str(Path.home())
            script.write_text(
                "import fs from 'node:fs';import net from 'node:net';"
                f"if(fs.existsSync({json.dumps(host_home)}))process.exit(11);"
                "if(fs.existsSync('/run/docker.sock'))process.exit(12);"
                "if(fs.existsSync('/var/run/docker.sock'))process.exit(13);"
                "if(process.env.TEST_SECRET)process.exit(14);"
                "const socket=net.connect({host:'1.1.1.1',port:443});"
                "const denied=()=>{socket.destroy();process.exit(0)};"
                "socket.on('error',denied);socket.setTimeout(1000,denied);"
                "socket.on('connect',()=>process.exit(15));\n"
            )
            workspace = TaskWorkspace(
                "widget", "TASK-LIVE", root, "synthetic/widget", "main", "a" * 40, False
            )
            runner = IsolatedCommandRunner(
                {
                    "live": OciRunnerProfile(
                        runtime,
                        runtime_host,
                        image,
                        f"{os.getuid()}:{os.getgid()}",
                        {"test": ("node", "containment.mjs")},
                    )
                },
                workspaces,
            )
            os.environ["TEST_SECRET"] = "must-not-leak"
            try:
                result = runner.run("live", workspace, command_request("test"))
            finally:
                os.environ.pop("TEST_SECRET", None)
            self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
