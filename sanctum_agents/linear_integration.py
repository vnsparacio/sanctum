"""Qualified Linear metadata and mutation payload construction."""

from __future__ import annotations

import json
from dataclasses import dataclass
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
    "Triage",
    "Backlog",
    "Watch",
    "Ready for Agent",
    "In Progress",
    "Human Review",
    "Rework",
    "Done",
    "Canceled",
}
_REQUIRED_LABELS = {
    "tech-debt",
    "product-discovery",
    "architecture",
    "security",
    "reliability",
    "agent-quality",
    "research",
    "documentation",
    "symphony",
    "Repo Steward",
    "Product Scout",
}
_REQUIRED_TEMPLATES = {
    "Engineering Finding",
    "Product Discovery",
    "Agent Quality Finding",
}

LINEAR_PROJECT_METADATA_QUERY = """
query SanctumProjectMetadata($slug: String!) {
  project(id: $slug) {
    id
    name
    slugId
    url
    teams {
      nodes { id name }
      pageInfo { hasNextPage }
    }
  }
}
""".strip()

LINEAR_TEAM_METADATA_QUERY = """
query SanctumTeamMetadata($id: String!) {
  team(id: $id) {
    id
    name
    states {
      nodes { id name }
      pageInfo { hasNextPage }
    }
    labels {
      nodes { id name parent { id name } }
      pageInfo { hasNextPage }
    }
    templates {
      nodes { id name type }
      pageInfo { hasNextPage }
    }
  }
}
""".strip()


def _connection_nodes(parent: Any, key: str) -> list[dict[str, Any]]:
    connection = parent.get(key) if isinstance(parent, dict) else None
    nodes = connection.get("nodes") if isinstance(connection, dict) else None
    page_info = connection.get("pageInfo") if isinstance(connection, dict) else None
    if (
        not isinstance(nodes, list)
        or any(not isinstance(item, dict) for item in nodes)
        or not isinstance(page_info, dict)
        or not isinstance(page_info.get("hasNextPage"), bool)
    ):
        raise LinearMetadataError(f"Linear {key} response is malformed")
    if page_info["hasNextPage"]:
        raise LinearMetadataError(f"Linear {key} metadata requires pagination")
    return nodes


def _required_mapping(
    nodes: list[dict[str, Any]], required: set[str], kind: str
) -> dict[str, str]:
    matches: dict[str, list[str]] = {name: [] for name in required}
    for item in nodes:
        name = item.get("name")
        identifier = item.get("id")
        if (
            not isinstance(name, str)
            or not isinstance(identifier, str)
            or not identifier
        ):
            raise LinearMetadataError(f"Linear {kind} response is malformed")
        if name in matches:
            matches[name].append(identifier)
    missing = sorted(name for name, identifiers in matches.items() if not identifiers)
    duplicates = sorted(
        name for name, identifiers in matches.items() if len(identifiers) > 1
    )
    if missing:
        raise LinearMetadataError(
            f"Linear {kind} missing required names: {', '.join(missing)}"
        )
    if duplicates:
        raise LinearMetadataError(
            f"Linear {kind} contain duplicate required names: {', '.join(duplicates)}"
        )
    return {name: matches[name][0] for name in sorted(required)}


