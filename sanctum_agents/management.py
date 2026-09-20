"""Shared finding schema, deduplication, and shadow artifact handling."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class MalformedModelOutput(ValueError):
    """Model output failed host validation."""


@dataclass(frozen=True)
class Evidence:
    id: str
    kind: str
    summary: str
    location: str | None = None


@dataclass(frozen=True)
class Finding:
    title: str
    summary: str
    severity: str
    recommendation: str
    evidence_ids: tuple[str, ...]
    labels: tuple[str, ...]
    source: str

    def fingerprint(self) -> str:
        canonical = json.dumps(
            {
                "title": " ".join(self.title.lower().split()),
                "evidence_ids": sorted(self.evidence_ids),
                "source": self.source,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


_SEVERITIES = {"low", "medium", "high"}
_RECOMMENDATIONS = {"Investigate", "Watch", "Ignore"}
_LABELS = {
    "tech-debt",
    "architecture",
    "security",
    "reliability",
    "agent-quality",
    "documentation",
    "research",
    "product-discovery",
}


def parse_findings(
    payload: dict[str, Any],
    evidence: list[Evidence],
    *,
    source: str,
    max_items: int,
) -> list[Finding]:
    if set(payload) != {"findings"} or not isinstance(payload["findings"], list):
        raise MalformedModelOutput("response must contain only a findings array")
    if len(payload["findings"]) > max_items:
        raise MalformedModelOutput("response exceeded the finding limit")
    known = {item.id for item in evidence}
    findings: list[Finding] = []
    for item in payload["findings"]:
        required = {
            "title",
            "summary",
            "severity",
            "recommendation",
            "evidence_ids",
            "labels",
        }
        if not isinstance(item, dict) or set(item) != required:
            raise MalformedModelOutput("finding fields are malformed")
        if not isinstance(item["title"], str) or not (8 <= len(item["title"]) <= 140):
            raise MalformedModelOutput("finding title is malformed")
        if not isinstance(item["summary"], str) or not (
            20 <= len(item["summary"]) <= 2000
        ):
            raise MalformedModelOutput("finding summary is malformed")
        if (
            item["severity"] not in _SEVERITIES
            or item["recommendation"] not in _RECOMMENDATIONS
        ):
            raise MalformedModelOutput("finding classification is malformed")
        evidence_ids = item["evidence_ids"]
        labels = item["labels"]
        if (
            not isinstance(evidence_ids, list)
            or not evidence_ids
            or len(evidence_ids) != len(set(evidence_ids))
            or any(value not in known for value in evidence_ids)
        ):
            raise MalformedModelOutput(
                "finding references unknown or duplicate evidence"
            )
        if (
            not isinstance(labels, list)
            or not labels
            or len(labels) != len(set(labels))
            or any(value not in _LABELS for value in labels)
            or "symphony" in labels
        ):
            raise MalformedModelOutput("finding labels are malformed")
        findings.append(
            Finding(
                title=item["title"].strip(),
                summary=item["summary"].strip(),
                severity=item["severity"],
                recommendation=item["recommendation"],
                evidence_ids=tuple(evidence_ids),
                labels=tuple(labels),
                source=source,
            )
        )
    return findings


class RoleState:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": 1,
                "last_successful_commit": None,
                "fingerprints": [],
            }
        try:
            value = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid role state: {exc}") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != 1
            or not isinstance(value.get("fingerprints"), list)
        ):
            raise RuntimeError("invalid role state schema")
        return value

    def save(self, *, commit: str | None, fingerprints: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "last_successful_commit": commit,
                    "fingerprints": sorted(set(fingerprints))[-5000:],
                },
                sort_keys=True,
            )
            + "\n"
        )
        temporary.chmod(0o600)
        temporary.replace(self.path)


def suppress_duplicates(
    findings: list[Finding], prior: list[str]
) -> tuple[list[Finding], list[str]]:
    known = set(prior)
    accepted: list[Finding] = []
    suppressed: list[str] = []
    for finding in findings:
        fingerprint = finding.fingerprint()
        if fingerprint in known:
            suppressed.append(fingerprint)
            continue
        known.add(fingerprint)
        accepted.append(finding)
    return accepted, suppressed


def shadow_document(
    run_id: str,
    role: str,
    commit: str | None,
    findings: list[Finding],
    evidence: list[Evidence],
    *,
    mode: str = "shadow",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "role": role,
        "mode": mode,
        "repository_commit": commit,
        "linear_writes": 0,
        "findings": [
            {**asdict(item), "fingerprint": item.fingerprint()} for item in findings
        ],
        "evidence": [asdict(item) for item in evidence],
    }
