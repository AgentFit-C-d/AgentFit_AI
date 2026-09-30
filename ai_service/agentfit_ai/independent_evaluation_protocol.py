"""Strict, content-free boundary for scored worker and checkpoint output."""
from copy import deepcopy
import hashlib
import re

from .diagnostics import SAFE_CODES
from .independent_evaluation_corpus import validate_gold
from .independent_profile_evaluation import _classification
from .profile import ARRAY_FIELDS, FIELDS

SCORE_KEYS = frozenset(('version', 'status', 'error', 'human_reviewed', 'release_gate_passed',
                         'evidence_invalid', 'questions', 'field_states', 'fields', 'items'))
COUNTS = ('produced', 'matched', 'missing', 'known_wrong', 'duplicates', 'unassessed')


def _count(value, limit=155):
    return type(value) is int and 0 <= value <= limit


def validate_score(document: str, gold: dict, score: dict) -> dict:
    """Validate grounded counts; syntax validation cannot prove semantic quality."""
    try:
        gold = validate_gold(document, gold)
        if (type(score) is not dict or set(score) != SCORE_KEYS
                or score['version'] != 'independent-profile-score-v1'
                or type(score['status']) is not str or score['status'] not in ('valid', 'failed', 'invalid')
                or score['human_reviewed'] is not False or score['release_gate_passed'] is not False
                or not _count(score['evidence_invalid'], 1) or not _count(score['questions'], 10)
                or type(score['error']) is not str
                or type(score['field_states']) is not dict
                or set(score['field_states']) != {'suggested', 'unknown', 'unresolved'}
                or not all(_count(n, 10) for n in score['field_states'].values())
                or type(score['fields']) is not dict or set(score['fields']) != set(FIELDS)
                or type(score['items']) is not list or len(score['items']) > 155):
            raise ValueError
        status = score['status']
        expected_error = {'valid': {'REVIEW_CONFIRMATION_REQUIRED'},
                          'invalid': {'INVALID_EVALUATION_OUTCOME'},
                          'failed': SAFE_CODES | {'ANALYSIS_FAILURE'}}[status]
        if score['error'] not in expected_error or score['evidence_invalid'] != int(status == 'invalid'):
            raise ValueError
        calculated = {f: dict.fromkeys(('produced', 'matched', 'known_wrong', 'duplicates', 'unassessed'), 0) for f in FIELDS}
        matched, empty_fields = set(), set()
        for item in score['items']:
            if (type(item) is not dict or set(item) != {'field', 'index', 'value_sha256', 'occurrences',
                                                       'occurrence_overflow', 'classification', 'unit_id'}
                    or type(item['field']) is not str or item['field'] not in FIELDS
                    or type(item['index']) is not int or type(item['occurrence_overflow']) is not bool
                    or type(item['occurrences']) is not list or len(item['occurrences']) > 128):
                raise ValueError
            field, digest = item['field'], item['value_sha256']
            counts = calculated[field]
            if item['index'] != counts['produced'] or item['index'] >= (30 if field in ARRAY_FIELDS else 1):
                raise ValueError
            if digest is None:
                if field not in ARRAY_FIELDS or item['index'] != 0:
                    raise ValueError
                empty_fields.add(field)
            elif type(digest) is not str or re.fullmatch('[0-9a-f]{64}', digest) is None or field in empty_fields:
                raise ValueError
            positions = set()
            for span in item['occurrences']:
                if type(span) is not dict or set(span) != {'start', 'end'}:
                    raise ValueError
                start, end = span['start'], span['end']
                if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(document)
                        or (start, end) in positions):
                    raise ValueError
                if digest is not None and (end - start > 200 or hashlib.sha256(document[start:end].encode()).hexdigest() != digest):
                    raise ValueError
                positions.add((start, end))
            if (item['occurrence_overflow'] and positions) or (not item['occurrence_overflow'] and not positions):
                raise ValueError
            category, unit = _classification(field, digest is None, positions, gold, matched)
            if item['classification'] != category or item['unit_id'] != unit:
                raise ValueError
            counts['produced'] += 1
            counts['duplicates' if category == 'duplicate' else category] += 1
        for field, counts in calculated.items():
            given = score['fields'][field]
            total = len(gold['fields'][field]['units'])
            if (type(given) is not dict or set(given) != {'assessment', 'gold', *COUNTS}
                    or given['assessment'] != gold['fields'][field]['assessment']
                    or not all(_count(given[k]) for k in ('gold', *COUNTS))
                    or given['gold'] != total or given['missing'] != total - counts['matched']
                    or any(given[k] != value for k, value in counts.items())):
                raise ValueError
        states = score['field_states']
        if status == 'valid':
            nonnull = sum(bool(f['produced']) for f in calculated.values())
            if (sum(states.values()) != 10 or score['questions'] != states['suggested'] + states['unresolved']
                    or states['suggested'] > nonnull or states['unknown'] > 10 - nonnull):
                raise ValueError
        elif score['items'] or score['questions'] or any(states.values()):
            raise ValueError
        return deepcopy(score)
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError('INVALID_SCORE') from None
