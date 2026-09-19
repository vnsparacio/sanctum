"""Render the supported overlay onto the base package, outside the checkout."""

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PackageClosure(unittest.TestCase):
    def test_reviewed_overlay_imports_and_builders_without_source_on_import_path(self):
        tree = ast.parse((ROOT / "scripts/upgrade_work_mode.py").read_text())
        files = next(
            ast.literal_eval(n.value)
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "FILES" for t in n.targets)
        )
        required = {
            "worker.py",
            "src/task_evidence.py",
            "runtime/protected-test-driver.cjs",
            "runtime/protected-test-preload.cjs",
            "src/experiment.py",
            "src/experiment_lifecycle.py",
            "experiment_control.py",
            "diagnostic-experiment.mjs",
            "runtime-readiness.mjs",
            "verify_exact_runtime.py",
            "verify_serving_runtime.py",
            "watch.py",
        }
        self.assertTrue(required <= set(files))
        self.assertEqual(len(files), len(set(files)))
        expected = json.loads(
            subprocess.check_output(["node", str(ROOT / "gate/runtime-readiness.mjs")])
        )
        with tempfile.TemporaryDirectory(prefix="sanctum-prelive-package-") as td:
            prefix = Path(td).resolve()
            package = prefix / "gate"
            package.mkdir()
            base_files = subprocess.check_output(
                ["git", "ls-tree", "-r", "--name-only", "HEAD", "gate"],
                cwd=ROOT,
                text=True,
            ).splitlines()
            for path in base_files:
                name = Path(path).relative_to("gate")
                if "tests" in name.parts:
                    continue
                target = package / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(
                    subprocess.check_output(["git", "show", "HEAD:" + path], cwd=ROOT)
                )
            for name in files:
                target = package / name
                target.parent.mkdir(parents=True, exist_ok=True)
                text = (ROOT / "gate" / name).read_text()
                tokens = {
                    "@STATE@": str(prefix / "state"),
                    "@CONFIG@": str(prefix / "config"),
                    "@GATE@": str(package),
                    "@PYTHON@": sys.executable,
                    "@NODE@": shutil.which("node"),
                    "@OPENCLAW@": str(ROOT / "node_modules/openclaw"),
                }
                for old, new in tokens.items():
                    text = text.replace(old, new)
                target.write_text(text)
            # All local edges must close in the rendered package. No checkout
            # module is used; only the approved interpreter/dependency runtime is external.
            js_edges = 0
            python_edges = 0
            for path in package.rglob("*.mjs"):
                for rel in re.findall(
                    r"(?:from\s*|import\s*\()['\"]([.][^'\"]+)['\"]", path.read_text()
                ):
                    target = (path.parent / rel).resolve()
                    self.assertTrue(target.is_relative_to(package))
                    self.assertTrue(target.exists(), str(target))
                    js_edges += 1
            local = {p.stem for p in (package / "src").glob("*.py")} | {
                p.stem for p in package.glob("*.py")
            }
            for path in package.rglob("*.py"):
                for node in ast.walk(ast.parse(path.read_text())):
                    names = (
                        [node.module]
                        if isinstance(node, ast.ImportFrom)
                        else (
                            [x.name for x in node.names]
                            if isinstance(node, ast.Import)
                            else []
                        )
                    )
                    for name in names:
                        if name and name.split(".")[0] in local:
                            python_edges += 1
            code = """import sys,pathlib
base=pathlib.Path(sys.argv[1]);sys.path[:0]=[str(base/'src'),str(base)]
import experiment,experiment_lifecycle,worker,experiment_control,verify_exact_runtime,verify_serving_runtime,task_evidence
for m in (experiment,experiment_lifecycle,worker,experiment_control,verify_exact_runtime,verify_serving_runtime,task_evidence):assert pathlib.Path(m.__file__).is_relative_to(base)
assert task_evidence.validate_contract(task_evidence.unrestricted_contract())['acceptance'] is None
for name in ('protected-test-driver.cjs','protected-test-preload.cjs'):assert (base/'runtime'/name).is_file()
print('isolated imports pass')
"""
            subprocess.run(
                [sys.executable, "-B", "-I", "-c", code, str(package)],
                cwd=td,
                check=True,
                capture_output=True,
            )
            actual = json.loads(
                subprocess.check_output(
                    ["node", str(package / "runtime-readiness.mjs")], cwd=td
                )
            )
            self.assertEqual(actual, expected)
            # Write only synthetic production requests for the actual isolated CLI.
            (prefix / "input.json").write_text(json.dumps(actual))
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-I",
                    str(package / "verify_exact_runtime.py"),
                    "--artifact",
                    str(prefix / "input.json"),
                ],
                cwd=td,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["status"], "NOT_RUN")
            self.assertGreater(js_edges, 40)
            self.assertGreater(python_edges, 45)
            print(
                f"Package closure: {len(files)} overlay files, {js_edges} JS edges, {python_edges} Python edges; isolated builders identical."
            )


if __name__ == "__main__":
    unittest.main()
