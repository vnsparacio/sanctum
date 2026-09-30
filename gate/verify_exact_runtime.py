"""Offline exact-runtime preparation. Never downloads, loads weights or infers.

A reviewed environment identity is mandatory. An inventory is a candidate record,
not compiler proof. This command calls the installed vLLM 0.20.1 backend itself.
"""

import argparse
import hashlib
import importlib
import importlib.metadata as metadata
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "src"))
from backends import PrivateLeadBackend, generation_order, generation_wire_json
from common import canonical, digest, strict_json

__all__ = ["generation_order"]

SURFACES = (
    "ordinaryIneligible",
    "ordinaryEligible",
    "researchIneligible",
    "researchEligible",
    "testOnlyIneligible",
    "reviewer",
)
TOKEN_FILES = (
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "chat_template.jinja",
    "vocab.json",
    "merges.txt",
    "added_tokens.json",
)
BACKENDS = {
    "xgrammar": ("backend_xgrammar", "XgrammarBackend"),
    "outlines": ("backend_outlines", "OutlinesBackend"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rendered_token_ids(tokenizer, messages, template_kwargs):
    """Count explicit flat IDs, never BatchEncoding mapping keys."""
    ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        return_dict=False,
        add_generation_prompt=True,
        **template_kwargs,
    )
    if (
        type(ids) is not list
        or not ids
        or any(type(x) is not int or x < 0 for x in ids)
    ):
        raise ValueError("TOKEN_RETURN_SHAPE")
    rendered = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, **template_kwargs
    )
    if type(rendered) is not str or ids != tokenizer.encode(
        rendered, add_special_tokens=False
    ):
        raise ValueError("TOKEN_RENDER_MISMATCH")
    return ids


def packages():
    # Full resolved distribution graph, including compiler transitive versions.
    return dict(
        sorted(
            (
                d.metadata["Name"].lower().replace("_", "-"),
                {
                    "version": d.version,
                    "record_sha256": hashlib.sha256(
                        (d.read_text("RECORD") or "").encode()
                    ).hexdigest(),
                },
            )
            for d in metadata.distributions()
        )
    )


def not_run(code):
    return {
        "schema": "sanctum-exact-runtime-verification/v1",
        "status": "NOT_RUN",
        "code": code,
        "exactCompiler": "NOT_RUN",
        "tokenMeasurement": "NOT_RUN",
        "liveEndpoint": "NOT_RUN",
    }


def inventory(tokenizer_root, resolved):
    if not tokenizer_root or not tokenizer_root.is_dir():
        raise ValueError("TOKENIZER_UNAVAILABLE")
    profile = strict_json(
        (BASE / "runtime/private-lead-interface-profile.json").read_text()
    )
    if tokenizer_root.name != profile["revision"]:
        raise ValueError("TOKENIZER_REVISION_UNVERIFIED")
    if (
        resolved.get("model") != profile["model"]
        or resolved.get("model_revision") != profile["revision"]
    ):
        raise ValueError("MODEL_IDENTITY")
    if set(resolved.get("per_surface_backend", {})) != set(SURFACES):
        raise ValueError("BACKEND_IDENTITY_ABSENT")
    if any(x not in BACKENDS for x in resolved["per_surface_backend"].values()):
        raise ValueError("BACKEND_ADAPTER_UNAVAILABLE")
    if (
        type(resolved.get("selection_config", {}).get("disable_any_whitespace"))
        is not bool
    ):
        raise ValueError("BACKEND_CONFIG_ABSENT")
    if resolved.get("selection_config", {}).get("backend") not in ("auto", *BACKENDS):
        raise ValueError("BACKEND_CONFIG_ABSENT")
    evidence = resolved.get("resolution_evidence_sha256", "")
    if len(evidence) != 64 or any(c not in "0123456789abcdef" for c in evidence):
        raise ValueError("BACKEND_RESOLUTION_UNVERIFIED")
    ps = packages()
    if ps.get("vllm", {}).get("version") != "0.20.1":
        raise ValueError("VLLM_IDENTITY_ABSENT")
    for backend in set(resolved["per_surface_backend"].values()):
        if ("xgrammar" if backend == "xgrammar" else "outlines-core") not in ps:
            raise ValueError("COMPILER_IDENTITY_ABSENT")
    files = {
        name: sha(tokenizer_root / name)
        for name in TOKEN_FILES
        if (tokenizer_root / name).is_file()
    }
    if not {"config.json", "tokenizer.json", "tokenizer_config.json"} <= set(files):
        raise ValueError("TOKENIZER_BYTES_ABSENT")
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(tokenizer_root), local_files_only=True, trust_remote_code=False
    )
    template = tokenizer.get_chat_template()
    if not isinstance(template, str) or not template:
        raise ValueError("TEMPLATE_UNAVAILABLE")
    compiler_sources = {}
    for name in sorted(set(resolved["per_surface_backend"].values())):
        module = importlib.import_module(
            "vllm.v1.structured_output." + BACKENDS[name][0]
        )
        compiler_sources[name] = sha(Path(module.__file__))
    return {
        "schema": "sanctum-exact-runtime-environment/v1",
        "packages": ps,
        "resolved": resolved,
        "tokenizer_files": files,
        "tokenizer_revision": tokenizer_root.name,
        "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
        "compiler_sources": compiler_sources,
    }, tokenizer


