"""Strict central configuration for the agent-management system."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .implementation import LifecycleError, implementation_backend_dispatch


class ConfigError(ValueError):
    """Configuration is missing, malformed, or unsafe."""


_ROLES = {
    "repo_steward",
    "product_scout",
    "triage",
    "implementation",
    "implementation_deep",
    "reviewer",
}
_REASONING = {"low", "medium", "high", "xhigh", "max", "ultra"}


@dataclass(frozen=True)
class ModelConfig:
    model: str
    reasoning: str


@dataclass(frozen=True)
class RoleConfig:
    cadence: str
    write_enabled: bool
    wall_clock_seconds: int
    max_items: int
    max_sources: int
    max_issues_created: int
    max_retries: int
    max_turns: int
    max_tokens: int
    repository_scope: tuple[str, ...]


@dataclass(frozen=True)
class AgentConfig:
    path: Path
    project: dict[str, Any]
    runtime: dict[str, Any]
    models: dict[str, ModelConfig]
    roles: dict[str, RoleConfig]
    symphony: dict[str, Any]

    def runtime_prefix(self, env: dict[str, str] | None = None) -> Path:
        values = os.environ if env is None else env
        name = self.runtime["prefix_env"]
        raw = values.get(name) or self.runtime["default_prefix"]
        result = Path(raw).expanduser()
        if not result.is_absolute():
            raise ConfigError(f"{name} must resolve to an absolute path")
        resolved = result.resolve(strict=False)
        repository = self.path.parents[1].resolve()
        if resolved == repository or resolved.is_relative_to(repository):
            raise ConfigError(
                "agent runtime prefix must remain outside the source repository"
            )
        return resolved

    def model_for(self, role: str) -> ModelConfig:
        try:
            return self.models[role]
        except KeyError as exc:
            raise ConfigError(f"no model configured for role {role!r}") from exc


def _positive(
    data: dict[str, Any],
    key: str,
    *,
    allow_zero: bool = False,
    qualified_name: str | None = None,
) -> int:
    value = data.get(key)
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ConfigError(f"{qualified_name or key} must be a {qualifier} integer")
    return value


def _role(name: str, raw: Any) -> RoleConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"role {name} must be an object")
    if type(raw.get("write_enabled")) is not bool:
        raise ConfigError(f"role {name} write_enabled must be boolean")
    scope = raw.get("repository_scope")
    if not isinstance(scope, list) or any(
        not isinstance(item, str) or not item for item in scope
    ):
        raise ConfigError(
            f"role {name} repository_scope must be a list of non-empty strings"
        )
    cadence = raw.get("cadence")
    if not isinstance(cadence, str) or not cadence:
        raise ConfigError(f"role {name} cadence must be non-empty")
    return RoleConfig(
        cadence=cadence,
        write_enabled=raw["write_enabled"],
        wall_clock_seconds=_positive(
            raw,
            "wall_clock_seconds",
            qualified_name=f"roles.{name}.wall_clock_seconds",
        ),
        max_items=_positive(raw, "max_items"),
        max_sources=_positive(raw, "max_sources", allow_zero=True),
        max_issues_created=_positive(raw, "max_issues_created", allow_zero=True),
        max_retries=_positive(raw, "max_retries", allow_zero=True),
        max_turns=_positive(raw, "max_turns"),
        max_tokens=_positive(raw, "max_tokens"),
        repository_scope=tuple(scope),
    )


def load_config(path: str | Path) -> AgentConfig:
    source = Path(path).resolve()
    try:
        raw = json.loads(source.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot load agent config: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ConfigError("agent config schema_version must be 1")
    for key in ("project", "runtime", "models", "roles", "symphony"):
        if not isinstance(raw.get(key), dict):
            raise ConfigError(f"agent config {key} must be an object")
    if set(raw["roles"]) != _ROLES:
        raise ConfigError(f"roles must be exactly {sorted(_ROLES)}")
    required_models = _ROLES | {"platform_build", "triage_escalation"}
    if set(raw["models"]) != required_models:
        raise ConfigError(f"models must be exactly {sorted(required_models)}")
    models: dict[str, ModelConfig] = {}
    for name, item in raw["models"].items():
        if not isinstance(item, dict) or set(item) != {"model", "reasoning"}:
            raise ConfigError(f"model {name} must contain only model and reasoning")
        if not isinstance(item["model"], str) or not item["model"]:
            raise ConfigError(f"model {name} identifier must be non-empty")
        if item["reasoning"] not in _REASONING:
            raise ConfigError(f"model {name} has unsupported reasoning value")
        models[name] = ModelConfig(item["model"], item["reasoning"])
    gate = raw["project"].get("implementation_gate")
    if gate != {"status": "Ready for Agent", "label": "symphony"}:
        raise ConfigError("implementation gate must remain Ready for Agent + symphony")
    if raw["project"].get("worker_routing") != {
        "standard_label": "agent-standard",
        "deep_label": "agent-deep",
    }:
        raise ConfigError("worker routing must remain agent-standard/agent-deep")
    if raw["project"].get("human_review_status") != "Human Review":
        raise ConfigError("human_review_status must remain Human Review")
    if raw["project"].get("integration_branch") != "v1.3-dev":
        raise ConfigError("integration_branch must remain v1.3-dev")
    concurrency = _positive(raw["symphony"], "max_concurrency")
    if concurrency > 5:
        raise ConfigError("Symphony concurrency may not exceed 5")
    symphony = raw["symphony"]
    if symphony.get("engineering_preview_acknowledged") is not True:
        raise ConfigError(
            "Symphony engineering preview must be explicitly acknowledged"
        )
    for key in (
        "binary_env",
        "default_binary",
        "workflow",
        "deep_workflow",
        "work_mode_workflow",
        "work_mode_deep_workflow",
    ):
        if not isinstance(symphony.get(key), str) or not symphony[key]:
            raise ConfigError(f"symphony.{key} must be non-empty")
    try:
        implementation_backend_dispatch(symphony, "standard")
        implementation_backend_dispatch(symphony, "deep")
    except LifecycleError as exc:
        raise ConfigError(str(exc)) from exc
    for key in (
        "shutdown_grace_seconds",
        "state_port",
        "poll_seconds",
        "state_timeout_seconds",
        "state_startup_grace_seconds",
        "state_stall_grace_seconds",
        "output_limit_bytes",
    ):
        _positive(symphony, key)
    warning_ratio = symphony.get("budget_warning_ratio")
    if type(warning_ratio) not in {int, float} or not 0 < warning_ratio < 1:
        raise ConfigError("symphony.budget_warning_ratio must be between zero and one")
    runtime = raw["runtime"]
    if not isinstance(runtime.get("prefix_env"), str) or not runtime["prefix_env"]:
        raise ConfigError("runtime.prefix_env must be non-empty")
    _positive(runtime, "lock_stale_seconds")
    _positive(runtime, "log_output_limit_bytes")
    return AgentConfig(
        path=source,
        project=dict(raw["project"]),
        runtime=dict(runtime),
        models=models,
        roles={name: _role(name, item) for name, item in raw["roles"].items()},
        symphony=dict(raw["symphony"]),
    )


def validate_model_catalog(config: AgentConfig, catalog: list[dict[str, Any]]) -> None:
    available: dict[str, set[str]] = {}
    for item in catalog:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        efforts = item.get("supportedReasoningEfforts", [])
        available[item["id"]] = {
            entry.get("reasoningEffort")
            for entry in efforts
            if isinstance(entry, dict) and isinstance(entry.get("reasoningEffort"), str)
        }
    for role, selected in config.models.items():
        if selected.model not in available:
            raise ConfigError(
                f"configured model unavailable for {role}: {selected.model}"
            )
        if selected.reasoning not in available[selected.model]:
            raise ConfigError(
                f"configured reasoning unavailable for {role}: "
                f"{selected.model}/{selected.reasoning}"
            )
