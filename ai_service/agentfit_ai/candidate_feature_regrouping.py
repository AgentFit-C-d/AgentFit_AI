"""Attempt one source-preserving repair of unresolved feature groups."""
import copy

from .candidate_feature_curation import (
    _feature_candidates, _propose_feature_partition, validate_feature_curation)
from .candidate_feature_relations import review_feature_relations
from .deepseek_evaluation import MODEL, NVIDIA_REVIEW_MODELS


def _assignments(partition):
    assigned = {member: None for member in partition['unrepresentedIds']}
    assigned.update({member: group['representativeId']
                     for group in partition['groups'] for member in group['memberIds']})
    return assigned


def repair_feature_curation(document, frozen, reviewed_labels, curation, key, *,
                            model=MODEL, transport=None, call_trace=None):
    """Return a copied, validated receipt after at most one regroup-and-review."""
    if (type(key) is not str or not key.strip() or
            type(model) is not str or model not in ('solar-pro4', *NVIDIA_REVIEW_MODELS) or
            (transport is not None and not callable(transport)) or
            (call_trace is not None and type(call_trace) is not list)):
        raise ValueError('invalid feature regrouping options')
    summary = validate_feature_curation(document, frozen, reviewed_labels, curation)
    previous = copy.deepcopy(curation)
    previous['uncoveredIds'] = summary['uncoveredIds']
    if not previous['uncoveredIds']:
        return previous
    candidates = _feature_candidates(document, frozen, reviewed_labels)
    partition = _propose_feature_partition(document, candidates, key,
        model=model, transport=transport, call_trace=call_trace, previous_curation=previous)
    if _assignments(previous) == _assignments(partition):
        return previous
    return review_feature_relations(document, frozen, reviewed_labels, partition, key,
        model=model, transport=transport, call_trace=call_trace)
