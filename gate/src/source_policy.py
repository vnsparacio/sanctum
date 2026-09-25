"""Pure Mac-owned Source-First policy and conservative query minimization."""

import json
import re
from dataclasses import asdict, dataclass
from hashlib import sha256

SOURCE_REASONS = frozenset(
    {
        "CURRENT_OR_CHANGING",
        "TECHNICAL_DOCUMENTATION",
        "PRODUCT_OR_MODEL_CAPABILITY",
        "PRICE_OR_AVAILABILITY",
        "LAW_OR_REGULATION",
        "CURRENT_ENTITY",
        "CURRENT_EVENT",
        "RECENT_RESEARCH",
        "TRAVEL",
        "CURRENT_RECOMMENDATION",
        "NICHE_OR_EXTERNALLY_VERIFIABLE",
        "SUPPLIED_EVIDENCE_ADEQUATE",
        "TRANSFORMATION_ONLY",
        "DETERMINISTIC_OR_SELF_CONTAINED",
    }
)
WEB_REASONS = SOURCE_REASONS - {
    "SUPPLIED_EVIDENCE_ADEQUATE",
    "TRANSFORMATION_ONLY",
    "DETERMINISTIC_OR_SELF_CONTAINED",
}
PRIVATE_MARKERS = re.compile(
    r"(?:\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b\+?\d[\d .()\-]{7,}\d\b|/Users/|/private/|\b(?:token|secret|password|api[_ -]?key)\b|-----BEGIN|\b(?:he|she|they) said\b|\b[A-Z][a-z]{1,30} said\b|\bmy (?:doctor|wife|husband|friend|boss|child|home|house|address|location|email|gmail|message|calendar|appointment|file|document|attachment)\b|\b(?:gmail|email|message|calendar|attachment|tool output|private context|local file)\s+(?:says?|shows?|contains?|from)\b)",
    re.I,
)
CONTROL = re.compile(r"/(?:gate|approve|attach|detach|result|cancel)\b", re.I)
WORDS = re.compile(r"[A-Za-z][A-Za-z0-9_.+/#:-]{1,79}|\b\d{5}\b")
QUERY_SCAFFOLDING = frozenset(
    {
        "both",
        "cite",
        "cites",
        "citing",
        "compare",
        "comparing",
        "directly",
        "discuss",
        "distinguish",
        "documented",
        "find",
        "give",
        "information",
        "later",
        "look",
        "lookup",
        "main",
        "only",
        "provide",
        "search",
        "source",
        "sources",
        "summarize",
        "summary",
        "up",
    }
)
WEATHER = re.compile(r"\b(?:weather|forecast|temperature|rain|conditions)\b", re.I)
WEATHER_ZIP = re.compile(r"\b(?:zip(?:\s*code)?|in|for)\s+(\d{5})\b", re.I)
UPGRADE = re.compile(
    r"\b(?:current|currently|latest|today|now|price|pricing|availability|available|regulation|law|schedule|documentation|docs|release notes|model capability|product behavior|recommend)\b",
    re.I,
)
LOCAL_SOURCE = re.compile(
    r"\bmy\s+(?:latest|recent|last|newest|unread|next|upcoming)?\s*(?:e-?mails?|gmail|inbox|texts?|iMessages?|sms|calendar|appointments?|meetings?)\b",
    re.I,
)
SAFE_PRIVATE_TERMS = frozenset(
    "current latest price pricing availability regulation law schedule documentation docs release notes model capability product behavior recommend cause causes symptom symptoms treatment persistent unilateral calf swelling medical legal technical public general guidance".split()
)


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class QueryDraft:
    query: str
    sensitivity: str
    mode: str
    reason_codes: tuple
    digest: str


@dataclass(frozen=True)
class SourceDecision:
    schema: str
    need: str
    reason_codes: tuple
    query_mode: str
    adequacy_requirement: str
    request_digest: str
    scope: str
    revision: int
    authority: str = "MAC_POLICY"
    query: dict | None = None


