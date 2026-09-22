"""Operator CLI for validation and bounded role execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ConfigError, load_config, validate_model_catalog
from .integrations import CodexCatalogClient, ExternalCallError, LinearGraphQLClient
from .linear_integration import (
    LinearWriter,
    capture_qualified_metadata,
    load_qualified_metadata,
)
from .product_scout import run_product_scout
from .repo_steward import run_repo_steward
from .reviewer import run_reviewer
from .runtime import RunMode
from .scheduler import load_schedule_plan
from .symphony_recovery import run_with_recovery
from .symphony_supervisor import (
    preflight as symphony_preflight,
)
from .symphony_supervisor import resume_from_incident
from .triage import capture_live_snapshot, run_triage

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "agents.json"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="sanctum-agents")
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subcommands = result.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate-config")
    subcommands.add_parser("models-check")
    preflight = subcommands.add_parser("symphony-preflight")
    preflight.add_argument(
        "--worker-class", choices=["standard", "deep"], default="standard"
    )
    symphony_run = subcommands.add_parser("symphony-run")
    symphony_run.add_argument(
        "--worker-class", choices=["standard", "deep"], default="standard"
    )
    resume = subcommands.add_parser("symphony-resume")
    resume.add_argument("--incident", type=Path, required=True)
    resume.add_argument("--issue", required=True)
    subcommands.add_parser("schedule-plan")
    subcommands.add_parser("linear-metadata-capture")
    linear_check = subcommands.add_parser("linear-metadata-check")
    linear_check.add_argument("--path", type=Path)
    run = subcommands.add_parser("run")
    run.add_argument(
        "role", choices=["repo-steward", "product-scout", "triage", "reviewer"]
    )
    run.add_argument(
        "--mode", choices=[item.value for item in RunMode], default="shadow"
    )
    run.add_argument("--deep", action="store_true")
    run.add_argument("--snapshot", type=Path)
    run.add_argument("--packet", type=Path)
    run.add_argument("--escalate", action="store_true")
    run.add_argument(
        "--deterministic", action="store_true", help="skip model invocation for tests"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate-config":
            print(json.dumps({"ok": True, "config": str(config.path)}, sort_keys=True))
            return 0
        if args.command == "models-check":
            catalog = CodexCatalogClient().list_models()
            validate_model_catalog(config, catalog)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "models": {
                            role: {
                                "model": selected.model,
                                "reasoning": selected.reasoning,
                            }
                            for role, selected in sorted(config.models.items())
                        },
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "symphony-preflight":
            print(
                json.dumps(
                    symphony_preflight(config, ROOT, worker_class=args.worker_class),
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "symphony-run":
            return run_with_recovery(config, ROOT, worker_class=args.worker_class)
        if args.command == "symphony-resume":
            print(
                json.dumps(
                    resume_from_incident(config, args.incident, args.issue),
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "schedule-plan":
            print(
                json.dumps(
                    load_schedule_plan(ROOT / "config" / "schedules.json"),
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "linear-metadata-check":
            path = args.path or (
                config.runtime_prefix() / "state" / "linear-metadata.json"
            )
            metadata = load_qualified_metadata(
                path, config.project["linear_project_slug"]
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "path": str(path),
                        "project_slug": metadata.project_slug,
                        "state_count": len(metadata.states),
                        "label_count": len(metadata.labels),
                        "template_count": len(metadata.templates),
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "linear-metadata-capture":
            path = config.runtime_prefix() / "state" / "linear-metadata.json"
            metadata = capture_qualified_metadata(
                LinearGraphQLClient(), config.project["linear_project_slug"], path
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "path": str(path),
                        "project_slug": metadata.project_slug,
                        "state_count": len(metadata.states),
                        "label_count": len(metadata.labels),
                        "template_count": len(metadata.templates),
                    },
                    sort_keys=True,
                )
            )
            return 0
        mode = RunMode(args.mode)
        linear_writer = None
        linear_client = None
        metadata = None
        role_key = args.role.replace("-", "_")
        if (
            mode is RunMode.LIVE
            and role_key in {"repo_steward", "product_scout", "triage"}
            and config.roles[role_key].write_enabled
        ):
            metadata = load_qualified_metadata(
                config.runtime_prefix() / "state" / "linear-metadata.json",
                config.project["linear_project_slug"],
            )
            linear_client = LinearGraphQLClient()
            linear_writer = LinearWriter(linear_client, metadata)
        if args.role == "repo-steward":
            result = run_repo_steward(
                config,
                ROOT,
                mode,
                use_model=not args.deterministic,
                deep=args.deep,
                linear_writer=linear_writer,
            )
        elif args.role == "triage":
            if args.snapshot is None:
                if (
                    mode is not RunMode.LIVE
                    or linear_client is None
                    or metadata is None
                ):
                    raise ValueError(
                        "Triage requires --snapshot until live Linear qualification"
                    )
                args.snapshot = (
                    config.runtime_prefix() / "state" / "linear-triage-snapshot.json"
                )
                capture_live_snapshot(
                    linear_client,
                    metadata,
                    args.snapshot,
                    max_items=config.roles["triage"].max_items,
                )
            if args.deterministic:
                raise ValueError(
                    "Triage deterministic runs require an explicit test fixture"
                )
            result = run_triage(
                config,
                ROOT,
                args.snapshot.resolve(),
                mode,
                escalate=args.escalate,
                linear_writer=linear_writer,
            )
        elif args.role == "reviewer":
            if args.packet is None:
                raise ValueError(
                    "Reviewer requires --packet until live GitHub/Linear qualification"
                )
            if args.deterministic:
                raise ValueError(
                    "Reviewer deterministic runs require an explicit test fixture"
                )
            result = run_reviewer(config, ROOT, args.packet.resolve(), mode)
        elif args.deterministic:
            raise ValueError(
                "Product Scout deterministic runs require an explicit test fixture"
            )
        else:
            result = run_product_scout(config, ROOT, mode, linear_writer=linear_writer)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ConfigError, ExternalCallError, RuntimeError, ValueError) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
