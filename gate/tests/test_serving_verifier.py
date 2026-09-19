"""No-provider counterexamples for the failed operator verifier."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE), str(BASE / "src")]
import verify_exact_runtime as exact
import verify_serving_runtime as serving


class ServingContracts(unittest.TestCase):
    def setUp(self):
        self.contract = serving.launch_contract(
            (BASE / "runtime/bootstrap-private-lead-vllm.sh").read_text()
        )
        self.env = {
            "HF_HOME": self.contract["values"]["CACHE"],
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }

    def test_real_bootstrap_yields_complete_launch_command(self):
        c = self.contract
        self.assertEqual(
            c["command"][:3], [c["values"]["VLLM"], "serve", c["values"]["MODEL"]]
        )
        self.assertEqual(
            c["command"][c["command"].index("--revision") + 1], c["values"]["REVISION"]
        )
        self.assertNotIn(">", c["command"])
        self.assertNotIn("$", " ".join(c["command"]))
        self.assertIn("--no-enable-log-requests", c["command"])

    def test_contract_rejects_shell_substitution(self):
        text = (
            (BASE / "runtime/bootstrap-private-lead-vllm.sh")
            .read_text()
            .replace("ALIAS=sanctum-private-lead-qwen35-122b", "ALIAS=$(touch /tmp/no)")
        )
        with self.assertRaises(serving.VerificationFailure):
            serving.launch_contract(text)

    def test_exact_command_accepts_shebang_interpreter(self):
        cmd = self.contract["command"]
        python = str(Path(cmd[0]).with_name("python3.12"))
        self.assertEqual(serving.verify_command([python] + cmd, self.contract), cmd[2:])
        self.assertEqual(serving.verify_command(cmd, self.contract), cmd[2:])

    def test_wrong_interpreter_model_or_flags_fail(self):
        cmd = self.contract["command"]
        variants = [
            ["/tmp/python"] + cmd,
            cmd + ["--structured-outputs-config", '{"backend":"outlines"}'],
            cmd[:2] + ["another/model"] + cmd[3:],
        ]
        for variant in variants:
            with (
                self.subTest(variant=variant[:2]),
                self.assertRaises(serving.VerificationFailure),
            ):
                serving.verify_command(variant, self.contract)

    def test_cold_verifier_gets_server_cache_before_import(self):
        env = {
            "HF_HOME": "/wrong",
            "HF_HUB_CACHE": "/wrong/hub",
            "TRANSFORMERS_CACHE": "/wrong/transformers",
            "UNRELATED": "keep",
        }
        snapshot = serving.bind_cache(self.contract, self.env, env, {})
        self.assertEqual(env["HF_HOME"], self.env["HF_HOME"])
        self.assertEqual(env["HF_HUB_CACHE"], self.env["HF_HOME"] + "/hub")
        self.assertEqual(env["HUGGINGFACE_HUB_CACHE"], env["HF_HUB_CACHE"])
        self.assertNotIn("TRANSFORMERS_CACHE", env)
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")
        self.assertEqual(env["UNRELATED"], "keep")
        self.assertEqual(snapshot.name, self.contract["values"]["REVISION"])

    def test_late_environment_binding_fails(self):
        for module in ("huggingface_hub.constants", "transformers", "vllm"):
            with (
                self.subTest(module=module),
                self.assertRaisesRegex(
                    serving.VerificationFailure, "CACHE_IMPORT_ORDER"
                ),
            ):
                serving.bind_cache(self.contract, self.env, {}, {module: object()})

    def test_wrong_observed_cache_and_network_settings_fail(self):
        for key, value in [
            ("HF_HOME", "/other"),
            ("HF_HUB_CACHE", "/other"),
            ("HUGGINGFACE_HUB_CACHE", "/other"),
            ("TRANSFORMERS_CACHE", "/other"),
            ("HF_ENDPOINT", "https://example.test"),
            ("HF_HUB_OFFLINE", "0"),
            ("TRANSFORMERS_OFFLINE", "0"),
        ]:
            with self.subTest(key=key), self.assertRaises(serving.VerificationFailure):
                serving.bind_cache(self.contract, {**self.env, key: value}, {}, {})

    def test_offline_resolved_snapshot_accepted_not_model_id_comparison(self):
        with tempfile.TemporaryDirectory() as td:
            snapshot = Path(td) / self.contract["values"]["REVISION"]
            snapshot.mkdir()
            serving.verify_model_identity(
                self.contract["values"]["MODEL"],
                snapshot.name,
                str(snapshot),
                self.contract,
                snapshot,
            )

    def test_wrong_snapshot_revision_request_or_missing_cache_fails(self):
        with tempfile.TemporaryDirectory() as td:
            snapshot = Path(td) / self.contract["values"]["REVISION"]
            snapshot.mkdir()
            model = self.contract["values"]["MODEL"]
            for requested, rev, resolved in [
                ("other/model", snapshot.name, str(snapshot)),
                (model, "other", str(snapshot)),
                (model, snapshot.name, str(snapshot.parent)),
                (model, snapshot.name, model),
            ]:
                with (
                    self.subTest(requested=requested),
                    self.assertRaises(serving.VerificationFailure),
                ):
                    serving.verify_model_identity(
                        requested, rev, resolved, self.contract, snapshot
                    )
            snapshot.rmdir()
            with self.assertRaises(serving.VerificationFailure):
                serving.verify_model_identity(
                    model, snapshot.name, str(snapshot), self.contract, snapshot
                )

    def test_snapshot_symlink_refused(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "other"
            target.mkdir()
            snapshot = Path(td) / self.contract["values"]["REVISION"]
            snapshot.symlink_to(target)
            with self.assertRaises(serving.VerificationFailure):
                serving.verify_model_identity(
                    self.contract["values"]["MODEL"],
                    snapshot.name,
                    str(snapshot),
                    self.contract,
                    snapshot,
                )

    def test_failure_keeps_stage_and_frames_without_exception_content(self):
        try:
            raise RuntimeError("SYNTHETIC_SECRET_AND_PROMPT")
        except RuntimeError as error:
            record = serving.failure_record(error, "MODEL_RESOLUTION")
        raw = json.dumps(record)
        self.assertNotIn("SYNTHETIC_SECRET_AND_PROMPT", raw)
        self.assertNotIn(str(BASE), raw)
        self.assertEqual(record["stage"], "MODEL_RESOLUTION")
        self.assertTrue(record["frames"])
        self.assertEqual(record["frames"][-1]["module"], "test_serving_verifier.py")

    def test_early_failure_is_structured_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            result = serving.run(Path(td))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["stage"], "BOOTSTRAP_IDENTITY")
        self.assertEqual(result["modelInference"], "NOT_RUN")

    def test_import_has_no_runtime_or_environment_side_effects(self):
        code = """import os,sys
