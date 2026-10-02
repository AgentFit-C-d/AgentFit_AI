"""Post-review obligations, separate from raw model judgments and user approval."""
from copy import deepcopy

from .semantic_confirmation_metadata import check_decision_profile

REVIEW_CONTRACT = 'confirmation-v3'
REASONS = frozenset(('wrong_field', 'not_current', 'not_product_fact', 'insufficient_evidence'))


def build_review_dispositions(review, reasons):
    """Require the review's exact rejected set and retain its original reason codes."""
    wrong = review['wrongCandidateIds']
    by_id = {}
    for row in reasons:
        if row['id'] in by_id or row['reason'] not in REASONS:
            raise ValueError('INVALID_REVIEW_DISPOSITIONS')
        by_id[row['id']] = row['reason']
    if len(wrong) != len(set(wrong)) or set(wrong) != set(by_id):
        raise ValueError('INVALID_REVIEW_DISPOSITIONS')
    return [{'candidateId': cid, 'disposition': 'needs_confirmation', 'reason': by_id[cid]}
            for cid in wrong]


def check_review_dispositions(profile, records, dispositions, *, states=None):
    """Records must already have passed source/semantic validation at this boundary."""
    if type(dispositions) is not list or len(dispositions) > 240:
        raise ValueError('INVALID_REVIEW_DISPOSITIONS')
    by_id = {r['id']: r for r in records}
    held = set()
    for row in dispositions:
        if (type(row) is not dict or set(row) != {'candidateId', 'disposition', 'reason'} or
                type(row['candidateId']) is not str or row['candidateId'] in held or
                row['candidateId'] not in by_id or row['disposition'] != 'needs_confirmation' or
                type(row['reason']) is not str or row['reason'] not in REASONS):
            raise ValueError('INVALID_REVIEW_DISPOSITIONS')
        record = by_id[row['candidateId']]
        if (record['decision'] != 'supported' or not record['groundingValid'] or
                record['field'] == 'other' or
                (states is not None and states.get(record['field']) != 'unresolved')):
            raise ValueError('INVALID_REVIEW_DISPOSITIONS')
        held.add(row['candidateId'])
    held_positions = {(by_id[cid]['documentId'], by_id[cid]['candidate']['start'],
                       by_id[cid]['candidate']['end']) for cid in held}
    if any((span['documentId'], span['start'], span['end']) in held_positions
           for spans in profile['evidence'].values() for span in spans):
        raise ValueError('REVIEW_HELD_EVIDENCE')
    # Revalidate evidence using only eligible occurrences. The same text at an
    # independent accepted occurrence remains usable, including name expressions.
    check_decision_profile(profile, [r for r in records if r['id'] not in held], states=states)
    return deepcopy(dispositions)