def verify_artifact(artifact):
    if artifact.get("schema") != "sanctum-runtime-readiness/v1" or set(
        artifact["surfaces"]
    ) != set(SURFACES):
        raise ValueError("SURFACE_ENUMERATION")
    for _label, row in artifact["surfaces"].items():
        if (
            digest(row["request"]["schema"]) != row["schemaDigest"]
            or digest(row["semanticSchema"]) != row["semanticSchemaDigest"]
            or len(row["representatives"]) != len(row["request"]["schema"]["oneOf"])
        ):
            raise ValueError("SCHEMA_IDENTITY")
        host = row.get("hostSemanticValidation", {})
        controls = host.get("negativeControls", [])
        if (
            host.get("schema") != "sanctum-host-semantic-readiness/v1"
            or host.get("status") != "PASS"
            or host.get("semanticSchemaDigest") != row["semanticSchemaDigest"]
            or host.get("representativesDigest") != digest(row["representatives"])
            or host.get("positiveBranches") != len(row["semanticSchema"]["oneOf"])
            or not controls
            or any(c.get("rejected") is not True for c in controls)
            or {c.get("branch") for c in controls}
            != set(range(host["positiveBranches"]))
        ):
            raise ValueError("HOST_SEMANTIC_VALIDATION")
    if set(artifact["messages"]) != {
        "ordinaryInitial",
        "accumulatedObservations",
        "activeCorrection",
        "nearCharacterLimit",
        "postPatchContinue",
        "reviewer",
    }:
        raise ValueError("REQUEST_ENUMERATION")


