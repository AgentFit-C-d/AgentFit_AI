"""Review only assigned, non-reflexive feature coverage relationships."""
import copy

from .candidate_feature_curation import (
    _feature_candidates, _validate_partition, validate_feature_curation)
from .candidate_split_review import _payload
from .deepseek_evaluation import MODEL, NVIDIA_REVIEW_MODELS, NvidiaAnalyzer, post_nvidia
from .diagnostics import safe_code
from .solar import AnalysisError, SolarAnalyzer, post_solar


_COVERAGE = ('covered', 'not_covered', 'uncertain')
_VALUE_CONTEXT_INSTRUCTION = (
    'The selected representative.value is the text used as the displayed feature, '
    'not the whole surrounding paragraph. Context may resolve references, scope or '
    'an established alias identity; it must not add a separate action or capability '
    'that is absent from that selected value. In particular, a conditional/action '
    'fragment does not inherit the actions of the following clause. Evaluate whether '
    'the selected value represents the member capability, rather than whether both '
    'belong to the same workflow. Preserve genuinely equivalent names and descriptions; '
    'do not reject aliases merely because their wording differs.')


def _validate_assessments(reply, relations):
    expected = {row['memberId']: row['representativeId'] for row in relations}
    if type(reply) is not dict or set(reply) != {'assessments'}:
        raise ValueError('invalid feature relations')
    rows = reply['assessments']
    if type(rows) is not list or len(rows) != len(expected):
        raise ValueError('incomplete feature relations')
    statuses = {}
    for row in rows:
        if type(row) is not dict or set(row) != {'memberId', 'representativeId', 'coverage'}:
            raise ValueError('invalid feature relation')
        member, representative, coverage = row['memberId'], row['representativeId'], row['coverage']
        if (type(member) is not str or member not in expected or member in statuses or
                type(representative) is not str or expected[member] != representative or
                type(coverage) is not str or coverage not in _COVERAGE):
            raise ValueError('invalid feature relation')
        statuses[member] = coverage
    return statuses


def review_feature_relations(document, frozen, reviewed_labels, partition, key, *,
                             model=MODEL, transport=None, call_trace=None):
    """Return the existing curation contract with zero or one semantic-review call."""
    if (type(key) is not str or not key.strip() or
            type(model) is not str or model not in ('solar-pro4', *NVIDIA_REVIEW_MODELS) or
            (transport is not None and not callable(transport)) or
            (call_trace is not None and type(call_trace) is not list)):
        raise ValueError('invalid feature relation options')
    candidates = _feature_candidates(document, frozen, reviewed_labels)
    _validate_partition(candidates, partition)
    partition = copy.deepcopy(partition)
    assigned = {member: group['representativeId']
                for group in partition['groups'] for member in group['memberIds']
                if member != group['representativeId']}
    relations = [{'memberId': item['id'], 'representativeId': assigned[item['id']]}
                 for item in candidates if item['id'] in assigned]
    statuses = {}
    if relations:
        participants = set(assigned) | set(assigned.values())
        payload = _payload('agentfit_feature_relations',
            'Assess each supplied representative-member relationship independently. '
            'Both occurrences were already reviewed as current product facts; do not '
            'reclassify them or judge the whole grouping at once. Does the representative '
            'operation, read in its exact source context, cover the capability expressed '
            'by this member occurrence? Use covered for equivalent operations, aliases, '
            'or genuinely included suboperations. Use not_covered for distinct capabilities '
            'not expressed by this representative. A step that provides input to another '
            'operation does not by itself represent that downstream capability. '
            'Similar wording alone does not establish coverage across different contexts. '
            'Use uncertain when the source does not resolve the relationship. Return every '
            'supplied pair exactly once with covered, not_covered or uncertain. Never '
            'change IDs, add relationships, quote source text or invent a broader operation. '
            'The server separately handles representatives themselves and unrepresented '
            'candidates; neither is a relationship to assess here. ' + _VALUE_CONTEXT_INSTRUCTION,
            {'document': document,
             'candidates': [item for item in candidates if item['id'] in participants],
             'relations': relations},
            {'assessments': {'type': 'array', 'minItems': len(relations),
                'maxItems': len(relations), 'items': {'type': 'object', 'properties': {
                    'memberId': {'type': 'string', 'enum': list(assigned)},
                    'representativeId': {'type': 'string', 'enum': list(dict.fromkeys(assigned.values()))},
                    'coverage': {'type': 'string', 'enum': list(_COVERAGE)}},
                    'required': ['memberId', 'representativeId', 'coverage'],
                    'additionalProperties': False}}})
        solar = model == 'solar-pro4'
        analyzer = (SolarAnalyzer(key, transport=transport or post_solar) if solar else
                    NvidiaAnalyzer(key, model=model, transport=transport or post_nvidia))
        trace = {}
        row = {'stage': 'feature_relations', 'candidate_count': len(candidates),
               'relation_count': len(relations), 'server_covered_count': len(partition['groups']),
               'unrepresented_count': len(partition['unrepresentedIds']), 'validated': False}
        try:
            reply, actual_model, _, _ = analyzer._send_payload(
                payload, ('assessments',), timeout=600, _trace=trace)
            if not (actual_model.startswith('solar-pro4') if solar else actual_model == model):
                raise AnalysisError('PROVIDER_MODEL')
            statuses = _validate_assessments(reply, relations)
            row.update({name + '_count': sum(value == name for value in statuses.values())
                        for name in _COVERAGE})
            row['validated'] = True
        except AnalysisError as error:
            row['error'] = safe_code(error.code)
            raise
        except ValueError:
            row['error'] = 'INVALID_FEATURE_RELATIONS'
            raise
        finally:
            if call_trace is not None:
                for name in ('model', 'finish_reason', 'prompt_tokens', 'completion_tokens',
                             'provider_elapsed_ms', 'request_bytes', 'response_bytes'):
                    row[name] = trace.get(name)
                call_trace.append(row)
    uncovered = set(partition['unrepresentedIds']) | {
        member for member, status in statuses.items() if status != 'covered'}
    result = {**partition, 'checkedCandidateIds': [item['id'] for item in candidates],
              'uncoveredIds': [item['id'] for item in candidates if item['id'] in uncovered]}
    validate_feature_curation(document, frozen, reviewed_labels, result)
    return result
