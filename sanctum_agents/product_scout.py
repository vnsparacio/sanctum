"""Bounded external technology research for Product Discovery proposals."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .authority import Role, assert_repository_unchanged
from .config import AgentConfig
from .integrations import repository_status
from .linear_integration import product_discovery_proposal
from .management import MalformedModelOutput, RoleState
from .reasoner import CodexReasoner
from .runtime import Budget, ExclusiveRoleLock, JsonlRunLog, RunMode, ensure_private_prefix, new_run_id


_KINDS = {"primary", "community", "paper", "repository", "release_notes", "security_research"}
_CREDIBLE = _KINDS - {"community"}
_LABELS = {"product-discovery", "architecture", "security", "reliability", "agent-quality", "research", "documentation"}
_RECOMMENDATIONS = {"Investigate", "Watch", "Ignore"}


@dataclass(frozen=True)
class ResearchSource:
    id: str
    url: str
    title: str
    published_at: str | None
    kind: str
    summary: str


@dataclass(frozen=True)
class ProductDiscovery:
    title: str
    summary: str
    sanctum_connection: str
    recommendation: str
    source_ids: tuple[str, ...]
    labels: tuple[str, ...]
    source: str = "Product Scout"

    def fingerprint(self, sources: dict[str, ResearchSource]) -> str:
        value = {
            "title": " ".join(self.title.lower().split()),
            "urls": sorted(sources[item].url for item in self.source_ids),
            "source": self.source,
        }
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _bounded_text(value: Any, low: int, high: int, name: str) -> str:
    if not isinstance(value, str) or not (low <= len(value.strip()) <= high):
        raise MalformedModelOutput(f"{name} is malformed")
    return value.strip()


def _public_https_url(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 2000:
        raise MalformedModelOutput("source URL is malformed")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise MalformedModelOutput("source URL must be public HTTPS")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".local"):
        raise MalformedModelOutput("source URL must be public HTTPS")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise MalformedModelOutput("source URL must be public HTTPS")
    return value


def parse_research(payload: dict[str, Any], *, max_sources: int, max_items: int) -> tuple[list[ResearchSource], list[ProductDiscovery]]:
    if not isinstance(payload, dict) or set(payload) != {"sources", "findings"}:
        raise MalformedModelOutput("response must contain only sources and findings")
    if not isinstance(payload["sources"], list) or len(payload["sources"]) > max_sources:
        raise MalformedModelOutput("response exceeded the source limit")
    sources: list[ResearchSource] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    required_source = {"id", "url", "title", "published_at", "kind", "summary"}
    for raw in payload["sources"]:
        if not isinstance(raw, dict) or set(raw) != required_source:
            raise MalformedModelOutput("source fields are malformed")
        source_id = _bounded_text(raw["id"], 1, 80, "source id")
        url = _public_https_url(raw["url"])
        if source_id in seen_ids or url in seen_urls or raw["kind"] not in _KINDS:
            raise MalformedModelOutput("source identity or classification is malformed")
        published = raw["published_at"]
        if published is not None and (not isinstance(published, str) or len(published) > 40):
            raise MalformedModelOutput("source published_at is malformed")
        seen_ids.add(source_id)
        seen_urls.add(url)
        sources.append(ResearchSource(
            source_id,
            url,
            _bounded_text(raw["title"], 4, 300, "source title"),
            published,
            raw["kind"],
            _bounded_text(raw["summary"], 20, 1200, "source summary"),
        ))
    if not isinstance(payload["findings"], list) or len(payload["findings"]) > max_items:
        raise MalformedModelOutput("response exceeded the finding limit")
    by_id = {item.id: item for item in sources}
    discoveries: list[ProductDiscovery] = []
    required_finding = {"title", "summary", "sanctum_connection", "recommendation", "source_ids", "labels"}
    for raw in payload["findings"]:
        if not isinstance(raw, dict) or set(raw) != required_finding:
            raise MalformedModelOutput("discovery fields are malformed")
        source_ids = raw["source_ids"]
        labels = raw["labels"]
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or len(source_ids) != len(set(source_ids))
            or any(item not in by_id for item in source_ids)
            or not any(by_id[item].kind in _CREDIBLE for item in source_ids)
        ):
            raise MalformedModelOutput("discovery lacks unique credible source evidence")
        if (
            not isinstance(labels, list)
            or not labels
            or len(labels) != len(set(labels))
            or any(item not in _LABELS for item in labels)
            or "symphony" in labels
            or "product-discovery" not in labels
        ):
            raise MalformedModelOutput("discovery labels are malformed")
        if raw["recommendation"] not in _RECOMMENDATIONS:
            raise MalformedModelOutput("discovery recommendation is malformed")
        discoveries.append(ProductDiscovery(
            _bounded_text(raw["title"], 8, 140, "discovery title"),
            _bounded_text(raw["summary"], 20, 1600, "discovery summary"),
            _bounded_text(raw["sanctum_connection"], 20, 1200, "Sanctum connection"),
            raw["recommendation"],
            tuple(source_ids),
            tuple(labels),
        ))
    return sources, discoveries


def prompt_for(max_sources: int, max_items: int) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    return (
        f"You are Sanctum's Product Scout. Today is {today}. Use native web search only; do not run shell "
        f"commands or spawn agents. Research at most {max_sources} sources and return at most {max_items} "
        "high-signal discoveries. Check recent Reddit and Hacker News discussions when useful, then verify "
        "claims with primary sources such as GitHub, Hugging Face, OpenAI, Anthropic, Qwen, MLX, llama.cpp, "
        "vLLM, papers, release notes, and security research. Favor concrete releases, reusable code, failure "
        "reports, local/private AI, inference, and agent orchestration over AI-news summaries. Every finding "
        "must cite at least one non-community source and explain a specific connection to Sanctum's private, "
        "owner-authorized architecture. Do not claim a Linear duplicate search occurred. Do not add symphony, "
        "authorize or recommend automatic implementation, modify code, or invent evidence. Every finding's "
        "labels array must include product-discovery. Empty arrays are valid."
    )


def run_product_scout(
    config: AgentConfig,
    repository: Path,
    mode: RunMode,
    *,
    reasoner: CodexReasoner | None = None,
    fixture_payload: dict[str, Any] | None = None,
    linear_writer: Any | None = None,
) -> dict[str, Any]:
    role_name = Role.PRODUCT_SCOUT.value
    role = config.roles[role_name]
    if mode is RunMode.LIVE and not role.write_enabled:
        raise RuntimeError("Product Scout live writes are disabled until shadow acceptance")
    prefix = config.runtime_prefix()
    ensure_private_prefix(prefix)
    run_id = new_run_id(role_name)
    log = JsonlRunLog(prefix / "logs" / role_name / f"{run_id}.jsonl", run_id, role_name, mode)
    lock = ExclusiveRoleLock(prefix / "locks" / f"{role_name}.lock", config.runtime["lock_stale_seconds"])
    state_store = RoleState(prefix / "state" / f"{role_name}.json")
    before = repository_status(repository)
    with lock.acquired_for(run_id):
        model = config.model_for(role_name)
        log.emit("started", model=model.model, reasoning=model.reasoning)
        state = state_store.load()
        budget = Budget(role.wall_clock_seconds, role.max_items, role.max_sources, role.max_retries, role.max_turns, role.max_tokens)
        if fixture_payload is None:
            reasoner = reasoner or CodexReasoner()
            cwd = prefix / "state" / "reasoner" / role_name
            cwd.mkdir(parents=True, exist_ok=True, mode=0o700)
            raw, process = reasoner.run(
                prompt_for(role.max_sources, role.max_items),
                model,
                repository / "config" / "schemas" / "product-discoveries.schema.json",
                cwd,
                budget,
                config.runtime["log_output_limit_bytes"],
                enable_search=True,
            )
            log.emit("reasoner_completed", runtime_seconds=process.runtime_seconds, counters=process.counters)
        else:
            raw = fixture_payload
        sources, findings = parse_research(raw, max_sources=role.max_sources, max_items=role.max_items)
        budget.consume("sources", len(sources))
        budget.consume("items", len(findings))
        prior = set(state.get("fingerprints", []))
        by_id = {item.id: item for item in sources}
        accepted = [item for item in findings if item.fingerprint(by_id) not in prior]
        suppressed = len(findings) - len(accepted)
        writes: list[dict[str, Any]] = []
        if mode is RunMode.LIVE:
            if linear_writer is None:
                raise RuntimeError("Product Scout Linear writer is unavailable")
            proposals = [
                product_discovery_proposal(linear_writer.metadata, item, by_id)
                for item in accepted
            ]
            writes = linear_writer.create_proposals(proposals, role.max_issues_created)
        after = repository_status(repository)
        assert_repository_unchanged(before, after, Role.PRODUCT_SCOUT)
        artifact = {
            "schema_version": 1,
            "run_id": run_id,
            "role": role_name,
            "mode": mode.value,
            "linear_writes": sum(item["status"] == "created" for item in writes),
            "linear_outcomes": writes,
            "sources": [asdict(item) for item in sources],
            "findings": [{**asdict(item), "fingerprint": item.fingerprint(by_id)} for item in accepted],
            "duplicates_suppressed": suppressed,
        }
        output = prefix / ("shadow" if mode is not RunMode.LIVE else "runs") / f"{run_id}.json"
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
        output.chmod(0o600)
        state_store.save(
            commit=datetime.now(timezone.utc).isoformat(),
            fingerprints=list(prior) + [item.fingerprint(by_id) for item in accepted],
        )
        log.emit("completed", source_count=len(sources), finding_count=len(accepted), duplicates_suppressed=suppressed, artifact=str(output))
        return {**artifact, "artifact_path": str(output)}
