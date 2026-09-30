"""Independent advisory review for Qwen-authored candidate pull requests."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

from .work_linear import WORKPAD_HEADING, WorkLinearOperations


class AdvisoryReviewError(RuntimeError):
    """The candidate, packet, response, or durable review record failed closed."""


PACKET_SCHEMA = "sanctum-qwen-candidate-advisory-review/v1"
MAX_PACKET_BYTES = 131_072
MAX_WORKPAD_INPUT_BYTES = 22_000
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
_COMMIT = re.compile(r"[a-f0-9]{40}")
_PR_PATH = re.compile(r"/([^/]+/[^/]+)/pull/([1-9][0-9]*)")
_VERDICTS = {"Approve", "Request changes", "Needs owner decision"}
_CATEGORIES = {
    "acceptance",
    "scope",
    "security",
    "privacy",
    "authority",
    "tests",
    "failure",
    "complexity",
    "documentation",
}


@dataclass(frozen=True)
class AdvisoryReviewBudget:
    """Host-selected reviewer limits, never values selected by issue content."""

    reviewer_family: str
    model: str
    reasoning_effort: str
    timeout_seconds: int
    max_attempts: int

    def __post_init__(self) -> None:
        if self.reviewer_family not in {"codex", "frontier"}:
            raise AdvisoryReviewError("reviewer must be independent Codex/frontier")
        _text(self.model, "reviewer model", 128)
        if self.reasoning_effort not in {
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
            "ultra",
        }:
            raise AdvisoryReviewError("invalid reviewer reasoning effort")
        if (
            type(self.timeout_seconds) is not int
            or not 1 <= self.timeout_seconds <= 3600
        ):
            raise AdvisoryReviewError("invalid reviewer timeout")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 3:
            raise AdvisoryReviewError("invalid reviewer attempt bound")


@dataclass(frozen=True)
class CandidatePullRequest:
    """Trusted candidate facts supplied by the host Git control plane."""

    number: int
    url: str
    base_branch: str
    head_branch: str
    head_commit: str
    open: bool
    merged: bool
    changed_files: tuple[str, ...]
    diff: str
    ci: tuple[Mapping[str, Any], ...]
    validation_evidence: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class AdvisoryFinding:
    title: str
    category: str
    blocking: bool
    evidence: str
    recommendation: str


@dataclass(frozen=True)
class AdvisoryReviewResult:
    verdict: str
    summary: str
    findings: tuple[AdvisoryFinding, ...]


class AdvisoryReviewBackend(Protocol):
    """Tool-less reviewer interface; it receives data and returns data only."""

    def invoke(
        self, packet: Mapping[str, Any], *, timeout_seconds: int
    ) -> Mapping[str, Any]: ...


def _text(value: Any, label: str, maximum: int, minimum: int = 1) -> str:
    if (
        type(value) is not str
        or value.strip() != value
        or not minimum <= len(value) <= maximum
        or any(ord(character) < 32 and character not in "\n\r\t" for character in value)
    ):
        raise AdvisoryReviewError(f"invalid or oversized {label}")
    return value


def _json_collection(
    value: Sequence[Mapping[str, Any]], label: str
) -> list[dict[str, Any]]:
    if len(value) > 50 or any(not isinstance(item, Mapping) for item in value):
        raise AdvisoryReviewError(f"invalid or unbounded {label}")
    try:
        return json.loads(json.dumps(list(value)))
    except (TypeError, ValueError) as exc:
        raise AdvisoryReviewError(f"non-serializable {label}") from exc


def _parse_result(value: Mapping[str, Any]) -> AdvisoryReviewResult:
    if not isinstance(value, Mapping) or set(value) != {
        "verdict",
        "summary",
        "findings",
    }:
        raise AdvisoryReviewError("advisory review response shape is invalid")
    verdict = value.get("verdict")
    summary = _text(value.get("summary"), "review summary", 2000, 20)
    raw_findings = value.get("findings")
    if (
        verdict not in _VERDICTS
        or not isinstance(raw_findings, list)
        or len(raw_findings) > 8
    ):
        raise AdvisoryReviewError("advisory review verdict or finding bound is invalid")
    findings = []
    required = {"title", "category", "blocking", "evidence", "recommendation"}
    for raw in raw_findings:
        if not isinstance(raw, Mapping) or set(raw) != required:
            raise AdvisoryReviewError("advisory review finding shape is invalid")
        if (
            raw.get("category") not in _CATEGORIES
            or type(raw.get("blocking")) is not bool
        ):
            raise AdvisoryReviewError("advisory review finding metadata is invalid")
        findings.append(
            AdvisoryFinding(
                _text(raw.get("title"), "finding title", 180, 8),
                raw["category"],
                raw["blocking"],
                _text(raw.get("evidence"), "finding evidence", 800, 20),
                _text(raw.get("recommendation"), "finding recommendation", 600, 20),
            )
        )
    blocking = any(item.blocking for item in findings)
    if verdict == "Approve" and blocking:
        raise AdvisoryReviewError("approval cannot contain blocking findings")
    if verdict == "Request changes" and not blocking:
        raise AdvisoryReviewError("request changes requires a blocking finding")
    return AdvisoryReviewResult(verdict, summary, tuple(findings))


class QwenCandidateAdvisoryReview:
    """Ask one bounded independent reviewer and record its untrusted findings."""

    def __init__(
        self,
        linear: WorkLinearOperations,
        candidate: CandidatePullRequest,
        run_id: str,
        budget: AdvisoryReviewBudget,
    ) -> None:
        if not isinstance(linear, WorkLinearOperations):
            raise AdvisoryReviewError("scoped Work Mode Linear operations required")
        if not isinstance(candidate, CandidatePullRequest):
            raise AdvisoryReviewError("trusted candidate pull request required")
        if not _RUN_ID.fullmatch(run_id):
            raise AdvisoryReviewError("invalid advisory review run ID")
        self.linear = linear
        self.candidate = candidate
        self.run_id = run_id
        self.budget = budget
        self.marker = f"<!-- advisory-review:{run_id} -->"

    def _workpad(self, issue: Mapping[str, Any]) -> str:
        comments = issue.get("comments")
        nodes = comments.get("nodes") if isinstance(comments, Mapping) else None
        if not isinstance(nodes, list) or len(nodes) > 100:
            raise AdvisoryReviewError("issue comment packet is invalid or unbounded")
        workpads = [
            item
            for item in nodes
            if isinstance(item, Mapping)
            and type(item.get("body")) is str
            and item["body"].splitlines()[:1] == [WORKPAD_HEADING]
        ]
        if len(workpads) != 1:
            raise AdvisoryReviewError("one stable Codex Workpad is required")
        body = workpads[0].get("body")
        if (
            type(body) is not str
            or not body.strip()
            or len(body.encode()) > MAX_WORKPAD_INPUT_BYTES
            or any(
                ord(character) < 32 and character not in "\n\r\t" for character in body
            )
        ):
            raise AdvisoryReviewError("invalid or oversized Workpad body")
        return body

    def _packet(self, issue: Mapping[str, Any], workpad: str) -> Mapping[str, Any]:
        state = issue.get("state")
        if not isinstance(state, Mapping) or state.get("name") != "Human Review":
            raise AdvisoryReviewError("candidate review requires Human Review")
        candidate = self.candidate
        parsed = urlsplit(_text(candidate.url, "candidate PR URL", 512))
        match = _PR_PATH.fullmatch(parsed.path)
        if (
            type(candidate.number) is not int
            or candidate.number <= 0
            or parsed.scheme != "https"
            or parsed.netloc.lower() != "github.com"
            or parsed.query
            or parsed.fragment
            or match is None
            or match.group(1).lower() != self.linear.scope.repository.lower()
            or int(match.group(2)) != candidate.number
            or candidate.base_branch != "v1.3-dev"
            or candidate.head_branch
            != f"symphony/{self.linear.scope.identifier.lower()}"
            or not _COMMIT.fullmatch(candidate.head_commit)
            or candidate.open is not True
            or candidate.merged is not False
        ):
            raise AdvisoryReviewError("candidate PR is outside the fixed issue scope")
        if (
            not 1 <= len(candidate.changed_files) <= 200
            or len(set(candidate.changed_files)) != len(candidate.changed_files)
            or any(
                type(path) is not str
                or not path
                or path.startswith("/")
                or ".." in path.split("/")
                for path in candidate.changed_files
            )
            or len(candidate.diff.encode()) > 100_000
        ):
            raise AdvisoryReviewError("candidate diff packet is invalid or unbounded")
        packet = {
            "schema": PACKET_SCHEMA,
            "issue": {
                "id": self.linear.scope.issue_id,
                "identifier": self.linear.scope.identifier,
                "title": _text(issue.get("title"), "issue title", 500),
                "description": _text(
                    issue.get("description"), "issue description", 16_000
                ),
                "state": "Human Review",
                "workpad": workpad,
            },
            "pull_request": {
                "number": candidate.number,
                "url": candidate.url,
                "base_branch": candidate.base_branch,
                "head_branch": candidate.head_branch,
                "head_commit": candidate.head_commit,
                "changed_files": list(candidate.changed_files),
                "diff": candidate.diff,
                "ci": _json_collection(candidate.ci, "candidate CI evidence"),
                "validation_evidence": _json_collection(
                    candidate.validation_evidence, "candidate validation evidence"
                ),
            },
            "review": {
                "run_id": self.run_id,
                "budget": asdict(self.budget),
                "authority": {
                    "advisory_only": True,
                    "may_modify_repository": False,
                    "may_merge": False,
                    "may_set_execution_gate": False,
                    "may_move_to_done": False,
                    "validates_completion_evidence": False,
                    "owner_decides_disposition": True,
                },
            },
        }
        encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > MAX_PACKET_BYTES:
            raise AdvisoryReviewError("advisory review packet exceeds its bound")
        return packet

    @staticmethod
    def _one_line(value: str) -> str:
        return " ".join(value.split())

    def _section(
        self,
        *,
        status: str,
        attempts: int,
        result: AdvisoryReviewResult | None = None,
        failure: str | None = None,
    ) -> str:
        lines = [
            self.marker,
            "### Independent advisory review",
            "",
            f"- Run: `{self.run_id}`",
            f"- Status: `{status}`",
            f"- Reviewer: `{self.budget.reviewer_family}` / `{self.budget.model}` / `{self.budget.reasoning_effort}`",
            f"- Attempts: `{attempts}/{self.budget.max_attempts}`; per-attempt timeout: `{self.budget.timeout_seconds}s`",
            "- Authority: advisory data only; cannot merge, set execution gates, move the issue to Done, or validate completion evidence.",
        ]
        if result is not None:
            lines.extend(
                [
                    f"- Verdict: `{result.verdict}`",
                    f"- Summary: {self._one_line(result.summary)}",
                    "- Findings:",
                ]
            )
            if not result.findings:
                lines.append("  - None.")
            for finding in result.findings:
                disposition = "blocking" if finding.blocking else "nonblocking"
                lines.append(
                    f"  - [{disposition}/{finding.category}] {self._one_line(finding.title)} — "
                    f"Evidence: {self._one_line(finding.evidence)} Recommendation: "
                    f"{self._one_line(finding.recommendation)}"
                )
        else:
            lines.append(
                f"- Failure: {self._one_line(failure or 'unknown reviewer failure')}"
            )
            lines.append(
                "- Disposition: visible advisory failure; no approval or completion claim was inferred."
            )
        return "\n".join(lines)

    def _record(self, workpad: str, section: str) -> None:
        updated = f"{workpad.rstrip()}\n\n{section}\n"
        if len(updated.encode()) > 32_000:
            raise AdvisoryReviewError("advisory review record exceeds Workpad bound")
        self.linear.upsert_workpad(updated)

    def run(self, backend: AdvisoryReviewBackend) -> Mapping[str, Any]:
        """Run within fixed limits; every terminal reviewer failure is recorded."""

        issue = self.linear.fetch_issue()
        workpad = self._workpad(issue)
        if self.marker in workpad:
            return {"status": "already_recorded", "run_id": self.run_id}
        packet = self._packet(issue, workpad)
        if not callable(getattr(backend, "invoke", None)):
            self._record(
                workpad,
                self._section(
                    status="FAILED", attempts=0, failure="reviewer backend unavailable"
                ),
            )
            return {"status": "failed", "run_id": self.run_id, "attempts": 0}
        last_error = "reviewer failed without a safe diagnostic"
        for attempt in range(1, self.budget.max_attempts + 1):
            try:
                raw = backend.invoke(
                    packet, timeout_seconds=self.budget.timeout_seconds
                )
                result = _parse_result(raw)
            except (
                Exception
            ) as exc:  # Backend and malformed-output failures share one bound.
                last_error = f"{type(exc).__name__}: {str(exc)[:240]}"
                continue
            # Recording is a host evidence operation, not a reviewer attempt. If it
            # fails, propagate rather than requesting another advisory response.
            self._record(
                workpad,
                self._section(status="COMPLETED", attempts=attempt, result=result),
            )
            return {
                "status": "completed",
                "run_id": self.run_id,
                "attempts": attempt,
                "verdict": result.verdict,
                "findings": len(result.findings),
                "completion_evidence": False,
            }
        self._record(
            workpad,
            self._section(
                status="FAILED",
                attempts=self.budget.max_attempts,
                failure=last_error,
            ),
        )
        return {
            "status": "failed",
            "run_id": self.run_id,
            "attempts": self.budget.max_attempts,
            "completion_evidence": False,
        }
