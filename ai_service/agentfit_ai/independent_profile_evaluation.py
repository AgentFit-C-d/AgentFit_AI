"""Preregistered literal grounding counts, never a semantic release verdict."""
import hashlib

from .candidate_confirmation import validate_candidate_confirmation
from .diagnostics import SAFE_CODES
from .independent_evaluation_corpus import validate_gold, verify_corpus
from .profile import FIELDS


def _positions(spans):
    return {(s['start'], s['end']) for s in spans}


def _occurrences(document, value, spans):
    if value is None:  # The caller maps an explicit empty array to this sentinel.
        found = _positions(spans)
        return (set(), True) if len(found) > 128 else (found, False)
    found = set()
    for start, end in _positions(spans):
        cursor = start
        while (at := document.find(value, cursor, end)) >= 0:
            found.add((at, at + len(value)))
            if len(found) > 128:
                return set(), True
            cursor = at + 1
    return found, False


def _classification(field, empty, positions, gold, matched):
    uncertain = set().union(*(_positions(r['spans']) for r in gold['ambiguities'] if field in r['fields']))
    if not positions or uncertain & positions:
        return 'unassessed', None
    units = {unit['id']: _positions(unit['spans']) for unit in gold['fields'][field]['units']
             if unit['kind'] == ('explicit_absence' if empty else 'present')}
    candidates = [ident for ident, allowed in units.items() if positions <= allowed]
    if len(candidates) == 1:
        ident = candidates[0]
        if ident in matched:
            return 'duplicate', ident
        matched.add(ident)
        return 'matched', ident
    wrong = set().union(*(_positions(r['spans']) for r in gold['exclusions'] if field in r['fields']))
    # Fields can overlap semantically. Registration elsewhere is not a negative
    # label here; only a preregistered exclusion establishes a known error.
    valid_here = set().union(*units.values())
    if not empty and not positions & valid_here and positions <= wrong:
        return 'known_wrong', None
    return 'unassessed', None


def score_confirmation(document: str, document_id: str, gold: dict, outcome: dict) -> dict:
    """Keep failures and unmatched outputs visible without persisting their text."""
    gold = validate_gold(document, gold)
    if type(document_id) is not str or document_id != gold['case_id']:
        raise ValueError('INVALID_GOLD')
    fields = {f: {'assessment': gold['fields'][f]['assessment'], 'gold': len(gold['fields'][f]['units']),
                  'produced': 0, 'matched': 0, 'missing': len(gold['fields'][f]['units']),
                  'known_wrong': 0, 'duplicates': 0, 'unassessed': 0} for f in FIELDS}
    result = {'version': 'independent-profile-score-v1', 'status': 'invalid', 'error': 'INVALID_EVALUATION_OUTCOME',
              'human_reviewed': False, 'release_gate_passed': False, 'evidence_invalid': 1, 'questions': 0,
              'field_states': {'suggested': 0, 'unknown': 0, 'unresolved': 0}, 'fields': fields, 'items': []}
    if (type(outcome) is dict and set(outcome) == {'contract', 'outcome', 'error'}
            and outcome['contract'] == 'confirmation-v2' and outcome['outcome'] == 'failed'
            and type(outcome['error']) is str and outcome['error'] in SAFE_CODES | {'ANALYSIS_FAILURE'}):
        return {**result, 'status': 'failed', 'error': outcome['error'], 'evidence_invalid': 0}
    try:
        checked = validate_candidate_confirmation(document, document_id, outcome)
    except (ValueError, TypeError, KeyError):
        return result
    result.update(status='valid', error='REVIEW_CONFIRMATION_REQUIRED', evidence_invalid=0,
                  questions=len(checked['questions']))
    matched = set()
    for field in FIELDS:
        result['field_states'][checked['fieldStates'][field]] += 1
        value = checked['profile']['data'][field]
        if value is None:
            continue
        values = [None] if value == [] else value if type(value) is list else [value]
        for index, item in enumerate(values):
            positions, overflow = _occurrences(document, item, checked['profile']['evidence'][field])
            classification, ident = _classification(field, item is None, positions, gold, matched)
            fields[field]['produced'] += 1
            fields[field]['duplicates' if classification == 'duplicate' else classification] += 1
            result['items'].append({'field': field, 'index': index,
                                    'value_sha256': hashlib.sha256(item.encode('utf-8')).hexdigest() if item is not None else None,
                                    'occurrences': [{'start': s, 'end': e} for s, e in sorted(positions)],
                                    'occurrence_overflow': overflow, 'classification': classification, 'unit_id': ident})
        fields[field]['missing'] -= fields[field]['matched']
    return result
