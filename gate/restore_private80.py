"""Validate the preserved 80B descriptor and a no-download synthetic rehydration."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent

REQUIRED = (
    "model",
    "revision",
    "container_image",
    "python",
    "cuda",
    "vllm_version",
    "quantization",
    "served_model_name",
    "launch",
    "cache_root",
    "runtime_root",
    "hardware",
    "health",
    "restore",
)


def descriptor():
    value = json.loads((BASE / "runtime/private-releases.json").read_text())
    release = value["releases"]["private-80b-accepted-v1"]
    if any(not release.get(key) for key in REQUIRED):
        raise ValueError("incomplete_80b_descriptor")
    if len(release["revision"]) != 40 or not release["container_image"].startswith(
        "runpod/pytorch@sha256:"
    ):
        raise ValueError("mutable_80b_identity")
    return release


def dry_run(root):
    release = descriptor()
    cache = Path(root) / release["release_id"] / "snapshots" / release["revision"]
    cache.mkdir(parents=True)
    artifact = cache / "synthetic-index.json"
    artifact.write_text(
        json.dumps({"model": release["model"], "revision": release["revision"]}) + "\n"
    )
    manifest = {
        "schema": "sanctum-private-artifact-manifest/v1",
        "model": release["model"],
        "revision": release["revision"],
        "artifacts": {artifact.name: hashlib.sha256(artifact.read_bytes()).hexdigest()},
    }
    (cache / "artifact-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True) + "\n"
    )
    observed = json.loads((cache / "artifact-manifest.json").read_text())
    if (
        observed != manifest
        or hashlib.sha256(artifact.read_bytes()).hexdigest()
        != manifest["artifacts"][artifact.name]
    ):
        raise ValueError("synthetic_manifest_failed")
    return {
        "status": "PASS",
        "download_performed": False,
        "model": release["model"],
        "revision": release["revision"],
        "restore": release["restore"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run-fixture", type=Path)
    parser.add_argument("--describe", action="store_true")
    args = parser.parse_args()
    try:
        if args.describe:
            print(json.dumps(descriptor(), indent=2))
        else:
            with tempfile.TemporaryDirectory(
                prefix="sanctum-80b-restore-", dir=args.dry_run_fixture
            ) as root:
                print(json.dumps(dry_run(root), indent=2))
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit("REFUSED: " + str(error))