def minimize_query(prompt):
    if type(prompt) is not str or not prompt.strip() or len(prompt.encode()) > 32768:
        return QueryDraft("", "RESTRICTED", "DENY", ("INVALID_QUERY",), "")
    raw = CONTROL.sub(" ", prompt)
    private = bool(PRIVATE_MARKERS.search(raw))
    # A ZIP explicitly supplied for a public weather request is the requested
    # location, not a generic numeric identifier. Keep exactly one such ZIP;
    # never lift a ZIP from private context into an automatic public query.
    weather_zips = (
        set(WEATHER_ZIP.findall(raw)) if not private and WEATHER.search(raw) else set()
    )
    all_zips = set(re.findall(r"\b\d{5}\b", raw))
    public_weather_zip = (
        next(iter(weather_zips)) if len(weather_zips) == len(all_zips) == 1 else None
    )
    raw = PRIVATE_MARKERS.sub(" ", raw)
    if private:
        raw = re.sub(r"\b[A-Z][a-z]{1,30}\b", " ", raw)
    # Quoted personal narrative is never a useful automatic public query.
    raw = re.sub(r'(["\']).{0,512}?\1', " ", raw)
    words = []
    for word in WORDS.findall(raw):
        lower = word.lower().strip(".:/#-")
        if lower.isdigit() and lower != public_weather_zip:
            continue
        if lower in QUERY_SCAFFOLDING or lower in {
            "please",
            "could",
            "would",
            "should",
            "tell",
            "about",
            "an",
            "and",
            "what",
            "when",
            "where",
            "with",
            "from",
            "this",
            "that",
            "the",
            "for",
            "is",
            "in",
            "of",
            "on",
            "at",
            "have",
            "does",
            "said",
            "yesterday",
            "use",
            "report",
            "public",
            "evidence",
            "preferably",
            "zip",
        }:
            continue
        if private and lower not in SAFE_PRIVATE_TERMS:
            continue
        if lower not in words:
            words.append(lower)
    # Verbose weather instructions dilute the ZIP search and can yield only
    # promotional or blocked pages. The explicit public ZIP already supplies
    # the requested location; keep the current-day cue without the prose.
    query = (
        f"{public_weather_zip} weather forecast today"
        if public_weather_zip and re.search(r"\btoday\b", raw, re.I)
        else " ".join(words[:16]).strip()
    )
    if len(query) < 4 or (private and len(words) < 3):
        return QueryDraft(
            "",
            "PERSONAL" if private else "RESTRICTED",
            "EXACT_APPROVAL_REQUIRED" if private else "DENY",
            ("PRIVATE_CONTEXT_REMOVED" if private else "QUERY_INADEQUATE",),
            "",
        )
    reasons = ("PRIVATE_CONTEXT_GENERALIZED",) if private else ("PUBLIC_REQUEST",)
    return QueryDraft(
        query,
        "PUBLIC",
        "PUBLIC_GENERALIZED",
        reasons,
        digest({"query": query, "reasons": reasons}),
    )


def decide(packet, audit):
    source = audit["source_need"]
    advised, codes = source["classification"], tuple(source["reason_codes"])
    prompt = packet["prompt"]
    need = advised
    # A stable local lower bound protects current/external requests if advisory
    # classification is too weak. It never lowers WEB_REQUIRED.
    if (
        advised != "WEB_REQUIRED"
        and UPGRADE.search(prompt)
        and not LOCAL_SOURCE.search(prompt)
    ):
        need = "WEB_REQUIRED"
        codes = tuple(sorted(set(codes) | {"CURRENT_OR_CHANGING"}))
    if need == "NONE":
        return SourceDecision(
            "sanctum-source/v1",
            need,
            codes,
            "NONE",
            "NOT_REQUIRED",
            digest(packet),
            packet["scope"],
            packet["revision"],
        )
    draft = minimize_query(prompt)
    return SourceDecision(
        "sanctum-source/v1",
        need,
        codes,
        draft.mode,
        "REQUIRED" if need == "WEB_REQUIRED" else "OPTIONAL",
        digest(packet),
        packet["scope"],
        packet["revision"],
        query=asdict(draft),
    )
