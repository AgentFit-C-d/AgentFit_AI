"""Bounded candidate provenance without source values or model responses."""
from copy import deepcopy
import hashlib
import json
import re

from agentfit_ai.candidate_confirmation import CONTRACT, _checked_result
from agentfit_ai.candidate_review_dispositions import REVIEW_CONTRACT
from agentfit_ai.candidate_first_profile import validate_candidate_labels
from agentfit_ai.operation_candidates import _validate_frozen
from agentfit_ai.profile import ARRAY_FIELDS, FIELDS, MAX_ARRAY_ITEMS, MAX_TEXT_CODE_POINTS, check_profile_snapshot

VERSION = 'candidate-provenance-trace-v1'
STAGES = ('grounded', 'classified', 'reviewed', 'projected')
MAX_TRACE_BYTES = 2 * 1024 * 1024
_ANALYSIS_KEYS = {'outcome', 'candidateCount', 'rejectedCandidateCount', 'unresolvedFields',
                  'reviewIssueCount', 'featureCuration', 'confirmationScope', 'allFieldsReasons'}


def _require(condition):
    if not condition:
        raise ValueError('INVALID_CANDIDATE_TRACE')


def _count(value, maximum=100_000):
    return type(value) is int and 0 <= value <= maximum


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def _same(left, right):
    # JSON distinguishes bool/int and rejects non-JSON values; Python equality does not.
    return _encoded(left) == _encoded(right)


def _identity(document, document_id):
    _require(type(document) is str and bool(document.strip()) and len(document) <= 100_000)
    _require(type(document_id) is str and re.fullmatch(r'PUBLIC-[0-9]{2}', document_id) is not None)
    return hashlib.sha256(document.encode('utf-8')).hexdigest()


def _label_data(document, frozen, selections):
    validate_candidate_labels(frozen, selections)
    _require(all(type(item) is dict and set(item) == {'id', 'field', 'status'} for item in selections))
    by_id = {item['id']: item for item in frozen['candidates']}
    details = {}
    for field in FIELDS:
        selected = [by_id[label['id']] for label in selections
                    if label['field'] == field and label['status'] == 'confirmed']
        values = [document[item['start']:item['end']] for item in selected]
        details[field] = {'confirmedCount': len(selected), 'uniqueCount': len(set(values)),
            'overlengthIds': [item['id'] for item, value in zip(selected, values)
                              if len(value) > MAX_TEXT_CODE_POINTS],
            'blankIds': [item['id'] for item, value in zip(selected, values) if not value.strip()]}
    return {'labels': deepcopy(selections), 'fields': details}


def _profile_data(profile):
    fields = {}
    for field in FIELDS:
        value = profile['data'][field]
        state = 'null' if value is None else 'empty' if value == [] else 'present'
        fields[field] = {'state': state,
                         'valueCount': 0 if value is None else len(value) if type(value) is list else 1,
                         'evidence': [{'start': span['start'], 'end': span['end']}
                                      for span in profile['evidence'][field]]}
    return {'fields': fields}


def _scope(result):
    reasons = []
    if result['rejectedCandidateCount']:
        reasons.append('REJECTED_CANDIDATES')
    if not result['candidateCount']:
        reasons.append('NO_CANDIDATES')
    if result['outcome'] == 'needs_confirmation' and not result['unresolvedFields']:
        reasons.append('UNLOCALIZED_ISSUE')
    return {'confirmationScope': 'all_fields' if reasons else 'reported_fields',
            'allFieldsReasons': reasons}


def _analysis_data(result):
    return {**{name: deepcopy(result[name]) for name in (
        'outcome', 'candidateCount', 'rejectedCandidateCount', 'unresolvedFields', 'reviewIssueCount')},
        'featureCuration': deepcopy(result.get('featureCuration')), **_scope(result)}


def _check_projection(document, value):
    _require(type(value) is dict and set(value) == {'fields'})
    _require(type(value['fields']) is dict and set(value['fields']) == set(FIELDS))
    for field, record in value['fields'].items():
        _require(type(record) is dict and set(record) == {'state', 'valueCount', 'evidence'})
        state, count, spans = record['state'], record['valueCount'], record['evidence']
        _require(type(state) is str and state in ('null', 'empty', 'present'))
        _require(_count(count, MAX_ARRAY_ITEMS if field in ARRAY_FIELDS else 1))
        _require((state == 'present') == (count > 0))
        _require(state != 'empty' or field in ARRAY_FIELDS)
        _require(type(spans) is list and len(spans) <= 10_000)
        _require((state == 'null') == (not spans))
        for span in spans:
            _require(type(span) is dict and set(span) == {'start', 'end'})
            _require(type(span['start']) is int and type(span['end']) is int
                     and 0 <= span['start'] < span['end'] <= len(document))


