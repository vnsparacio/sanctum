"""Pure offline composition. No I/O, dispatch, approvals, or tool capabilities."""
from dataclasses import dataclass
from hashlib import sha256
import json

REASONS = frozenset({'ambiguity', 'conflicting_heads', 'missing_context',
                     'weak_training_support', 'unsupported_input', 'inference_failure'})
PRIVACY = {'PUBLIC': 0, 'PERSONAL': 1, 'RESTRICTED': 2}

@dataclass(frozen=True)
class Request:
    scope: str
    revision: int
    messages: tuple
    operation_revision: str = ''

    def valid(self):
        return (type(self.scope) is str and bool(self.scope) and type(self.revision) is int
                and self.revision >= 0 and type(self.operation_revision) is str
                and type(self.messages) is tuple and bool(self.messages)
                and all(type(m) is tuple and len(m) == 2 and type(m[0]) is str and m[0] in
                        {'user', 'assistant', 'tool'} and type(m[1]) is str and bool(m[1])
                        for m in self.messages))

    def digest(self):
        return sha256(json.dumps([self.scope, self.revision, self.messages,
                                 self.operation_revision], ensure_ascii=False).encode()).hexdigest()

@dataclass(frozen=True)
class Signal:
    value: str  # CLEAR, POSITIVE, UNKNOWN
    request_digest: str
    reasons: tuple = ()

    def usable(self, digest):
        return (type(self.value) is str and self.value in {'CLEAR', 'POSITIVE'}
                and self.request_digest == digest and self.reasons == ())

@dataclass(frozen=True)
class TrustedFacts:
    """Only a future authenticated Mac adapter may construct these in deployment.

    This workbench has no such adapter and cannot issue an approval or an action.
    A model's JSON must never be deserialized into TrustedFacts.
    """
    privacy_floor: str = 'RESTRICTED'
    context_complete: bool = False
    reset_scope: bool = False
    external_approval_digest: str | None = None
    closed_frontier_available: bool = False

@dataclass(frozen=True)
class State:
    scope: str = ''
    high_stakes: bool = False
    privacy_floor: str = 'PUBLIC'
    revision: int = -1
    request_digest: str = ''

@dataclass(frozen=True)
class Decision:
    handling: str
    route_requirement: str
    privacy_floor: str
    reasons: tuple
    open_weight_eligible: bool
    external_processing_eligible: bool
    authority: str = 'MAC_ONLY'
    tool_authorized: bool = False
    action_authorized: bool = False
    egress_authorized: bool = False
    offline_only: bool = True

def compose(request, facts, state, urgency, global_stakes, domain_heads=(), architecture='A'):
    if type(facts) is not TrustedFacts or type(state) is not State:
        raise TypeError('Trusted Mac facts/state required; learned dictionaries are not accepted')
    if architecture not in {'A', 'C'}:
        raise ValueError('Unsupported architecture')
    valid = type(request) is Request and request.valid()
    digest = request.digest() if valid else ''
    reasons = set()
    privacy_values = [state.privacy_floor, facts.privacy_floor]
    privacy = max((v if type(v) is str and v in PRIVACY else 'RESTRICTED' for v in privacy_values), key=PRIVACY.get)
    if not valid:
        reasons.add('unsupported_input')
    if facts.context_complete is not True:
        reasons.add('missing_context')
    reset = facts.reset_scope is True
    changed_scope = valid and state.scope and request.scope != state.scope
    stale = valid and state.scope == request.scope and request.revision < state.revision
    reused_revision = (valid and state.scope == request.scope and
                       request.revision == state.revision and
                       (not state.request_digest or state.request_digest != digest))
    if (changed_scope and not reset) or stale or reused_revision:
        reasons.add('missing_context')
    context_invalid = bool({'missing_context', 'unsupported_input'} & reasons)
    def check(signal):
        if type(signal) is not Signal:
            reasons.add('inference_failure')
            return 'UNKNOWN'
        if not signal.usable(digest):
            if type(signal.reasons) is tuple:
                reasons.update(r for r in signal.reasons if type(r) is str and r in REASONS)
            reasons.add('ambiguity' if signal.request_digest == digest else 'missing_context')
            return 'UNKNOWN'
        return signal.value
    u = check(urgency)
    # A global head is mandatory even if domain heads or urgency are positive.
    g = check(global_stakes)
    ds = [check(s) for s in domain_heads] if architecture == 'C' else []
    if architecture == 'C' and not ds:
        ds = ['UNKNOWN']
        reasons.add('weak_training_support')
    if 'POSITIVE' in [g] + ds and 'CLEAR' in [g] + ds:
        reasons.add('conflicting_heads')
    held = state.high_stakes is True and not reset
    if context_invalid or u != 'CLEAR':
        handling = 'URGENT_SAFETY'
    elif held or g != 'CLEAR' or any(s != 'CLEAR' for s in ds):
        handling = 'HIGH_STAKES'
    else:
        handling = 'NORMAL'
    approved = valid and facts.external_approval_digest == digest
    external = False
    if handling == 'URGENT_SAFETY':
        route = 'DETERMINISTIC_URGENT_RESPONSE'
    elif handling == 'HIGH_STAKES':
        if privacy != 'PUBLIC' and not approved:
            route = 'BLOCKED_PENDING_MAC_EXTERNAL_APPROVAL'
        elif facts.closed_frontier_available is not True:
            route = 'BLOCKED_CLOSED_FRONTIER_UNAVAILABLE'
        else:
            route = 'CLOSED_FRONTIER_REQUIRED_MAC_DISPATCH'
            external = True
    else:
        route = 'ORDINARY_LOCAL_ELIGIBLE_MAC_DISPATCH'
    decision = Decision(handling, route, privacy, tuple(sorted(reasons)),
                        handling == 'NORMAL', external)
    # Invalid/incomplete requests may raise the floor, never move the checkpoint
    # backwards or adopt an untrusted new scope. Retries need a complete request.
    checkpoint_ok = valid and not context_invalid
    next_state = State(request.scope if checkpoint_ok else state.scope,
                       handling != 'NORMAL' or held, privacy,
                       request.revision if checkpoint_ok else state.revision,
                       digest if checkpoint_ok else state.request_digest)
    return decision, next_state

class OfflineRouter:
    def __init__(self, urgency, stakes, domains=(), architecture='A'):
        self.urgency, self.stakes, self.domains = urgency, stakes, tuple(domains)
        self.architecture = architecture

    def assess(self, request, facts, state=State()):
        def call(head):
            try:
                return head(request)
            except Exception:
                # Exception messages may contain private input: do not log them.
                return Signal('UNKNOWN', '', ('inference_failure',))
        urgency = call(self.urgency)
        stakes = call(self.stakes)
        domains = tuple(call(h) for h in self.domains) if self.architecture == 'C' else ()
        return compose(request, facts, state, urgency, stakes, domains, self.architecture)
