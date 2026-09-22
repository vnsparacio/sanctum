"""Issue-bound Linear evidence operations for host-owned Work Mode tasks."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit


class WorkLinearError(RuntimeError):
    """A Work Mode Linear request escaped or violated its fixed issue scope."""


class LinearClient(Protocol):
    def query(
        self, query: str, variables: dict[str, Any] | None = None, timeout: float = 15
    ) -> dict[str, Any]: ...


WORKPAD_HEADING = "## Codex Workpad"
_UUID = re.compile(
    r"[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}"
)
_ISSUE_IDENTIFIER = re.compile(r"[A-Z][A-Z0-9]*-[1-9][0-9]*")
_REPOSITORY = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})/[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,99})"
)
_PR_PATH = re.compile(r"/([^/]+/[^/]+)/pull/([1-9][0-9]*)")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

ISSUE_QUERY = """
query WorkModeIssue($id: String!) {
  issue(id: $id) {
    id identifier title url description
    state { id name type }
    project { id name }
    parent { id identifier title }
    children(first: 100) {
      nodes { id identifier title }
      pageInfo { hasNextPage endCursor }
    }
    relations(first: 100) {
      nodes { id type relatedIssue { id identifier title } }
      pageInfo { hasNextPage endCursor }
    }
    inverseRelations(first: 100) {
      nodes { id type issue { id identifier title } }
      pageInfo { hasNextPage endCursor }
    }
    comments(first: 100) {
      nodes { id body createdAt updatedAt }
      pageInfo { hasNextPage endCursor }
    }
    attachments(first: 100) {
      nodes { id title url sourceType }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

CREATE_COMMENT = """
mutation CreateWorkModeWorkpad($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) {
    success
    comment { id body }
  }
}
"""

UPDATE_COMMENT = """
mutation UpdateWorkModeWorkpad($id: String!, $body: String!) {
  commentUpdate(id: $id, input: { body: $body }) {
    success
    comment { id body }
  }
}
"""

ATTACH_PULL_REQUEST = """
mutation AttachWorkModePullRequest($issueId: String!, $url: String!, $title: String!) {
  attachmentLinkGitHubPR(
    issueId: $issueId
    url: $url
    title: $title
    linkKind: links
  ) {
    success
    attachment { id title url }
  }
}
"""


@dataclass(frozen=True)
class WorkIssueScope:
    """Host-selected immutable identity for one Work Mode task issue."""

    issue_id: str
    identifier: str
    project_id: str
    repository: str

    def __post_init__(self) -> None:
        if not _UUID.fullmatch(self.issue_id):
            raise WorkLinearError("invalid scoped Linear issue ID")
        if not _ISSUE_IDENTIFIER.fullmatch(self.identifier):
            raise WorkLinearError("invalid scoped Linear issue identifier")
        if not _UUID.fullmatch(self.project_id):
            raise WorkLinearError("invalid scoped Linear project ID")
        if not _REPOSITORY.fullmatch(self.repository):
            raise WorkLinearError("invalid scoped repository identity")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkLinearError(f"Linear {label} response is malformed")
    return value


def _nodes(value: Any, label: str) -> list[Mapping[str, Any]]:
    connection = _mapping(value, label)
    nodes = connection.get("nodes")
    if not isinstance(nodes, list) or any(
        not isinstance(item, Mapping) for item in nodes
    ):
        raise WorkLinearError(f"Linear {label} response is malformed")
    page_info = connection.get("pageInfo")
    if isinstance(page_info, Mapping) and page_info.get("hasNextPage") is not False:
        raise WorkLinearError(f"Linear {label} response requires pagination")
    return nodes


def _text(value: Any, label: str, *, minimum: int = 1, maximum: int) -> str:
    if (
        type(value) is not str
        or not minimum <= len(value) <= maximum
        or value.strip() != value
        or _CONTROL.search(value)
    ):
        raise WorkLinearError(f"invalid {label}")
    return value


class WorkLinearOperations:
    """Expose only evidence operations for one immutable issue and repository."""

    def __init__(self, client: LinearClient, scope: WorkIssueScope) -> None:
        if not callable(getattr(client, "query", None)):
            raise WorkLinearError("Linear client is unavailable")
        if not isinstance(scope, WorkIssueScope):
            raise WorkLinearError("Work Mode issue scope is unavailable")
        self._client = client
        self.scope = scope

    def _issue(self) -> Mapping[str, Any]:
        data = _mapping(
            self._client.query(ISSUE_QUERY, {"id": self.scope.issue_id}), "query"
        )
        issue = _mapping(data.get("issue"), "issue")
        project = _mapping(issue.get("project"), "issue project")
        if (
            issue.get("id") != self.scope.issue_id
            or issue.get("identifier") != self.scope.identifier
            or project.get("id") != self.scope.project_id
        ):
            raise WorkLinearError("Linear issue does not match the fixed task scope")
        comments = _nodes(issue.get("comments"), "issue comments")
        attachments = _nodes(issue.get("attachments"), "issue attachments")
        children = _nodes(issue.get("children"), "issue children")
        relations = _nodes(issue.get("relations"), "issue relations")
        inverse_relations = _nodes(
            issue.get("inverseRelations"), "issue inverse relations"
        )
        # Copy provider-owned values so callers cannot mutate a fake client's cache.
        return {
            **copy.deepcopy(dict(issue)),
            "project": copy.deepcopy(dict(project)),
            "children": {"nodes": copy.deepcopy(children)},
            "relations": {"nodes": copy.deepcopy(relations)},
            "inverseRelations": {"nodes": copy.deepcopy(inverse_relations)},
            "comments": {"nodes": copy.deepcopy(comments)},
            "attachments": {"nodes": copy.deepcopy(attachments)},
        }

    def fetch_issue(self) -> Mapping[str, Any]:
        """Fetch only the host-bound issue, including acceptance and relation data."""

        return self._issue()

    @staticmethod
    def _workpad(issue: Mapping[str, Any]) -> Mapping[str, Any] | None:
        comments = _nodes(issue.get("comments"), "issue comments")
        workpads = [
            item
            for item in comments
            if type(item.get("body")) is str
            and item["body"].splitlines()[:1] == [WORKPAD_HEADING]
        ]
        if len(workpads) > 1:
            raise WorkLinearError("scoped issue has multiple active Codex Workpads")
        return workpads[0] if workpads else None

    def _workpad_matches(self, body: str) -> Mapping[str, Any] | None:
        issue = self._issue()
        workpad = self._workpad(issue)
        return workpad if workpad is not None and workpad.get("body") == body else None

    def upsert_workpad(self, body: Any) -> Mapping[str, Any]:
        """Create, find, or update the one Workpad; exact replay is read-only."""

        checked = _text(body, "Workpad body", maximum=32_000)
        if checked.splitlines()[:1] != [WORKPAD_HEADING]:
            raise WorkLinearError(f"Workpad must begin with {WORKPAD_HEADING!r}")
        issue = self._issue()
        workpad = self._workpad(issue)
        if workpad is not None and workpad.get("body") == checked:
            return {"status": "unchanged", "comment_id": workpad.get("id")}
        if workpad is None:
            query = CREATE_COMMENT
            variables = {"issueId": self.scope.issue_id, "body": checked}
            field = "commentCreate"
            status = "created"
        else:
            comment_id = workpad.get("id")
            if type(comment_id) is not str or not comment_id:
                raise WorkLinearError("Linear Workpad response is malformed")
            query = UPDATE_COMMENT
            variables = {"id": comment_id, "body": checked}
            field = "commentUpdate"
            status = "updated"
        try:
            result = _mapping(self._client.query(query, variables), "mutation")
            mutation = _mapping(result.get(field), "mutation")
            if mutation.get("success") is not True:
                raise WorkLinearError("Linear Workpad mutation was not confirmed")
        except Exception as error:
            # A timed-out mutation may have succeeded. One scoped read reconciles it.
            try:
                matched = self._workpad_matches(checked)
            except Exception as reconcile_error:
                raise WorkLinearError(
                    "Linear Workpad mutation outcome is unknown"
                ) from reconcile_error
            if matched is not None:
                return {"status": "reconciled", "comment_id": matched.get("id")}
            raise WorkLinearError(
                "Linear Workpad mutation outcome is unknown"
            ) from error
        matched = self._workpad_matches(checked)
        if matched is None:
            raise WorkLinearError("Linear Workpad mutation was not observable")
        return {"status": status, "comment_id": matched.get("id")}

    def _pull_request_url(self, value: Any) -> str:
        checked = _text(value, "pull request URL", maximum=512)
        parsed = urlsplit(checked)
        match = _PR_PATH.fullmatch(parsed.path)
        if (
            parsed.scheme != "https"
            or parsed.netloc.lower() != "github.com"
            or parsed.query
            or parsed.fragment
            or match is None
            or match.group(1).lower() != self.scope.repository.lower()
        ):
            raise WorkLinearError("pull request URL is outside the scoped repository")
        return checked

    @staticmethod
    def _pull_attachments(issue: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        return [
            item
            for item in _nodes(issue.get("attachments"), "issue attachments")
            if type(item.get("url")) is str
            and urlsplit(item["url"]).netloc.lower() == "github.com"
            and _PR_PATH.fullmatch(urlsplit(item["url"]).path) is not None
        ]

    def _attachment_matches(self, url: str) -> Mapping[str, Any] | None:
        attachments = self._pull_attachments(self._issue())
        matches = [item for item in attachments if item.get("url") == url]
        if len(matches) > 1:
            raise WorkLinearError("scoped issue has duplicate pull request attachments")
        return matches[0] if matches else None

    def attach_pull_request(self, url: Any, title: Any) -> Mapping[str, Any]:
        """Attach the one exact repository PR, reconciling replay by provider state."""

        checked_url = self._pull_request_url(url)
        checked_title = _text(title, "pull request title", maximum=200)
        issue = self._issue()
        attachments = self._pull_attachments(issue)
        exact = [item for item in attachments if item.get("url") == checked_url]
        if len(exact) > 1:
            raise WorkLinearError("scoped issue has duplicate pull request attachments")
        if exact:
            return {"status": "unchanged", "attachment_id": exact[0].get("id")}
        if attachments:
            raise WorkLinearError(
                "scoped issue is already attached to another pull request"
            )
        try:
            result = _mapping(
                self._client.query(
                    ATTACH_PULL_REQUEST,
                    {
                        "issueId": self.scope.issue_id,
                        "url": checked_url,
                        "title": checked_title,
                    },
                ),
                "mutation",
            )
            mutation = _mapping(result.get("attachmentLinkGitHubPR"), "mutation")
            if mutation.get("success") is not True:
                raise WorkLinearError(
                    "Linear pull request attachment was not confirmed"
                )
        except Exception as error:
            try:
                matched = self._attachment_matches(checked_url)
            except Exception as reconcile_error:
                raise WorkLinearError(
                    "Linear pull request attachment outcome is unknown"
                ) from reconcile_error
            if matched is not None:
                return {"status": "reconciled", "attachment_id": matched.get("id")}
            raise WorkLinearError(
                "Linear pull request attachment outcome is unknown"
            ) from error
        matched = self._attachment_matches(checked_url)
        if matched is None:
            raise WorkLinearError("Linear pull request attachment was not observable")
        return {"status": "created", "attachment_id": matched.get("id")}