def _check_analysis(value, grounded):
    _require(type(value) is dict and set(value) == _ANALYSIS_KEYS)
    _require(type(value['outcome']) is str and value['outcome'] in ('candidate_profile', 'needs_confirmation'))
    for name in ('candidateCount', 'rejectedCandidateCount', 'reviewIssueCount'):
        _require(_count(value[name], 240 if name == 'candidateCount' else 100_000))
    _require(value['candidateCount'] == len(grounded['candidates']))
    _require(value['rejectedCandidateCount'] == grounded['rejectedCount'])
    unresolved = value['unresolvedFields']
    _require(type(unresolved) is list and all(type(field) is str and field in FIELDS for field in unresolved))
    _require(len(unresolved) == len(set(unresolved)))
    if value['outcome'] == 'candidate_profile':
        _require(value['candidateCount'] > 0 and not unresolved
                 and value['rejectedCandidateCount'] == 0 and value['reviewIssueCount'] == 0)
    curation = value['featureCuration']
    if curation is not None:
        _require(type(curation) is dict and set(curation) == {'candidateCount', 'selectedCount', 'uncoveredCount'})
        _require(all(_count(number, 240) for number in curation.values()))
        _require(curation['candidateCount'] <= value['candidateCount'])
        _require(curation['selectedCount'] <= min(MAX_ARRAY_ITEMS, curation['candidateCount']))
        _require(curation['uncoveredCount'] <= min(curation['candidateCount'], value['reviewIssueCount']))
        _require(not curation['uncoveredCount'] or 'features' in unresolved)
    _require(_same({key: value[key] for key in ('confirmationScope', 'allFieldsReasons')}, _scope(value)))


def validate_trace(document: str, document_id: str, value: dict) -> dict:
    """Validate shape, source identity and observable facts; not semantic correctness."""
    try:
        digest = _identity(document, document_id)
        _require(type(value) is dict and set(value) == {
            'version', 'documentId', 'sourceSha256', 'status', 'stages', 'analysis'})
        _require(value['version'] == VERSION and value['documentId'] == document_id and value['sourceSha256'] == digest)
        _require(len(_encoded(value)) <= MAX_TRACE_BYTES)
        stages = value['stages']
        _require(type(stages) is dict and set(stages) == set(STAGES))
        missing = False
        frozen = None
        for stage in STAGES:
            record = stages[stage]
            if record is None:
                missing = True
                continue
            _require(not missing)
            if stage == 'grounded':
                _require(type(record) is dict and set(record) == {'candidates', 'rejectedCount'})
                _require(_count(record['rejectedCount']))
                frozen = {'candidates': record['candidates'], 'rejected': []}
                _validate_frozen(document, frozen)
            elif stage in ('classified', 'reviewed'):
                _require(type(record) is dict and set(record) == {'labels', 'fields'})
                _require(_same(record, _label_data(document, frozen, record['labels'])))
            else:
                _check_projection(document, record)
        analysis = value['analysis']
        if analysis is not None:
            _require(not missing)
            _check_analysis(analysis, stages['grounded'])
        expected_status = 'complete' if not missing and analysis is not None else 'partial'
        _require(type(value['status']) is str and value['status'] == expected_status)
        return deepcopy(value)
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError, OverflowError):
        raise ValueError('INVALID_CANDIDATE_TRACE') from None


class CandidateTrace:
    def __init__(self, document: str, document_id: str, *, contract=CONTRACT):
        _require(contract in (CONTRACT, REVIEW_CONTRACT))
        self._contract = contract
        digest = _identity(document, document_id)
        self._document, self._document_id = document, document_id
        self._frozen = None
        self._value = {'version': VERSION, 'documentId': document_id, 'sourceSha256': digest,
                       'status': 'partial', 'stages': dict.fromkeys(STAGES), 'analysis': None}

    def observe(self, stage: str, state: dict) -> None:
        try:
            _require(type(stage) is str and stage in STAGES and self._value['analysis'] is None)
            current = self._value['stages']
            _require(current[stage] is None and all(current[name] is not None for name in STAGES[:STAGES.index(stage)]))
            if stage == 'grounded':
                _validate_frozen(self._document, state)
                record = {'candidates': deepcopy(state['candidates']), 'rejectedCount': len(state['rejected'])}
            elif stage in ('classified', 'reviewed'):
                _require(type(state) is dict and set(state) == {'frozen', 'labels'})
                _require(_same(state['frozen'], self._frozen))
                record = _label_data(self._document, self._frozen, state['labels'])
            else:
                profile = check_profile_snapshot(self._document, self._document_id, state)
                record = _profile_data(profile)
            proposed = deepcopy(self._value)
            proposed['stages'][stage] = record
            checked = validate_trace(self._document, self._document_id, proposed)
            if stage == 'grounded':
                self._frozen = deepcopy(state)
            self._value = checked
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError, OverflowError):
            raise ValueError('INVALID_CANDIDATE_TRACE') from None

    def finish(self, result: dict) -> None:
        try:
            _require(self._value['analysis'] is None and self._value['stages']['projected'] is not None)
            profile = _checked_result(self._document, self._document_id, result, self._contract)
            _require(_same(_profile_data(profile), self._value['stages']['projected']))
            proposed = deepcopy(self._value)
            proposed.update(status='complete', analysis=_analysis_data(result))
            self._value = validate_trace(self._document, self._document_id, proposed)
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError, OverflowError):
            raise ValueError('INVALID_CANDIDATE_TRACE') from None

    def summary(self) -> dict:
        return deepcopy(self._value)
