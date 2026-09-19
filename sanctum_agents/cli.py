"""Operator CLI for validation and bounded role execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import ConfigError, load_config, validate_model_catalog
from .integrations import CodexCatalogClient, ExternalCallError


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "agents.json"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="sanctum-agents")
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subcommands = result.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate-config")
    subcommands.add_parser("models-check")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate-config":
            print(json.dumps({"ok": True, "config": str(config.path)}, sort_keys=True))
            return 0
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
    except (ConfigError, ExternalCallError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