def run(artifact, expected=None, tokenizer_root=None):
    verify_artifact(artifact)
    if expected is None:
        return not_run("EXACT_ENVIRONMENT_IDENTITY_ABSENT")
    try:
        observed, tokenizer = inventory(tokenizer_root, expected["resolved"])
    except (ImportError, ValueError, KeyError, OSError) as error:
        code = (
            str(error)
            if type(error) is ValueError
            else "EXACT_PACKAGES_OR_BYTES_UNAVAILABLE"
        )
        return not_run(code)
    observed["artifactDigest"] = digest(artifact)
    if observed != expected:
        return not_run("EXACT_ENVIRONMENT_IDENTITY_MISMATCH")
    from vllm.v1.structured_output.backend_types import StructuredOutputOptions

    resolved = observed["resolved"]
    config = SimpleNamespace(
        structured_outputs_config=SimpleNamespace(**resolved["selection_config"]),
        speculative_config=None,
    )
    model_config = strict_json((tokenizer_root / "config.json").read_text())
    vocab_size = model_config.get(
        "vocab_size", model_config.get("text_config", {}).get("vocab_size")
    )
    if type(vocab_size) is not int:
        raise ValueError("VOCAB_IDENTITY")
    rows = []
    for label, row in artifact["surfaces"].items():
        backend_name = resolved["per_surface_backend"][label]
        module_name, class_name = BACKENDS[backend_name]
        backend = getattr(
            importlib.import_module("vllm.v1.structured_output." + module_name),
            class_name,
        )(config, tokenizer, vocab_size)
        try:
            for kind, schema in (("generation", row["request"]["schema"]),):
                # Compile the whole production generation schema unchanged.
                # Authoritative semantic constraints are checked on the Mac.
                try:
                    branches = []
                    for value in row["representatives"]:
                        # vLLM 0.20.1 xgrammar reset leaves the wrapper's terminal
                        # flag set after EOS. Compile a fresh request grammar for
                        # each branch; the backend may cache its immutable context.
                        grammar = backend.compile_grammar(
                            StructuredOutputOptions.JSON, generation_wire_json(schema)
                        )
                        tokens = tokenizer.encode(
                            generation_wire_json(value), add_special_tokens=False
                        )
                        accepted = all(
                            grammar.accept_tokens("offline", [token])
                            for token in tokens
                        )
                        # Match backend EOS behavior one token at a time as serving does.
                        grammar.is_terminated()
                        accepted = accepted and grammar.accept_tokens(
                            "offline", [tokenizer.eos_token_id]
                        )
                        branches.append(
                            {
                                "accepted": bool(accepted),
                                "terminated": bool(grammar.is_terminated()),
                                "tokens": len(tokens),
                            }
                        )
                    rows.append(
                        {
                            "surface": label,
                            "schemaKind": kind,
                            "schemaDigest": digest(schema),
                            "wireSchemaSha256": hashlib.sha256(
                                generation_wire_json(schema).encode()
                            ).hexdigest(),
                            "backend": backend_name,
                            "compiled": True,
                            "branches": branches,
                        }
                    )
                except Exception:
                    rows.append(
                        {
                            "surface": label,
                            "schemaKind": kind,
                            "schemaDigest": digest(schema),
                            "wireSchemaSha256": hashlib.sha256(
                                generation_wire_json(schema).encode()
                            ).hexdigest(),
                            "backend": backend_name,
                            "compiled": False,
                            "code": "COMPILER_OR_REACHABILITY_FAILED",
                        }
                    )
        finally:
            backend.destroy()
    settings = strict_json((BASE / "SETTINGS.json").read_text())
    builder = PrivateLeadBackend(settings)
    measurements = []
    for label, request in artifact["messages"].items():
        payload = builder.proposal_payload(request)
        messages = payload["messages"]
        ids = rendered_token_ids(tokenizer, messages, payload["chat_template_kwargs"])
        system = len(tokenizer.encode(messages[0]["content"], add_special_tokens=False))
        user = len(tokenizer.encode(messages[1]["content"], add_special_tokens=False))
        window = artifact["profile"]["modelWindow"]
        reserve = artifact["profile"]["reservedOutput"]
        measurements.append(
            {
                "state": label,
                "systemMessageTokens": system,
                "userMessageTokens": user,
                "totalInputTokens": len(ids),
                "templateOverheadTokens": len(ids) - system - user,
                "reservedOutputTokens": reserve,
                "proposalOutputTokens": payload["max_tokens"],
                "modelWindow": window,
                "remainingContextHeadroom": window - len(ids) - reserve,
            }
        )
    token_fit = all(row["remainingContextHeadroom"] >= 0 for row in measurements)
    passed = token_fit and all(
        r["compiled"] and all(b["accepted"] and b["terminated"] for b in r["branches"])
        for r in rows
    )
    return {
        "schema": "sanctum-exact-runtime-verification/v1",
        "status": "PASS" if passed else "FAIL",
        "environment": observed,
        "environmentDigest": digest(observed),
        "artifactDigest": digest(artifact),
        "exactCompiler": rows,
        "tokenMeasurement": measurements,
        "messageCountConvention": "content-only plus rendered total and overhead",
        "hostSemanticValidation": {
            label: row["hostSemanticValidation"]
            for label, row in artifact["surfaces"].items()
        },
        "semanticCompiler": "NOT_REQUIRED_HOST_AUTHORITATIVE",
        "tokenFit": token_fit,
        "liveEndpoint": "NOT_RUN",
        "modelInference": "NOT_RUN",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--environment", type=Path)
    p.add_argument("--tokenizer", type=Path)
    p.add_argument("--inventory-from-resolved", type=Path)
    a = p.parse_args()
    artifact = strict_json(a.artifact.read_text())
    verify_artifact(artifact)
    if a.inventory_from_resolved:
        result, _ = inventory(
            a.tokenizer, strict_json(a.inventory_from_resolved.read_text())
        )
        result["artifactDigest"] = digest(artifact)
        print(canonical(result))
        return
    result = run(
        artifact,
        strict_json(a.environment.read_text()) if a.environment else None,
        a.tokenizer,
    )
    print(canonical(result))
    if result["status"] != "PASS":
        sys.exit(2)


if __name__ == "__main__":
    main()
