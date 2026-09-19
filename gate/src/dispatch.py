"""Deterministic Mac policy: learned capability signals never grant authority."""

from dataclasses import asdict

from common import canonical
from risk_policy import Request, Signal, State, TrustedFacts, compose
from schema import validate
from source_policy import decide


def assess(packet, state, audit, strong=False):
    x = validate(audit)
    r = Request(
        packet["scope"],
        packet["revision"],
        (("user", packet["prompt"]),),
        canonical(packet),
    )

    def signal(value, mapping):
        v = mapping[value]
        return Signal(v, r.digest(), ("ambiguity",) if v == "UNKNOWN" else ())

    d, s = compose(
        r,
        TrustedFacts("PERSONAL", True, False, None, True),
        State(**state),
        signal(
            x["urgency"],
            {"ABSENT": "CLEAR", "PRESENT": "POSITIVE", "UNKNOWN": "UNKNOWN"},
        ),
        signal(
            x["stakes"],
            {"NORMAL": "CLEAR", "HIGH_STAKES": "POSITIVE", "UNKNOWN": "UNKNOWN"},
        ),
    )
    needed = x["context_need"]["classification"]
    if x["urgency"] == "PRESENT":
        route = "URGENT_SAFETY"
    elif "REQUIRED" in needed.values():
        route = "CONTEXT_REQUIRED"
    elif x["urgency"] == "UNKNOWN" or x["stakes"] == "UNKNOWN":
        route = "UNAVAILABLE"
    elif d.handling == "HIGH_STAKES" or strong:
        route = "OPENAI_FRONTIER"
    elif x["needs_local_tools"]:
        # OpenClaw keeps its own tool loop and existing permissions. Media requiring
        # tools needs a separate owner-authored task; never sneak it into an agent.
        route = "UNAVAILABLE" if packet["attachment_summary"]["count"] else "LOCAL_4B"
    elif packet["attachment_summary"]["visual_count"] and (
        x["quality"]["recommended_tier"] == "MULTIMODAL"
        or x["context_need"]["answer"]["attachments"] == "REQUIRED"
    ):
        route = "MULTIMODAL"
    else:
        tier = x["quality"]["recommended_tier"]
        route = tier if tier != "MULTIMODAL" else "UNAVAILABLE"
        if (
            packet["attachment_summary"]["count"]
            and x["context_need"]["answer"]["attachments"] == "REQUIRED"
            and route == "LOCAL_4B"
        ):
            route = "HOSTED_235B"
        if route == "LOCAL_4B" and set(x["quality"]["reason_codes"]) & {
            "CODE_DATA_ANALYSIS",
            "TECHNICAL_DEBUGGING",
            "MULTISTEP_NUMERIC",
            "STRUCTURED_SCHEMA",
            "COMPLEX_SYNTHESIS",
        }:
            route = "HOSTED_235B"
    if route == "PRIVATE_80B":
        route = "HOSTED_235B"  # Normal policy; exact disclosure still required.
    return {
        "status": "OK",
        "state": asdict(s),
        "handling": d.handling,
        "urgency": x["urgency"],
        "route": route,
        "audit": x,
        "source_decision": asdict(decide(packet, x)),
    }
