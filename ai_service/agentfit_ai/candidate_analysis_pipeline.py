"""Opt-in integration of source candidates, semantic review and feature curation."""

from .candidate_first_profile import CandidateContractError
from .operation_candidates import _validate_frozen


def _merge_occurrences(document, *sets):
    """Merge unclassified spans; certainty is decided once after deduplication."""
    if not sets:
        raise ValueError('missing candidate sets')
    positions, rejected = set(), []
    for frozen in sets:
        _validate_frozen(document, frozen)
        positions.update((item['start'], item['end']) for item in frozen['candidates'])
        if len(positions) > 240:
            raise CandidateContractError('CANDIDATE_OCCURRENCE_LIMIT')
        rejected.extend({'index': len(rejected), 'reason': item['reason']}
                        for item in frozen['rejected'])
    return {'candidates': [{'id': f'C{index:03}', 'start': start, 'end': end}
                           for index, (start, end) in enumerate(sorted(positions))],
            'rejected': rejected}
