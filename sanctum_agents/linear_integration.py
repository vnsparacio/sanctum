"""Qualified Linear metadata and mutation payload construction."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .authority import Role, validate_issue_mutation
from .management import Finding


class LinearMetadataError(ValueError):
    """Linear metadata does not match the reviewed Sanctum contract."""


@dataclass(frozen=True)
class QualifiedLinearMetadata:
    project_id: str
    project_slug: str
    team_id: str
    states: dict[str, str]
    labels: dict[str, str]
    templates: dict[str, str]


@dataclass(frozen=True)
class LinearIssueProposal:
    fingerprint: str
    template: str
    variables: dict[str, Any]


_REQUIRED_STATES = {
    "Triage", "Backlog", "Watch", "Ready for Agent", "In Progress",
    "Human Review", "Rework", "Done", "Canceled",
}
_REQUIRED_LABELS = {
    "tech-debt", "product-discovery", "architecture", "security", "reliability",
    "agent-quality", "research", "documentation", "symphony",
    "Repo Steward", "Product Scout",
}
_REQUIRED_TEMPLATES = {"Engineering Finding", "Product Discovery", "Agent Quality Finding"}


def load_qualified_metadata(path: Path, expected_slug: str) -> QualifiedLinearMetadata:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise LinearMetadataError(f"invalid Linear metadata snapshot: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {"schema_version", "project", "states", "labels", "templates"}:
        raise LinearMetadataError("Linear metadata snapshot shape is invalid")
    project = value["project"]
    if value["schema_version"] != 1 or not isinstance(project, dict) or set(project) != {"id", "slug", "team_id"}:
        raise LinearMetadataError("Linear project metadata is invalid")
    if project["slug"] != expected_slug:
        raise LinearMetadataError("Linear project slug does not match configuration")
    for name, mapping, required in (
        ("states", value["states"], _REQUIRED_STATES),
        ("labels", value["labels"], _REQUIRED_LABELS),
        ("templates", value["templates"], _REQUIRED_TEMPLATES),
    ):
        if not isinstance(mapping, dict) or not required.issubset(mapping):
            raise LinearMetadataError(f"Linear {name} are incomplete")
        if any(not isinstance(key, str) or not isinstance(item, str) or not item for key, item in mapping.items()):
            raise LinearMetadataError(f"Linear {name} contain malformed IDs")
    for key in ("id", "slug", "team_id"):
        if not isinstance(project[key], str) or not project[key]:
            raise LinearMetadataError("Linear project metadata contains malformed IDs")
    return QualifiedLinearMetadata(
        project["id"], project["slug"], project["team_id"],
        dict(value["states"]), dict(value["labels"]), dict(value["templates"]),
    )


def _issue_input(metadata: QualifiedLinearMetadata, title: str, description: str, labels: list[str]) -> dict[str, Any]:
    validate_issue_mutation(Role.REPO_STEWARD, {"state": "Triage", "add_labels": labels})
    if "symphony" in {item.lower() for item in labels}:
        raise LinearMetadataError("management proposal may not add symphony")
    try:
        label_ids = [metadata.labels[item] for item in labels]
    except KeyError as exc:
        raise LinearMetadataError(f"unqualified Linear label: {exc.args[0]}") from exc
    return {
        "input": {
            "teamId": metadata.team_id,
            "projectId": metadata.project_id,
            "stateId": metadata.states["Triage"],
            "title": title,
            "description": description,
            "labelIds": label_ids,
        }
    }


def engineering_finding_proposal(metadata: QualifiedLinearMetadata, finding: Finding, evidence: dict[str, str]) -> LinearIssueProposal:
    if finding.source != "Repo Steward":
        raise LinearMetadataError("engineering finding source must be Repo Steward")
    fingerprint = finding.fingerprint()
    lines = [f"- `{item}`: {evidence[item]}" for item in finding.evidence_ids]
    description = "\n".join([
        "## Engineering Finding", "", finding.summary, "", "## Evidence", *lines, "",
        "## Recommendation", finding.recommendation, "", "Source: Repo Steward", "",
        f"<!-- sanctum-fingerprint:{fingerprint} -->",
    ])
    labels = list(dict.fromkeys([*finding.labels, "Repo Steward"]))
    return LinearIssueProposal(
        fingerprint, "Engineering Finding",
        _issue_input(metadata, finding.title, description, labels),
    )


def product_discovery_proposal(
    metadata: QualifiedLinearMetadata,
    finding: Any,
    sources: dict[str, Any],
) -> LinearIssueProposal:
    if finding.source != "Product Scout":
        raise LinearMetadataError("product discovery source must be Product Scout")
    fingerprint = finding.fingerprint(sources)
    citations = [f"- [{sources[item].title}]({sources[item].url})" for item in finding.source_ids]
    description = "\n".join([
        "## Product Discovery", "", finding.summary, "", "## Sanctum connection",
        finding.sanctum_connection, "", "## Sources", *citations, "", "## Recommendation",
        finding.recommendation, "", "Source: Product Scout", "",
        f"<!-- sanctum-fingerprint:{fingerprint} -->",
    ])
    labels = list(dict.fromkeys([*finding.labels, "Product Scout"]))
    return LinearIssueProposal(
        fingerprint, "Product Discovery",
        _issue_input(metadata, finding.title, description, labels),
    )


def triage_update_variables(
    metadata: QualifiedLinearMetadata,
    issue_id: str,
    state: str,
) -> dict[str, Any]:
    validate_issue_mutation(Role.TRIAGE, {"state": state})
    if state not in {"Backlog", "Watch", "Canceled"}:
        raise LinearMetadataError("triage writer only supports reviewed management states")
    return {"id": issue_id, "input": {"stateId": metadata.states[state]}}


ISSUE_CREATE_MUTATION = """
mutation SanctumIssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) { success issue { id identifier url } }
}
""".strip()

ISSUE_UPDATE_MUTATION = """
mutation SanctumIssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) { success issue { id identifier state { name } } }
}
""".strip()

DUPLICATE_CANDIDATES_QUERY = """
query SanctumDuplicateCandidates($projectId: String!) {
  project(id: $projectId) {
    issues(first: 100) {
      nodes { id identifier title description url state { name } }
    }
  }
}
""".strip()

ISSUE_RELATION_CREATE_MUTATION = """
mutation SanctumIssueRelationCreate($input: IssueRelationCreateInput!) {
  issueRelationCreate(input: $input) { success issueRelation { id } }
}
""".strip()


class LinearWriter:
    """Narrow idempotent writer over a qualified metadata snapshot."""

    def __init__(self, client: Any, metadata: QualifiedLinearMetadata):
        self.client = client
        self.metadata = metadata

    def _candidates(self) -> list[dict[str, Any]]:
        data = self.client.query(
            DUPLICATE_CANDIDATES_QUERY, {"projectId": self.metadata.project_id}
        )
        project = data.get("project")
        issues = project.get("issues") if isinstance(project, dict) else None
        nodes = issues.get("nodes") if isinstance(issues, dict) else None
        if not isinstance(nodes, list):
            raise LinearMetadataError("Linear duplicate candidate response is malformed")
        return [item for item in nodes if isinstance(item, dict)]

    def create_proposals(self, proposals: list[LinearIssueProposal], max_created: int) -> list[dict[str, Any]]:
        if type(max_created) is not int or max_created < 0:
            raise ValueError("max_created must be non-negative")
        candidates = self._candidates()
        outcomes: list[dict[str, Any]] = []
        created = 0
        for proposal in proposals:
            marker = f"sanctum-fingerprint:{proposal.fingerprint}"
            duplicate = next((item for item in candidates if marker in str(item.get("description", ""))), None)
            if duplicate is None:
                title = proposal.variables["input"]["title"].strip().casefold()
                duplicate = next((item for item in candidates if str(item.get("title", "")).strip().casefold() == title), None)
            if duplicate is not None:
                outcomes.append({"status": "duplicate", "issue": duplicate})
                continue
            if created >= max_created:
                outcomes.append({"status": "creation_cap", "fingerprint": proposal.fingerprint})
                continue
            data = self.client.query(ISSUE_CREATE_MUTATION, proposal.variables)
            result = data.get("issueCreate")
            if not isinstance(result, dict) or result.get("success") is not True or not isinstance(result.get("issue"), dict):
                raise LinearMetadataError("Linear issue creation response is malformed")
            issue = result["issue"]
            candidates.append({**issue, "title": proposal.variables["input"]["title"], "description": proposal.variables["input"]["description"]})
            outcomes.append({"status": "created", "issue": issue})
            created += 1
        return outcomes

    def apply_triage(self, issue_id: str, state: str, duplicate_of: str | None = None) -> list[dict[str, Any]]:
        variables = triage_update_variables(self.metadata, issue_id, state)
        update = self.client.query(ISSUE_UPDATE_MUTATION, variables)
        result = update.get("issueUpdate")
        if not isinstance(result, dict) or result.get("success") is not True:
            raise LinearMetadataError("Linear issue update response is malformed")
        outcomes = [{"status": "updated", "issue": result.get("issue")}]
        if duplicate_of is not None:
            relation = self.client.query(ISSUE_RELATION_CREATE_MUTATION, {
                "input": {"issueId": issue_id, "relatedIssueId": duplicate_of, "type": "duplicate"}
            })
            relation_result = relation.get("issueRelationCreate")
            if not isinstance(relation_result, dict) or relation_result.get("success") is not True:
                raise LinearMetadataError("Linear duplicate relation response is malformed")
            outcomes.append({"status": "linked_duplicate", "relation": relation_result.get("issueRelation")})
        return outcomes