def capture_qualified_metadata(
    client: Any, project_slug: str, path: Path
) -> QualifiedLinearMetadata:
    """Capture and validate the exact read-only Linear metadata contract."""
    project_data = client.query(LINEAR_PROJECT_METADATA_QUERY, {"slug": project_slug})
    project = project_data.get("project")
    slug_id = project.get("slugId") if isinstance(project, dict) else None
    project_url = project.get("url") if isinstance(project, dict) else None
    if (
        not isinstance(project, dict)
        or not isinstance(project.get("id"), str)
        or not project["id"]
        or not isinstance(project.get("name"), str)
        or not project["name"]
        or not isinstance(slug_id, str)
        or not slug_id
        or not project_slug.endswith(f"-{slug_id}")
        or not isinstance(project_url, str)
        or not project_url.startswith("https://linear.app/")
        or not project_url.rstrip("/").endswith(f"/project/{project_slug}")
    ):
        raise LinearMetadataError("Linear project metadata is invalid")
    teams = _connection_nodes(project, "teams")
    if len(teams) != 1:
        raise LinearMetadataError("Linear project must have exactly one owning team")
    team_id = teams[0].get("id")
    if not isinstance(team_id, str) or not team_id:
        raise LinearMetadataError("Linear owning team metadata is invalid")

    team_data = client.query(LINEAR_TEAM_METADATA_QUERY, {"id": team_id})
    team = team_data.get("team")
    if (
        not isinstance(team, dict)
        or team.get("id") != team_id
        or not isinstance(team.get("name"), str)
        or not team["name"]
    ):
        raise LinearMetadataError("Linear owning team metadata is invalid")
    states = _connection_nodes(team, "states")
    labels = _connection_nodes(team, "labels")
    templates = _connection_nodes(team, "templates")

    state_mapping = _required_mapping(states, _REQUIRED_STATES, "states")
    label_mapping = _required_mapping(labels, _REQUIRED_LABELS, "labels")
    template_mapping = _required_mapping(templates, _REQUIRED_TEMPLATES, "templates")

    source_parents: list[str] = []
    for item in labels:
        if item.get("name") not in {"Repo Steward", "Product Scout"}:
            continue
        parent = item.get("parent")
        if (
            not isinstance(parent, dict)
            or parent.get("name") != "source"
            or not isinstance(parent.get("id"), str)
            or not parent["id"]
        ):
            raise LinearMetadataError(
                "Linear management labels must belong to the source group"
            )
        source_parents.append(parent["id"])
    if len(set(source_parents)) != 1:
        raise LinearMetadataError(
            "Linear management labels use different source groups"
        )
    for item in templates:
        if item.get("name") in _REQUIRED_TEMPLATES and item.get("type") != "issue":
            raise LinearMetadataError(
                "Linear required templates must be issue templates"
            )

    payload = {
        "schema_version": 1,
        "project": {"id": project["id"], "slug": project_slug, "team_id": team_id},
        "states": state_mapping,
        "labels": label_mapping,
        "templates": template_mapping,
    }
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)
    return load_qualified_metadata(path, project_slug)


def load_qualified_metadata(path: Path, expected_slug: str) -> QualifiedLinearMetadata:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise LinearMetadataError(f"invalid Linear metadata snapshot: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "project",
        "states",
        "labels",
        "templates",
    }:
        raise LinearMetadataError("Linear metadata snapshot shape is invalid")
    project = value["project"]
    if (
        value["schema_version"] != 1
        or not isinstance(project, dict)
        or set(project) != {"id", "slug", "team_id"}
    ):
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
        if any(
            not isinstance(key, str) or not isinstance(item, str) or not item
            for key, item in mapping.items()
        ):
            raise LinearMetadataError(f"Linear {name} contain malformed IDs")
    for key in ("id", "slug", "team_id"):
        if not isinstance(project[key], str) or not project[key]:
            raise LinearMetadataError("Linear project metadata contains malformed IDs")
    return QualifiedLinearMetadata(
        project["id"],
        project["slug"],
        project["team_id"],
        dict(value["states"]),
        dict(value["labels"]),
        dict(value["templates"]),
    )


def _issue_input(
    metadata: QualifiedLinearMetadata, title: str, description: str, labels: list[str]
) -> dict[str, Any]:
    validate_issue_mutation(
        Role.REPO_STEWARD, {"state": "Triage", "add_labels": labels}
    )
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


