#!/usr/bin/env python3
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from session_state import SessionStore
from session_decision import state_to_classifier_context, decision_privacy_to_session_state
from request_classifier import load_rules, classify_request
from router import load_policy
from provenance import load_registry, build_envelope, route_envelope

tmp = Path(tempfile.mkdtemp(prefix="phase9a4-test-"))
state_dir = tmp / "state"
store = SessionStore(state_dir)

passed = 0
total = 0

def check(name, cond):
    global passed, total
    total += 1
    if not cond:
        raise AssertionError(name)
    passed += 1

# 1-4: storage + unknown
u = store.get("sess-test")
check("unknown before start", u["privacy"] == "UNKNOWN")
check("state dir mode 700", stat.S_IMODE(state_dir.stat().st_mode) == 0o700)
check("state file mode 600", stat.S_IMODE((state_dir/"sessions.json").stat().st_mode) == 0o600)
check("audit file mode 600", stat.S_IMODE((state_dir/"audit.jsonl").stat().st_mode) == 0o600)

# 5-8: start
s = store.start("sess-test")
check("start clean", s["privacy"] == "CLEAN")
check("generation one", s["generation"] == 1)
check("get clean", store.get("sess-test")["privacy"] == "CLEAN")
try:
    store.start("sess-test")
    dup_refused = False
except RuntimeError:
    dup_refused = True
check("duplicate start refused", dup_refused)

# 9-13: monotonic observations
r = store.observe("sess-test", "CLEAN", reason="public request")
check("clean observation stays clean", r["privacy"] == "CLEAN")
r = store.observe("sess-test", "PERSONAL", reason="gmail provenance")
check("escalates personal", r["privacy"] == "PERSONAL")
r = store.observe("sess-test", "CLEAN", reason="later public request")
check("cannot auto downgrade personal", r["privacy"] == "PERSONAL")
r = store.observe("sess-test", "RESTRICTED", reason="credential tag")
check("escalates restricted", r["privacy"] == "RESTRICTED")
r = store.observe("sess-test", "PERSONAL", reason="later personal request")
check("cannot downgrade restricted", r["privacy"] == "RESTRICTED")

# 14-17: reset rules
try:
    store.reset("sess-test", reason="please")
    bad_reset_refused = False
except ValueError:
    bad_reset_refused = True
check("reset exact reason required", bad_reset_refused)
r = store.reset("sess-test", reason="new-context")
check("explicit reset clean", r["privacy"] == "CLEAN")
check("reset increments generation", r["generation"] == 2)
check("created_at retained", r["created_at"] == s["created_at"])

# 18: unknown observe refused
try:
    store.observe("missing", "PERSONAL", reason="test")
    unknown_observe_refused = False
except RuntimeError:
    unknown_observe_refused = True
check("unknown observe refused", unknown_observe_refused)

# 19: invalid session id refused
try:
    store.start("bad/session")
    invalid_id_refused = False
except ValueError:
    invalid_id_refused = True
check("invalid session id refused", invalid_id_refused)

