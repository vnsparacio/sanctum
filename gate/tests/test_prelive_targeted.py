"""R1/R2 offline regressions: synthetic stores, provider and compiler API only.

The fake grammar models the pinned wrapper's sticky termination on reset. These
checks test verifier orchestration; they are never exact compiler/tokenizer proof.
"""

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE / "src"), str(BASE), str(BASE / "tests")]
import verify_exact_runtime as exact
from common import Refused, canonical, database, digest
from experiment import ExperimentLedger, process_identity
from experiment_lifecycle import ExperimentSupervisor
from lifecycle import Private80BLifecycle, PrivateLeadLifecycle
from test_prelive import Fixture, Provider


class LeaseRepairTests(Fixture):
    def test_denied_ordinary_calls_leave_neither_release_a_lease(self):
        for stopped in (False, True):
            if stopped:
                self.ledger.stop(self.binding, "CANCELLED")
            for cls in (PrivateLeadLifecycle, Private80BLifecycle):
                for method in ("infer", "propose"):
                    with self.subTest(
                        stopped=stopped, release=cls.__name__, method=method
                    ):
                        provider = Provider()
                        lc = cls(self.settings, provider=provider, now=self.now)
                        # Isolate ordinary admission/release from the independently
                        # tested supervisor. The old admission bug must not retire
                        # the fixture experiment before the next subcase.
                        with (
                            patch.object(lc, "sweep"),
                            self.assertRaisesRegex(
                                Refused,
                                (
                                    "private_80b_retired"
                                    if cls is Private80BLifecycle
                                    else "experiment_ownership_required"
                                ),
                            ),
                        ):
                            getattr(lc, method)("d" * 32, {})
                        with database(lc.root) as c:
                            self.assertEqual(
                                c.execute("select count(*) from leases").fetchone()[0],
                                0,
                            )
                        self.assertEqual(provider.created, 0)
                        self.assertEqual(provider.deleted, [])

    def test_existing_ordinary_leases_prevent_experiment_creation(self):
        # Retire the fixture's empty experiment before testing a fresh one.
        self.update(state="COMPLETE", cleanup="CONFIRMED")
        for root in (self.state, self.root):
            for active in (0, 1):
                with self.subTest(root=root.name, active=active):
                    with database(root) as c:
                        c.execute(
                            "insert into leases values (?,?,?,0)",
                            ("d" * 32, 999, active),
                        )
                    with self.assertRaisesRegex(Refused, "experiment_existing_leases"):
                        self.ledger.create(
                            {**self.binding, "experiment_id": "e" * 32},
                            owner_pid=os.getpid(),
                            owner_process=process_identity(os.getpid()),
                            ordinary_root=self.root,
                        )
                    with database(root) as c:
                        self.assertEqual(
                            c.execute("select active from leases").fetchone()[0], active
                        )
                        c.execute("delete from leases")
                    self.assertIsNone(self.ledger.current())

    def test_installed_create_command_checks_other_release_leases(self):
        import experiment_control

        self.update(state="COMPLETE", cleanup="CONFIRMED")
        binding_file = self.root / "binding.json"
        binding_file.write_text(canonical({**self.binding, "experiment_id": "e" * 32}))
        binding_file.chmod(0o600)
        with database(self.root) as c:
            c.execute("insert into leases values (?,?,0,0)", ("d" * 32, 2000))
        argv = [
            "experiment_control.py",
            "create",
            "--binding",
            str(binding_file),
            "--owner-pid",
            str(os.getpid()),
        ]
        with (
            patch.object(experiment_control, "verify_release"),
            patch.object(
                experiment_control, "load_settings", return_value=self.settings
            ),
            patch.object(
                experiment_control, "installed_identity", return_value=self.identity
            ),
            patch.object(
                experiment_control, "ExperimentLedger", return_value=self.ledger
            ),
            patch.object(experiment_control.os, "umask"),
            patch.object(sys, "argv", argv),
        ):
            with self.assertRaisesRegex(Refused, "experiment_existing_leases"):
                experiment_control.main()
        self.assertIsNone(self.ledger.current())

    def test_terminal_cleanup_preserves_foreign_leases_and_waits_for_both_stores(self):
        provider = Provider()
        lc = PrivateLeadLifecycle(self.settings, provider=provider, now=self.now)
        supervisor = ExperimentSupervisor(self.ledger, lc, is_alive=lambda *_: False)
        for root in (self.state, self.root):
            for active in (0, 1):
                for expires in (999, 2000):
                    with self.subTest(root=root.name, active=active, expires=expires):
                        self.update(
                            state="CLEANUP_REQUIRED",
                            cleanup="REQUIRED",
                            allocation="OWNED",
                            allocation_id="synthetic-pod",
                            allocation_name="synthetic-name",
                            lease_scope="e" * 32,
                            worker_pid=999999,
                            worker_process="f" * 64,
                        )
                        provider.rows = [
                            {"id": "synthetic-pod", "name": "synthetic-name"}
                        ]
                        lc.save(
                            lc.state(),
                            phase="READY",
                            pod_id="synthetic-pod",
                            pod_name="synthetic-name",
                        )
                        with database(self.state) as c:
                            c.execute(
                                "insert into leases values (?,?,1,0)", ("e" * 32, 2000)
                            )
                        with database(root) as c:
                            c.execute(
                                "insert into leases values (?,?,?,0)",
                                ("d" * 32, expires, active),
                            )
                        result = supervisor.tick()
                        self.assertEqual(result["allocation"], "ABSENT")
                        self.assertEqual(result["state"], "CLEANUP_REQUIRED")
                        self.assertNotEqual(result["cleanup"], "CONFIRMED")
                        self.assertIsNotNone(self.ledger.current())
                        with database(root) as c:
                            self.assertEqual(
                                c.execute(
                                    "select active,expires from leases where scope=?",
                                    ("d" * 32,),
                                ).fetchone(),
                                (active, expires),
                            )
                            # Simulate explicit reconciliation by the lease owner.
                            c.execute("delete from leases where scope=?", ("d" * 32,))
                        result = supervisor.tick()
                        self.assertEqual(result["state"], "COMPLETE")
                        self.assertEqual(result["cleanup"], "CONFIRMED")
                        for store in (self.state, self.root):
                            with database(store) as c:
                                self.assertEqual(
                                    c.execute("select count(*) from leases").fetchone()[
                                        0
                                    ],
                                    0,
                                )

    def test_no_allocation_cleanup_still_requires_both_stores_empty(self):
        lc = PrivateLeadLifecycle(self.settings, provider=Provider(), now=self.now)
        self.ledger.stop(self.binding, "CANCELLED")
        with database(self.root) as c:
            c.execute("insert into leases values (?,?,1,0)", ("d" * 32, 999))
        with patch.object(
            lc.provider, "pods", side_effect=AssertionError("no provider call")
        ):
            result = ExperimentSupervisor(
                self.ledger, lc, is_alive=lambda *_: False
            ).tick()
        self.assertEqual(result["state"], "CLEANUP_REQUIRED")
        self.assertNotEqual(result["cleanup"], "CONFIRMED")

    def test_same_scope_in_other_release_is_never_deleted_as_diagnostic_lease(self):
        self.update(lease_scope="d" * 32)
        self.ledger.stop(self.binding, "CANCELLED")
        with database(self.root) as c:
            c.execute("insert into leases values (?,?,1,0)", ("d" * 32, 2000))
        lc = PrivateLeadLifecycle(self.settings, provider=Provider(), now=self.now)
        result = ExperimentSupervisor(self.ledger, lc, is_alive=lambda *_: False).tick()
        self.assertEqual(result["state"], "CLEANUP_REQUIRED")
        with database(self.root) as c:
            self.assertEqual(c.execute("select active from leases").fetchone()[0], 1)

    def test_live_diagnostic_worker_blocks_own_lease_reconciliation(self):
        self.update(worker_pid=987654, worker_process="f" * 64, lease_scope="d" * 32)
        self.ledger.stop(self.binding, "CANCELLED")
        with database(self.state) as c:
            c.execute("insert into leases values (?,?,1,0)", ("d" * 32, 2000))
        lc = PrivateLeadLifecycle(self.settings, provider=Provider(), now=self.now)
        result = ExperimentSupervisor(
            self.ledger, lc, is_alive=lambda pid, _: pid == 987654, kill=lambda *_: None
        ).tick()
        self.assertEqual(result["state"], "CLEANUP_REQUIRED")
        with database(self.state) as c:
            self.assertEqual(c.execute("select active from leases").fetchone()[0], 1)

    def test_ordinary_behavior_without_experiment_retains_idle_lease(self):
        self.update(state="COMPLETE", cleanup="CONFIRMED")
        for cls in (PrivateLeadLifecycle,):
            lc = cls(self.settings, provider=Provider(), now=self.now)
            lc.acquire("d" * 32)
            lc.release("d" * 32)
            with database(lc.root) as c:
                self.assertEqual(
                    c.execute("select active,closing from leases").fetchone(), (0, 0)
                )