def engineering_finding_proposal(
    metadata: QualifiedLinearMetadata, finding: Finding, evidence: dict[str, str]
) -> LinearIssueProposal:
    if finding.source != "Repo Steward":
        raise LinearMetadataError("engineering finding source must be Repo Steward")
    fingerprint = finding.fingerprint()
    lines = [f"- `{item}`: {evidence[item]}" for item in finding.evidence_ids]
    description = "\n".join(
        [
            "## Engineering Finding",
            "",
            finding.summary,
            "",
            "## Evidence",
            *lines,
            "",
            "## Recommendation",
            finding.recommendation,
            "",
            "Source: Repo Steward",
            "",
            f"<!-- sanctum-fingerprint:{fingerprint} -->",
        ]
    )
    labels = list(dict.fromkeys([*finding.labels, "Repo Steward"]))
    return LinearIssueProposal(
        fingerprint,
        "Engineering Finding",
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
    citations = [
        f"- [{sources[item].title}]({sources[item].url})" for item in finding.source_ids
    ]
    description = "\n".join(
        [
            "## Product Discovery",
            "",
            finding.summary,
            "",
            "## Sanctum connection",
            finding.sanctum_connection,
            "",
            "## Sources",
            *citations,
            "",
            "## Recommendation",
            finding.recommendation,
            "",
            "Source: Product Scout",
            "",
            f"<!-- sanctum-fingerprint:{fingerprint} -->",
        ]
    )
    labels = list(dict.fromkeys([*finding.labels, "Product Scout"]))
    return LinearIssueProposal(
        fingerprint,
        "Product Discovery",
        _issue_input(metadata, finding.title, description, labels),
    )


def triage_update_variables(
    metadata: QualifiedLinearMetadata,
    issue_id: str,
    state: str,
) -> dict[str, Any]:
    validate_issue_mutation(Role.TRIAGE, {"state": state})
    if state not in {"Backlog", "Watch", "Canceled"}:
        raise LinearMetadataError(
            "triage writer only supports reviewed management states"
        )
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
            raise LinearMetadataError(
                "Linear duplicate candidate response is malformed"
            )
        return [item for item in nodes if isinstance(item, dict)]

    def create_proposals(
        self, proposals: list[LinearIssueProposal], max_created: int
    ) -> list[dict[str, Any]]:
        if type(max_created) is not int or max_created < 0:
            raise ValueError("max_created must be non-negative")
        candidates = self._candidates()
        outcomes: list[dict[str, Any]] = []
        created = 0
        for proposal in proposals:
            marker = f"sanctum-fingerprint:{proposal.fingerprint}"
            duplicate = next(
                (
                    item
                    for item in candidates
                    if marker in str(item.get("description", ""))
                ),
                None,
            )
            if duplicate is None:
                title = proposal.variables["input"]["title"].strip().casefold()
                duplicate = next(
                    (
                        item
                        for item in candidates
                        if str(item.get("title", "")).strip().casefold() == title
                    ),
                    None,
                )
            if duplicate is not None:
                outcomes.append({"status": "duplicate", "issue": duplicate})
                continue
            if created >= max_created:
                outcomes.append(
                    {"status": "creation_cap", "fingerprint": proposal.fingerprint}
                )
                continue
            data = self.client.query(ISSUE_CREATE_MUTATION, proposal.variables)
            result = data.get("issueCreate")
            if (
                not isinstance(result, dict)
                or result.get("success") is not True
                or not isinstance(result.get("issue"), dict)
            ):
                raise LinearMetadataError("Linear issue creation response is malformed")
            issue = result["issue"]
            candidates.append(
                {
                    **issue,
                    "title": proposal.variables["input"]["title"],
                    "description": proposal.variables["input"]["description"],
                }
            )
            outcomes.append({"status": "created", "issue": issue})
            created += 1
        return outcomes

    def apply_triage(
        self, issue_id: str, state: str, duplicate_of: str | None = None
    ) -> list[dict[str, Any]]:
        variables = triage_update_variables(self.metadata, issue_id, state)
        update = self.client.query(ISSUE_UPDATE_MUTATION, variables)
        result = update.get("issueUpdate")
        if not isinstance(result, dict) or result.get("success") is not True:
            raise LinearMetadataError("Linear issue update response is malformed")
        outcomes = [{"status": "updated", "issue": result.get("issue")}]
        if duplicate_of is not None:
            relation = self.client.query(
                ISSUE_RELATION_CREATE_MUTATION,
                {
                    "input": {
                        "issueId": issue_id,
                        "relatedIssueId": duplicate_of,
                        "type": "duplicate",
                    }
                },
            )
            relation_result = relation.get("issueRelationCreate")
            if (
                not isinstance(relation_result, dict)
                or relation_result.get("success") is not True
            ):
                raise LinearMetadataError(
                    "Linear duplicate relation response is malformed"
                )
            outcomes.append(
                {
                    "status": "linked_duplicate",
                    "relation": relation_result.get("issueRelation"),
                }
            )
        return outcomes