# 20-23: audit is metadata only
audit_lines = [
    json.loads(line)
    for line in (state_dir/"audit.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
check("audit exists", len(audit_lines) >= 1)
allowed = {"ts","session_id","event","before","after","reason","generation"}
check("audit keys constrained", all(set(x.keys()) <= allowed for x in audit_lines))
check("audit no content field", all("content" not in x for x in audit_lines))
check("audit no prompt field", all("prompt" not in x for x in audit_lines))

# 24-27: mapping
check("clean maps clean", state_to_classifier_context("CLEAN") == "clean")
check("personal maps personal", state_to_classifier_context("PERSONAL") == "personal")
check("restricted maps restricted", state_to_classifier_context("RESTRICTED") == "restricted")
check("unknown maps unknown", state_to_classifier_context("UNKNOWN") == "unknown")
check("public decision maps clean state", decision_privacy_to_session_state("PUBLIC") == "CLEAN")
check("personal decision maps personal state", decision_privacy_to_session_state("PERSONAL") == "PERSONAL")
check("restricted decision maps restricted state", decision_privacy_to_session_state("RESTRICTED") == "RESTRICTED")

# 31-38: end-to-end decision semantics without invoking CLI
policy = load_policy(HERE / "policy.json")
registry = load_registry(HERE / "source_registry.json")
rules = load_rules(HERE / "classifier_rules.json")

# Fresh clean generic request stays public and clean.
fresh = store.start("sess-public")
c = classify_request(rules, "Explain Kubernetes taints.", session_context="clean")
env = build_envelope(
    registry, tools=[], user_class=c["user_class"], browser_visibility="private",
    task=c["task"], context_tokens=0, tags=c["tags"], quality=c["quality"],
    aws_state="stopped", hosted_state="available"
)
d = route_envelope(policy, env)["decision"]
store.observe("sess-public", decision_privacy_to_session_state(d["privacy"]), reason=f"routing decision => {d['privacy']}")
check("generic clean decision public", d["privacy"] == "PUBLIC")
check("public observation leaves session clean", store.get("sess-public")["privacy"] == "CLEAN")

# Gmail taints same session PERSONAL.
c = classify_request(rules, "Summarize my email.", session_context="clean")
env = build_envelope(
    registry, tools=["gmail_read"], user_class=c["user_class"], browser_visibility="private",
    task=c["task"], context_tokens=0, tags=c["tags"], quality=c["quality"],
    aws_state="running", hosted_state="available"
)
d = route_envelope(policy, env)["decision"]
store.observe("sess-public", decision_privacy_to_session_state(d["privacy"]), reason=f"routing decision => {d['privacy']}")
check("gmail decision personal", d["privacy"] == "PERSONAL")
check("gmail taints session personal", store.get("sess-public")["privacy"] == "PERSONAL")

# Generic next request cannot auto-declassify because session is PERSONAL.
c2 = classify_request(rules, "Explain Kubernetes taints.", session_context="personal")
check("generic followup in personal session stays personal", c2["privacy_hint"] == "PERSONAL")
check("generic followup not auto public", c2["auto_declassified"] is False)

# Explicit public ignored while session personal.
c3 = classify_request(
    rules, "Explain Kubernetes taints.",
    session_context="personal", explicit_public=True
)
check("explicit public ignored in tainted session", c3["privacy_hint"] == "PERSONAL")

# Reset permits clean classification again.
store.reset("sess-public", reason="new-context")
c4 = classify_request(rules, "Explain Kubernetes taints.", session_context="clean")
check("new context permits public again", c4["privacy_hint"] == "PUBLIC")

# 36-39 restricted persistence concept
store.start("sess-restricted")
store.observe("sess-restricted", "RESTRICTED", reason="credential tag")
check("restricted persisted", store.get("sess-restricted")["privacy"] == "RESTRICTED")
cr = classify_request(rules, "Explain Kubernetes.", session_context="restricted")
check("restricted classifier context remains restricted", cr["privacy_hint"] == "RESTRICTED")
check("restricted session tags marker", "session_restricted" in cr["tags"])
store.observe("sess-restricted", "CLEAN", reason="later clean text")
check("restricted cannot clean itself", store.get("sess-restricted")["privacy"] == "RESTRICTED")

# 40-42 listing/state schema
sessions = store.list_sessions()
check("list returns sessions", len(sessions) >= 3)
raw = json.loads((state_dir/"sessions.json").read_text(encoding="utf-8"))
check("state schema correct", raw["schema"] == "hybrid-ai-session-state/v1")
check("state stores no request content", all("content" not in rec and "prompt" not in rec for rec in raw["sessions"].values()))

print(f"Phase 9A.4 session-state tests: {passed}/{total} PASS")
print("PASS: monotonic metadata-only session privacy regression suite")