class AdmissionRaceTests(unittest.TestCase):
    def test_cross_process_create_and_ordinary_acquire_are_mutually_exclusive(self):
        code = """import json,sys,os
from pathlib import Path
sys.path[:0]=[sys.argv[1]]
from common import Refused
from experiment import ExperimentLedger,process_identity
from lifecycle import PrivateLeadLifecycle,Private80BLifecycle
root,settings,binding,operation,release=json.loads(sys.argv[2])
ledger=ExperimentLedger(Path(root)/'private-lead',lambda:1000)
print('READY',flush=True);input()
try:
 if operation=='create':ledger.create(binding,owner_pid=os.getpid(),owner_process=process_identity(os.getpid()),ordinary_root=Path(root))
 else:(PrivateLeadLifecycle if release=='lead' else Private80BLifecycle)(settings,now=lambda:1000).acquire('d'*32)
 print('OK',flush=True)
except Refused:print('REFUSED',flush=True)
"""
        for release in ("lead", "80b"):
            for order in (("create", "acquire"), ("acquire", "create")):
                with (
                    self.subTest(release=release, first=order[0]),
                    tempfile.TemporaryDirectory() as td,
                ):
                    root = Path(td)
                    root.chmod(0o700)
                    settings = json.loads((BASE / "SETTINGS.json").read_text())
                    settings["state_directory"] = td
                    settings["gpu"][
                        "enabled"
                    ] = True  # Synthetic ordinary-acquisition contender.
                    binding = {
                        "experiment_id": "a" * 32,
                        "source_id": "b" * 64,
                        "install_id": "c" * 64,
                        "deadline": 1900,
                    }
                    children = [
                        subprocess.Popen(
                            [
                                sys.executable,
                                "-B",
                                "-c",
                                code,
                                str(BASE / "src"),
                                json.dumps([td, settings, binding, op, release]),
                            ],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                        for op in order
                    ]
                    try:
                        for child in children:
                            self.assertEqual(child.stdout.readline().strip(), "READY")
                        for child in children:
                            child.stdin.write("\n")
                            child.stdin.flush()
                        results = []
                        for child in children:
                            out, err = child.communicate(timeout=20)
                            self.assertEqual(child.returncode, 0, err)
                            results.append(out.strip())
                        self.assertEqual(sorted(results), ["OK", "REFUSED"])
                        ledger = ExperimentLedger(root / "private-lead", lambda: 1000)
                        with database(
                            root / ("private-lead" if release == "lead" else "")
                        ) as c:
                            leases = c.execute(
                                "select count(*) from leases"
                            ).fetchone()[0]
                        self.assertEqual(leases, 0 if ledger.current() else 1)
                    finally:
                        for child in children:
                            if child.poll() is None:
                                child.kill()
                                child.wait()
                            for stream in (child.stdin, child.stdout, child.stderr):
                                stream.close()


class CompilerRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads(
            subprocess.check_output(["node", str(BASE / "runtime-readiness.mjs")])
        )

    def run_verifier(self, *, reject=False, compile_error=False):
        # Stub external packages only. The full production verifier control flow,
        # artifact checks, request builder and result aggregation remain real.
        compiled = []
        grammars = []
        destroyed = []

        class Tokenizer:
            eos_token_id = 0

            def encode(self, text, **_):
                return [1, 2, 3] if text == "synthetic rendered chat" else [1, 2]

            def apply_chat_template(self, *args, **kwargs):
                return (
                    [1, 2, 3] if kwargs.get("tokenize") else "synthetic rendered chat"
                )

        class Grammar:
            def __init__(self):
                self.terminated = False
                self.seen = []

            def reset(self):
                self.seen = []  # Pinned xgrammar wrapper retains termination.

            def accept_tokens(self, request_id, tokens):
                if self.terminated:
                    return False
                if reject and len(grammars) == 2:
                    return False
                self.seen += tokens
                self.terminated = tokens == [0]
                return True

            def is_terminated(self):
                return self.terminated

        class Backend:
            def __init__(self, *args):
                pass

            def compile_grammar(self, kind, schema):
                compiled.append((kind, schema))
                if compile_error:
                    raise ValueError("synthetic compiler rejection")
                grammar = Grammar()
                grammars.append(grammar)
                return grammar

            def destroy(self):
                destroyed.append(True)

        environment = {
            "resolved": {
                "selection_config": {
                    "backend": "auto",
                    "disable_any_whitespace": False,
                },
                "per_surface_backend": {k: "xgrammar" for k in exact.SURFACES},
            }
        }
        expected = {**environment, "artifactDigest": digest(self.artifact)}
        backend_types = SimpleNamespace(
            StructuredOutputOptions=SimpleNamespace(JSON="JSON")
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config.json").write_text('{"vocab_size":3}')
            with (
                patch.object(
                    exact, "inventory", return_value=(environment, Tokenizer())
                ),
                patch.object(
                    exact.importlib,
                    "import_module",
                    return_value=SimpleNamespace(XgrammarBackend=Backend),
                ),
                patch.dict(
                    sys.modules,
                    {"vllm.v1.structured_output.backend_types": backend_types},
                ),
            ):
                result = exact.run(copy.deepcopy(self.artifact), expected, root)
        return result, compiled, grammars, destroyed

    def test_fresh_grammar_accepts_all_successive_branches_including_eos(self):
        result, compiled, grammars, destroyed = self.run_verifier()
        self.assertEqual(result["status"], "PASS")
        expected = [
            ("JSON", exact.generation_wire_json(row["request"]["schema"]))
            for row in self.artifact["surfaces"].values()
            for _ in row["representatives"]
        ]
        self.assertEqual(compiled, expected)
        self.assertEqual(len(grammars), len(expected))
        self.assertEqual(len(grammars), 29)
        self.assertTrue(
            all(row["schemaKind"] == "generation" for row in result["exactCompiler"])
        )
        self.assertEqual(result["semanticCompiler"], "NOT_REQUIRED_HOST_AUTHORITATIVE")
        self.assertEqual(set(result["hostSemanticValidation"]), set(exact.SURFACES))
        for row in result["exactCompiler"]:
            schema = self.artifact["surfaces"][row["surface"]]["request"]["schema"]
            self.assertEqual(
                row["wireSchemaSha256"],
                hashlib.sha256(exact.generation_wire_json(schema).encode()).hexdigest(),
            )
        self.assertTrue(all(g.seen == [1, 2, 0] for g in grammars))
        self.assertEqual(len(destroyed), 6)
        self.assertEqual(result["liveEndpoint"], "NOT_RUN")
        self.assertEqual(result["modelInference"], "NOT_RUN")

    def test_rejected_branch_still_fails_overall_verification(self):
        result, _, _, destroyed = self.run_verifier(reject=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(len(destroyed), 6)
        self.assertFalse(result["exactCompiler"][0]["branches"][1]["accepted"])

    def test_compile_error_fails_and_destroys_each_backend(self):
        result, _, _, destroyed = self.run_verifier(compile_error=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(len(destroyed), 6)
        self.assertTrue(all(not row["compiled"] for row in result["exactCompiler"]))


if __name__ == "__main__":
    unittest.main()
