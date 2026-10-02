"""Preserve grounded candidate proposals under an explicit confirmation contract."""
from copy import deepcopy

from .profile import FIELDS, MAX_ARRAY_ITEMS, check_profile_snapshot
from .semantic_confirmation_metadata import (
    check_decision_profile, unassigned_decision_questions, check_unassigned_questions,
)
from .candidate_review_dispositions import REVIEW_CONTRACT, check_review_dispositions


CONTRACT = 'confirmation-v2'
_RESULT_KEYS = frozenset(('outcome', 'profile', 'unresolvedFields', 'rejectedCandidateCount',
                          'candidateCount', 'rejectedReasons', 'reviewIssueCount'))
_DRAFT_KEYS = frozenset(('contract', 'outcome', 'profile', 'fieldStates', 'questions', 'error'))
_STATES = frozenset(('suggested', 'unknown', 'unresolved'))
_UNRESOLVED_REASONS = frozenset(('REVIEW_ISSUE', 'CANDIDATE_MISSING'))


def _count(value):
    return type(value) is int and value >= 0


def _checked_result(document, document_id, result, contract=CONTRACT):
    extra = {'reviewDispositions'} if contract == REVIEW_CONTRACT else set()
    if (type(result) is not dict or set(result) - {'featureCuration', 'modelDecisions'} - extra != _RESULT_KEYS
            or type(result['outcome']) is not str
            or result['outcome'] not in ('candidate_profile', 'needs_confirmation')):
        raise ValueError('invalid candidate result')
    unresolved = result['unresolvedFields']
    if (type(unresolved) is not list or
            any(type(field) is not str or field not in FIELDS for field in unresolved) or
            len(unresolved) != len(set(unresolved)) or
            not all(_count(result[name]) for name in ('candidateCount', 'rejectedCandidateCount', 'reviewIssueCount')) or
            result['candidateCount'] > 240):
        raise ValueError('invalid candidate metadata')
    reasons = result['rejectedReasons']
    if (type(reasons) is not dict or
            any(type(name) is not str or not name.strip() or not _count(count) or count == 0
                for name, count in reasons.items()) or
            sum(reasons.values()) != result['rejectedCandidateCount']):
        raise ValueError('invalid candidate rejection metadata')
    if 'featureCuration' in result:
        curation = result['featureCuration']
        if (type(curation) is not dict or
                set(curation) != {'candidateCount', 'selectedCount', 'uncoveredCount'} or
                not all(_count(count) for count in curation.values()) or
                curation['candidateCount'] > result['candidateCount'] or
                curation['selectedCount'] > min(MAX_ARRAY_ITEMS, curation['candidateCount']) or
                curation['uncoveredCount'] > curation['candidateCount'] or
                curation['uncoveredCount'] > result['reviewIssueCount'] or
                (curation['uncoveredCount'] and 'features' not in unresolved)):
            raise ValueError('invalid candidate curation metadata')
    if (result['outcome'] == 'candidate_profile' and
            (unresolved or result['rejectedCandidateCount'] or result['reviewIssueCount'] or
             result['candidateCount'] == 0)):
        raise ValueError('contradictory candidate result')
    profile = check_profile_snapshot(document, document_id, result['profile'])
    if 'modelDecisions' in result:
        records = check_decision_profile(profile, result['modelDecisions'], document=document, document_id=document_id)
        if len(records) != result['candidateCount']:
            raise ValueError('invalid semantic candidate count')
    if contract == REVIEW_CONTRACT:
        if not {'modelDecisions', 'reviewDispositions'} <= set(result):
            raise ValueError('missing review dispositions')
        check_review_dispositions(profile, records, result['reviewDispositions'])
    if result['candidateCount'] == 0 and any(value is not None for value in profile['data'].values()):
        raise ValueError('empty candidates contradict profile')
    return profile


