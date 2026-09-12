#!/usr/bin/env python3
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = HERE / "shadow_bridge.py"
tmp = Path(tempfile.mkdtemp(prefix="phase9a5a-test-"))
state = tmp / "state"
log = tmp / "shadow.jsonl"

passed = 0
total = 0

def check(name, cond):
    global passed,total
    total += 1
    if not cond:
        raise AssertionError(name)
    passed += 1

def send(payload):
    payload["state_dir"] = str(state)
    p = subprocess.run(
        ["python3", str(BRIDGE), "--log", str(log)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=5,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stdout)
    return json.loads(p.stdout)

send({"event_type":"session_start","session_id":"s1","resumed":False,"ts":"t0"})
r = send({"event_type":"turn_start","session_id":"s1","run_hash":"r1","ts":"t1"})
check("turn starts clean", r["session_before"] == "CLEAN")

# Same exact synthetic prompt that exposed the bug.
r = send({
    "event_type":"route_decision",
    "session_id":"s1",
    "run_hash":"r1",
    "prompt":"Compare TCP and UDP in one sentence.",
    "ts":"t2",
    "aws_state":"stopped",
    "hosted_state":"available",
})
check("smoke prompt public", r["decision"]["privacy"] == "PUBLIC")
check("smoke prompt hosted", r["decision"]["preferred_route"] == "HOSTED_REMOTE")
check("smoke prompt 80b", r["decision"]["reasoning_tier"] == "hosted_80b")
check("public leaves session clean", r["session_after"] == "CLEAN")

# Tool privacy can escalate during turn while route is evaluated from pre-turn snapshot.
send({"event_type":"turn_start","session_id":"s1","run_hash":"r2","ts":"t3"})
rtool = send({
    "event_type":"tool_result",
    "session_id":"s1",
    "run_hash":"r2",
    "tool_name":"gmail_read",
    "ts":"t4",
})
check("gmail escalates current session", rtool["session_after"] == "PERSONAL")

r = send({
    "event_type":"route_decision",
    "session_id":"s1",
    "run_hash":"r2",
    "prompt":"Compare TCP and UDP in one sentence.",
    "ts":"t5",
})
check("opening snapshot still public", r["decision"]["privacy"] == "PUBLIC")
check("opening hypothetical hosted", r["decision"]["preferred_route"] == "HOSTED_REMOTE")
check("midturn boundary detected", r["boundary_alert"] is True)
check("final session remains personal", r["session_after"] == "PERSONAL")

serialized = log.read_text()
check("raw public prompt not persisted", "Compare TCP and UDP" not in serialized)
check("forbidden prompt key absent", '"prompt"' not in serialized)

events = [json.loads(x) for x in serialized.splitlines() if x.strip()]
check("route decision logged", any(e.get("event")=="route_decision" for e in events))
check("turn start logged", any(e.get("event")=="turn_start" for e in events))

print(f"Phase 9A.5a end-of-turn routing tests: {passed}/{total} PASS")
print("PASS: raw-user shadow classification without llm_input")
