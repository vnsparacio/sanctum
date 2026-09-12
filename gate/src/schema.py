"""Extend the installed audit; preserve the original risk ontology and composer."""
from common import Refused

TIERS = ['LOCAL_4B', 'PRIVATE_80B', 'HOSTED_235B', 'MULTIMODAL', 'OPENAI_FRONTIER']
REASONS = ['ROUTINE_LANGUAGE', 'CODE_DATA_ANALYSIS', 'TECHNICAL_DEBUGGING', 'MULTISTEP_NUMERIC', 'STRUCTURED_SCHEMA', 'COMPLEX_SYNTHESIS', 'VISUAL_UNDERSTANDING', 'FRONTIER_REQUIRED']
def enum(values): return {'type': 'string', 'enum': values}
def obj(properties): return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}
def array(values): return {'type': 'array', 'items': enum(values)}

SCHEMA = obj({
    'urgency': enum(['PRESENT', 'ABSENT', 'UNKNOWN']),
    'stakes': enum(['HIGH_STAKES', 'NORMAL', 'UNKNOWN']),
    'domains': array(['medical_medication', 'finance', 'legal', 'employment', 'security', 'other_unknown']),
    'request_role': enum(['explanation', 'transformation', 'personalized_recommendation', 'decision_support', 'proposed_execution', 'other_unknown']),
    'uncertainty': array(['ambiguity', 'missing_context', 'unsupported_input', 'inference_failure', 'weak_training_support', 'conflicting_heads']),
    'quality': obj({'recommended_tier': enum(TIERS), 'reason_codes': array(REASONS)}),
    'context_need': obj({
        'classification': obj({'attachments': enum(['NONE', 'HELPFUL', 'REQUIRED']), 'prior_context': enum(['NONE', 'REQUIRED'])}),
        'answer': obj({'attachments': enum(['NONE', 'HELPFUL', 'REQUIRED']), 'prior_context': enum(['NONE', 'REQUIRED'])})}),
    'needs_local_tools': {'type': 'boolean'}
})

def validate(value, schema=SCHEMA):
    typ = schema['type']
    if typ == 'object':
        if type(value) is not dict or set(value) != set(schema['required']): raise Refused('schema_keys')
        for k, v in value.items(): validate(v, schema['properties'][k])
    elif typ == 'array':
        if type(value) is not list or len(value) > 12 or any(type(x) is not str for x in value) or len(set(value)) != len(value): raise Refused('schema_array')
        for x in value: validate(x, schema['items'])
    elif typ == 'boolean':
        if type(value) is not bool: raise Refused('schema_boolean')
    elif type(value) is not str or value not in schema['enum']: raise Refused('schema_enum')
    if schema is SCHEMA:
        if not value['domains']: raise Refused('empty_domains')
        unknown = 'UNKNOWN' in (value['urgency'], value['stakes'])
        if unknown != bool(value['uncertainty']): raise Refused('inconsistent_uncertainty')
        if value['urgency'] == 'PRESENT' and value['stakes'] == 'NORMAL': raise Refused('contradictory_targets')
        needs = value['context_need']['classification']
        if 'REQUIRED' in needs.values() and not unknown: raise Refused('missing_context_not_unknown')
    return value