def project_candidate_confirmation(document, document_id, result, *, contract=CONTRACT) -> dict:
    """Map a completed pipeline result to suggestions; never approve or persist it."""
    if contract not in (CONTRACT, REVIEW_CONTRACT):
        raise ValueError('invalid candidate confirmation contract')
    profile = _checked_result(document, document_id, result, contract)
    unresolved = set(result['unresolvedFields'])
    records = result.get('modelDecisions', [])
    unassigned = unassigned_decision_questions(records)
    only_unassigned = (bool(unassigned) and result['reviewIssueCount'] ==
                       sum(r['decision'] == 'needs_confirmation' for r in records))
    if (result['rejectedCandidateCount'] or not result['candidateCount'] or
            (result['outcome'] == 'needs_confirmation' and not unresolved and not only_unassigned)):
        unresolved = set(FIELDS)
    states, questions = {}, []
    for field in FIELDS:
        state = ('unresolved' if field in unresolved else
                 'unknown' if profile['data'][field] is None else 'suggested')
        states[field] = state
        if state != 'unknown':
            reason = ('CONFIRM_SUGGESTION' if state == 'suggested' else
                      'CANDIDATE_MISSING' if not result['candidateCount'] else 'REVIEW_ISSUE')
            questions.append({'field': field, 'reason': reason, 'questionId': 'confirm_' + field})
    metadata = ({'modelDecisions': check_decision_profile(profile, result['modelDecisions'],
                 document=document, document_id=document_id, states=states)} if 'modelDecisions' in result else {})
    if unassigned:
        metadata['unassignedQuestions'] = unassigned
    if contract == REVIEW_CONTRACT:
        metadata['reviewDispositions'] = result['reviewDispositions']
    return validate_candidate_confirmation(document, document_id, {
        'contract': contract, 'outcome': 'needs_confirmation', 'profile': profile,
        'fieldStates': states, 'questions': questions, 'error': 'REVIEW_CONFIRMATION_REQUIRED', **metadata}, contract=contract)


def validate_candidate_confirmation(document, document_id, outcome, *, contract=CONTRACT) -> dict:
    """Validate the explicitly selected boundary, defaulting to unchanged v2."""
    extra = {'reviewDispositions'} if contract == REVIEW_CONTRACT else set()
    if (contract not in (CONTRACT, REVIEW_CONTRACT) or type(outcome) is not dict or
            set(outcome) - {'modelDecisions', 'unassignedQuestions'} - extra != _DRAFT_KEYS or
            outcome['contract'] != contract or outcome['outcome'] != 'needs_confirmation' or
            outcome['error'] != 'REVIEW_CONFIRMATION_REQUIRED'):
        raise ValueError('invalid candidate confirmation contract')
    profile = check_profile_snapshot(document, document_id, outcome['profile'])
    states, questions = outcome['fieldStates'], outcome['questions']
    if (type(states) is not dict or set(states) != set(FIELDS) or
            any(type(state) is not str or state not in _STATES for state in states.values()) or
            type(questions) is not list or len(questions) > len(FIELDS)):
        raise ValueError('invalid candidate confirmation states')
    if any((state == 'suggested' and profile['data'][field] is None) or
           (state == 'unknown' and profile['data'][field] is not None)
           for field, state in states.items()):
        raise ValueError('candidate confirmation contradicts profile')
    seen = set()
    for question in questions:
        if type(question) is not dict or set(question) != {'field', 'reason', 'questionId'}:
            raise ValueError('invalid candidate confirmation question')
        field, reason = question['field'], question['reason']
        if (type(field) is not str or field not in FIELDS or field in seen or
                type(reason) is not str or question['questionId'] != 'confirm_' + field):
            raise ValueError('invalid candidate confirmation question')
        if not ((states[field] == 'suggested' and reason == 'CONFIRM_SUGGESTION') or
                (states[field] == 'unresolved' and reason in _UNRESOLVED_REASONS)):
            raise ValueError('candidate confirmation question contradicts state')
        seen.add(field)
    if seen != {field for field in FIELDS if states[field] != 'unknown'}:
        raise ValueError('missing candidate confirmation question')
    metadata = {}
    if 'modelDecisions' in outcome:
        metadata['modelDecisions'] = check_decision_profile(profile, outcome['modelDecisions'], document=document,
                                                           document_id=document_id, states=states)
        check_unassigned_questions(metadata['modelDecisions'], outcome.get('unassignedQuestions', []))
    elif 'unassignedQuestions' in outcome:
        raise ValueError('unassigned questions require model decisions')
    if contract == REVIEW_CONTRACT:
        if not {'modelDecisions', 'reviewDispositions'} <= set(outcome):
            raise ValueError('missing review dispositions')
        metadata['reviewDispositions'] = check_review_dispositions(
            profile, metadata['modelDecisions'], outcome['reviewDispositions'], states=states)
    return deepcopy({**outcome, 'profile': profile, **metadata})
