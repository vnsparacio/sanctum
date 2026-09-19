"""Operator CLI for validation and bounded role execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import ConfigError, load_config, validate_model_catalog
from .integrations import CodexCatalogClient, ExternalCallError
from .product_scout import run_product_scout
from .repo_steward import run_repo_steward
from .runtime import RunMode


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "agents.json"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="sanctum-agents")
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subcommands = result.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate-config")
    subcommands.add_parser("models-check")
    run = subcommands.add_parser("run")
    run.add_argument("role", choices=["repo-steward", "product-scout"])
    run.add_argument("--mode", choices=[item.value for item in RunMode], default="shadow")
    run.add_argument("--deep", action="store_true")
    run.add_argument("--deterministic", action="store_true", help="skip model invocation for tests")
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
            print(json.dumps({
                "ok": True,
                "models": {
                    role: {"model": selected.model, "reasoning": selected.reasoning}
                    for role, selected in sorted(config.models.items())
                },
            }, sort_keys=True))
            return 0
        if args.role == "repo-steward":
            result = run_repo_steward(
                config,
                ROOT,
                RunMode(args.mode),
                use_model=not args.deterministic,
                deep=args.deep,
            )
        elif args.deterministic:
            raise ValueError("Product Scout deterministic runs require an explicit test fixture")
        else:
            result = run_product_scout(config, ROOT, RunMode(args.mode))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ConfigError, ExternalCallError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