sys.path.insert(0,sys.argv[1]);before=dict(os.environ)
import verify_serving_runtime
assert before==dict(os.environ)
assert not any(x in sys.modules for x in ('vllm','transformers','huggingface_hub.constants'))
"""
        subprocess.run(
            [sys.executable, "-B", "-I", "-c", code, str(BASE)],
            check=True,
            capture_output=True,
        )

    def test_process_facts_whitelists_environment_and_keeps_start_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pids").mkdir()
            (root / "pids/vllm.pid").write_text("123\n")
            proc = root / "proc/123"
            proc.mkdir(parents=True)
            fields = ["S"] + ["0"] * 18 + ["98765"]
            (proc / "stat").write_text("123 (name with spaces) " + " ".join(fields))
            (proc / "cmdline").write_bytes(b"python\0vllm\0serve\0")
            (proc / "environ").write_bytes(
                b"HF_HOME=/cache\0HF_HUB_OFFLINE=1\0TOKEN=SYNTHETIC_SECRET\0"
            )
            pid, start, command, environment = serving.process_facts(
                root, root / "proc"
            )
            self.assertEqual((pid, start), ("123", "98765"))
            self.assertEqual(command, ["python", "vllm", "serve"])
            self.assertEqual(environment, {"HF_HOME": "/cache", "HF_HUB_OFFLINE": "1"})

    def test_cli_failure_is_single_structured_record(self):
        result = subprocess.run(
            [sys.executable, "-B", str(BASE / "verify_serving_runtime.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse(result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["stage"], "SERVER_IDENTITY")
        self.assertEqual(value["status"], "FAIL")


class TokenShapes(unittest.TestCase):
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            if not kwargs["tokenize"]:
                return "rendered"
            # Mirrors the newer tokenizer default that caused the original bug.
            return (
                [1, 2, 3]
                if kwargs.get("return_dict") is False
                else {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1]}
            )

        def encode(self, text, **kwargs):
            return [1, 2, 3]

    def test_explicit_flat_ids_prevent_batch_encoding_key_count(self):
        self.assertEqual(exact.rendered_token_ids(self.Tokenizer(), [], {}), [1, 2, 3])

    def test_malformed_token_shapes_fail_before_counting(self):
        for ids in ({"input_ids": [1, 2]}, [[1, 2]], [], [True], [1.2], [-1], None):
            t = self.Tokenizer()
            with (
                self.subTest(ids=ids),
                patch.object(t, "apply_chat_template", return_value=ids),
                self.assertRaisesRegex(ValueError, "TOKEN_RETURN_SHAPE"),
            ):
                exact.rendered_token_ids(t, [], {})

    def test_independent_render_mismatch_fails(self):
        t = self.Tokenizer()
        with (
            patch.object(t, "encode", return_value=[9]),
            self.assertRaisesRegex(ValueError, "TOKEN_RENDER_MISMATCH"),
        ):
            exact.rendered_token_ids(t, [], {})


class StagedVerifierFlow(unittest.TestCase):
    """External-package stubs prove orchestration, never compiler acceptance."""

    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads(
            subprocess.check_output(["node", str(BASE / "runtime-readiness.mjs")])
        )

    def exercise(self, failure=None):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "runtime").mkdir()
            home = root / "cache"
            bootstrap = (BASE / "runtime/bootstrap-private-lead-vllm.sh").read_text()
            contract = serving.launch_contract(bootstrap)
            bootstrap = bootstrap.replace(
                "CACHE=" + contract["values"]["CACHE"], "CACHE=" + str(home)
            )
            (root / "runtime/bootstrap-private-lead-vllm.sh").write_text(bootstrap)
            contract = serving.launch_contract(bootstrap)
            snapshot = (
                home
                / "hub/models--nvidia--Qwen3.5-122B-A10B-NVFP4/snapshots"
                / contract["values"]["REVISION"]
            )
            snapshot.mkdir(parents=True)
            hashes = {}
            for name in ("config.json", "tokenizer.json", "tokenizer_config.json"):
                (snapshot / name).write_text('{"vocab_size":8}')
                hashes[name] = exact.sha(snapshot / name)
            (root / "expected-tokenizer.json").write_text(
                json.dumps(
                    {
                        "files": hashes,
                        "template": __import__("hashlib")
                        .sha256(b"template")
                        .hexdigest(),
                    }
                )
            )
            (root / "runtime-requests.json").write_text(json.dumps(self.artifact))
            env = {
                "HF_HOME": str(home),
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
            }
            facts = ("17", "12345", contract["command"], env)
            end = (
                facts
                if failure != "replaced"
                else ("17", "67890", contract["command"], env)
            )
            stages = []
            seen = []

            @dataclass
            class Config:
                backend: str = "auto"
                disable_any_whitespace: bool = False
                reasoning_parser: str = ""

            class Parser:
                def parse_args(self, argv):
                    return SimpleNamespace(
                        model_tag=argv[0],
                        model=None,
                        revision=argv[argv.index("--revision") + 1],
                    )

            class Engine:
                @staticmethod
                def from_cli_args(args):
                    # Reproduce vLLM's offline model-ID -> snapshot transformation.
                    self.assertEqual(os.environ["HF_HOME"], str(home))
                    seen.append("resolved")
                    if failure == "cache":
                        raise RuntimeError("SYNTHETIC_PRIVATE_EXCEPTION_BODY")
                    return SimpleNamespace(
                        model=str(
                            snapshot if failure != "snapshot" else snapshot.parent
                        ),
                        structured_outputs_config=Config(),
                        reasoning_parser="qwen3",
                    )

            class Tokenizer:
                def get_chat_template(self):
                    return "template"

                def encode(self, *args, **kwargs):
                    return [1]

                eos_token_id = 0

            class Params:
                def __init__(self, structured_outputs):
                    self.structured_outputs = structured_outputs

                def _validate_structured_outputs(self, c, t):
                    self.structured_outputs._backend = "xgrammar"

            class Grammar:
                def accept_tokens(self, *args):
                    return False

            class Backend:
                def __init__(self, *args):
                    pass

                def compile_grammar(self, kind, schema):
                    if "INVALID_TYPE" in schema:
                        raise ValueError("invalid synthetic schema")
                    return Grammar()

                def destroy(self):
                    pass

            fake = {
                "transformers": SimpleNamespace(
                    AutoTokenizer=SimpleNamespace(
                        from_pretrained=lambda *a, **k: Tokenizer()
                    )
                ),
                "vllm.engine.arg_utils": SimpleNamespace(AsyncEngineArgs=Engine),
                "vllm.entrypoints.openai.cli_args": SimpleNamespace(
                    make_arg_parser=lambda x: Parser()
                ),
                "vllm.utils.argparse_utils": SimpleNamespace(
                    FlexibleArgumentParser=lambda: None
                ),
                "vllm.sampling_params": SimpleNamespace(
                    SamplingParams=Params,
                    StructuredOutputsParams=lambda **k: SimpleNamespace(**k),
                    __file__=__file__,
                ),
                "vllm.v1.structured_output.backend_types": SimpleNamespace(
                    StructuredOutputOptions=SimpleNamespace(JSON="JSON")
                ),
                "vllm.v1.structured_output.backend_xgrammar": SimpleNamespace(
                    XgrammarBackend=Backend
                ),
            }

            def progress(stage):
                stages.append(stage)
                if stage == "EXACT_IMPORTS":
                    sys.modules.update(fake)

            def inventory(path, resolved):
                return {"resolved": resolved}, Tokenizer()

            with (
                patch.dict(sys.modules, {}),
                patch.dict(os.environ, {}),
                patch.object(serving, "process_facts", side_effect=[facts, end]),
                patch.object(exact, "inventory", side_effect=inventory),
                patch.object(
                    exact,
                    "run",
                    return_value={"status": "PASS", "modelInference": "NOT_RUN"},
                ),
            ):
                result = serving.run(root, progress=progress)
            return result, stages, seen

    def test_full_staging_passes_offline_snapshot_path_without_completion(self):
        result, stages, seen = self.exercise()
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["serverIdentityStable"])
        self.assertEqual(len(result["negativeControls"]), 6)
        self.assertEqual(seen, ["resolved"])
        self.assertLess(stages.index("CACHE_BINDING"), stages.index("EXACT_IMPORTS"))

    def test_cache_exception_retains_stage_without_secret_message(self):
        result, stages, _ = self.exercise("cache")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["stage"], "MODEL_RESOLUTION")
        self.assertNotIn("SYNTHETIC_PRIVATE_EXCEPTION_BODY", json.dumps(result))
        self.assertNotIn("BACKEND_RESOLUTION", stages)

    def test_wrong_resolved_snapshot_never_reaches_compiler(self):
        result, stages, _ = self.exercise("snapshot")
        self.assertEqual(result["code"], "MODEL_SNAPSHOT_IDENTITY")
        self.assertNotIn("BACKEND_RESOLUTION", stages)

    def test_server_replacement_invalidates_otherwise_passing_proof(self):
        result, _, _ = self.exercise("replaced")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "SERVER_IDENTITY_CHANGED")


if __name__ == "__main__":
    unittest.main()
