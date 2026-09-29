"""Compare review policies on a verified frozen snapshot, with no extraction calls."""

from copy import deepcopy
import hashlib
import json
import re
import time

from .candidate_field_semantics import field_semantics_instructions
from .candidate_first_profile import finalize_candidate_analysis, validate_candidate_labels
from .candidate_paired_review import (
    REVIEW_MODELS, _failure, _field_summaries, _references, _review_settings,
)
from .candidate_split_review import review_candidates_separately
from .real_document_holdout import score_profile


def restore_snapshot(case, snapshot):
    """Restore only validated IDs/ranges/labels; rejected details are unavailable."""
    if (type(case.text) is not str or not case.text.strip() or len(case.text) > 100_000 or
            type(case.id) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,80}', case.id) is None or
            type(snapshot) is not dict or snapshot.get('state') != 'finished' or
            snapshot.get('case_id') != case.id):
        raise ValueError('invalid review snapshot')
    for key in ('source_sha256', 'redacted_sha256'):
        value = snapshot.get(key)
        if (type(value) is not str or re.fullmatch(r'[0-9a-f]{64}', value) is None or
                value != getattr(case, key)):
            raise ValueError('snapshot source mismatch')
    if hashlib.sha256(case.text.encode('utf-8')).hexdigest() != case.redacted_sha256:
        raise ValueError('snapshot text mismatch')
    refs = snapshot.get('classification_refs')
    count, rejected = snapshot.get('candidate_count'), snapshot.get('rejected_candidate_count')
    if (type(refs) is not list or not 0 <= len(refs) <= 240 or
            type(count) is not int or count != len(refs) or
            type(rejected) is not int or not 0 <= rejected <= 240):
        raise ValueError('invalid snapshot counts')
    candidates, labels, positions = [], [], set()
    for item in refs:
        if (type(item) is not dict or set(item) != {'id', 'start', 'end', 'field', 'status'} or
                type(item['id']) is not str or re.fullmatch(r'C\d{3}', item['id']) is None or
                type(item['start']) is not int or type(item['end']) is not int or
                not 0 <= item['start'] < item['end'] <= len(case.text) or
                not case.text[item['start']:item['end']].strip() or
                (item['start'], item['end']) in positions):
            raise ValueError('invalid snapshot reference')
        positions.add((item['start'], item['end']))
        candidates.append({key: item[key] for key in ('id', 'start', 'end')})
        labels.append({key: item[key] for key in ('id', 'field', 'status')})
    frozen = {'candidates': candidates,
              'rejected': [{'index': index, 'reason': 'snapshot_rejected'} for index in range(rejected)]}
    validate_candidate_labels(frozen, labels)
    return frozen, labels


def evaluate_review_policies(case, snapshot, key, model, *,
                             policies=('legacy', 'explicit-v1'), reviewer=None, on_update=None):
    """Use identical copies and model settings for each sequential review policy."""
    if (type(model) is not str or model not in REVIEW_MODELS or
            type(key) is not str or not key.strip() or
            type(policies) not in (tuple, list) or not 1 <= len(policies) <= 2):
        raise ValueError('invalid replay selection')
    for policy in policies:
        field_semantics_instructions(policy)
    if len(set(policies)) != len(policies):
        raise ValueError('duplicate replay policies')
    if on_update is not None and not callable(on_update):
        raise ValueError('invalid replay observer')
    frozen, labels = restore_snapshot(case, snapshot)
    if key in case.text or key in case.id:
        raise ValueError('sensitive replay input')
    # Validate checks before a provider call. Gold stays outside the requests.
    score_profile({'data': {}}, case.checks)
    result = {'state': 'running', 'case_id': case.id, 'held_out': False,
              'source_sha256': case.source_sha256, 'redacted_sha256': case.redacted_sha256,
              'snapshot_sha256': hashlib.sha256(json.dumps(snapshot, sort_keys=True,
                  ensure_ascii=False).encode('utf-8')).hexdigest(),
              'review_model': model, 'review_settings': _review_settings([model])[model],
              'candidate_count': len(frozen['candidates']),
              'rejected_candidate_count': len(frozen['rejected']),
              'rejected_details_available': False, 'policy_order': list(policies),
              'classification_refs': _references(frozen, labels), 'policies': [], 'failed': 0}

    def emit():
        result['failed'] = sum(row['outcome'] == 'failed' for row in result['policies'])
        if on_update:
            on_update(deepcopy(result))

    emit()
    review = reviewer or review_candidates_separately
    for index, policy in enumerate(policies):
        calls, reviewed = [], {}
        row = {'field_semantics': policy, 'review_calls': calls}
        def observer(stage, state):
            if stage == 'reviewed':
                reviewed.update(state)
        started, stage = time.monotonic(), 'COVERAGE_REVIEW_FAILED'
        try:
            verdict = review(case.text, deepcopy(frozen), deepcopy(labels), key,
                review_model=model, review_calls=calls, adaptive_review=model == 'solar-pro4',
                field_semantics=policy)
            stage = 'PROJECTION_FAILED'
            projected = finalize_candidate_analysis(case.text, case.id, frozen, labels,
                                                     verdict, observer=observer)
            score = score_profile(projected['profile'], case.checks)
            row.update(outcome=projected['outcome'], unresolved_fields=projected['unresolvedFields'],
                       review_issue_count=projected['reviewIssueCount'],
                       reviewed_refs=_references(frozen, reviewed['labels']),
                       fields=_field_summaries(case.text, frozen, labels, reviewed['labels'], projected['profile']),
                       suggestion_matched=score['matched'], suggestion_checked=score['total'],
                       suggestion_failed_check_ids=score['failed_check_ids'])
        except Exception as error:
            row.update(_failure(error, stage))
        row['review_elapsed_ms'] = round((time.monotonic() - started) * 1000)
        result['policies'].append(row)
        if index == len(policies) - 1:
            result['state'] = 'finished'
        emit()
    return result
