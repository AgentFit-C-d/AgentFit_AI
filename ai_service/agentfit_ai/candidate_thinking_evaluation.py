"""Opt-in same-snapshot DeepSeek thinking comparison; never a service default."""
from copy import deepcopy
import hashlib
import json
import time

from .candidate_first_profile import finalize_candidate_analysis
from .candidate_paired_review import _failure, _field_summaries, _references
from .candidate_review_replay import restore_snapshot
from .candidate_split_review import review_candidates_separately
from .deepseek_evaluation import MODEL
from .diagnostics import safe_code
from .nvidia_streaming import post_nvidia_streaming
from .real_document_holdout import score_profile
from .solar import AnalysisError


class _ObserverFailure(RuntimeError):
    pass


def _safe_calls(calls):
    result = []
    for call in calls:
        row = {name: call[name] for name in (
            'stage', 'batch_index', 'sub_batch_index', 'candidate_count', 'validated',
            'contract_issue') if name in call}
        # Model/finish metadata originates at the provider, not the caller.
        row['model'] = MODEL if call.get('model') == MODEL else None
        finish = call.get('finish_reason')
        row['finish_reason'] = finish if finish in ('stop', 'length', 'content_filter',
            'tool_calls', 'function_call') else None
        for name in ('prompt_tokens', 'completion_tokens', 'provider_elapsed_ms',
                     'request_bytes', 'response_bytes'):
            value = call.get(name)
            row[name] = value if type(value) is int and value >= 0 else None
        if 'error' in call:
            row['error'] = ('INVALID_REVIEW_CONTRACT' if call['error'] == 'INVALID_REVIEW_CONTRACT'
                            else safe_code(call['error']))
        result.append(row)
    return result


def evaluate_thinking_reviews(case, snapshot, key, *, expected_keep,
                              transport=None, on_update=None):
    """Review the same classified occurrences with thinking false then true."""
    if (type(key) is not str or not key.strip() or
            (transport is not None and not callable(transport)) or
            (on_update is not None and not callable(on_update))):
        raise ValueError('invalid thinking evaluation options')
    frozen, labels = restore_snapshot(case, snapshot)
    if key in case.text or key in case.id:
        raise ValueError('sensitive thinking evaluation input')
    ids = {label['id'] for label in labels}
    if (type(expected_keep) is not dict or not expected_keep or
            any(type(item) is not str or item not in ids or type(keep) is not bool
                for item, keep in expected_keep.items())):
        raise ValueError('invalid candidate audit gold')
    expected_keep = dict(expected_keep)
    score_profile({'data': {}}, case.checks)
    per_arm = (sum(label['status'] == 'confirmed' for label in labels) + 19) // 20 + 1
    result = {'state': 'running', 'case_id': case.id, 'held_out': False,
        'source_sha256': case.source_sha256, 'redacted_sha256': case.redacted_sha256,
        'snapshot_sha256': hashlib.sha256(json.dumps(snapshot, sort_keys=True,
            ensure_ascii=False).encode()).hexdigest(), 'review_model': MODEL,
        'candidate_count': len(labels), 'planned_calls': 2 * per_arm,
        'settings': {'temperature': 0, 'max_tokens': 8192, 'timeout_seconds': 600,
                     'batch_size': 20, 'reasoned_review': True,
                     'field_semantics': 'explicit-v1', 'retry_limit': 0},
        'thinking_order': [False, True], 'active_thinking': None, 'arms': [], 'failed': 0}

    def emit():
        result['failed'] = sum(arm['outcome'] == 'failed' for arm in result['arms'])
        if on_update is not None:
            try:
                on_update(deepcopy(result))
            except Exception:
                raise _ObserverFailure('progress observer failed') from None

    emit()
    sender = transport if transport is not None else post_nvidia_streaming
    for thinking in (False, True):
        calls, reasons, reviewed = [], [], {}
        row = {'thinking': thinking, 'outcome': 'running', 'attempted_calls': 0,
               'transport_attempts': [], 'review_calls': [], 'review_reasons': reasons}
        result['arms'].append(row)
        result['active_thinking'] = thinking
        started, stage = time.monotonic(), 'COVERAGE_REVIEW_FAILED'

        def send(payload, api_key, timeout):
            if (payload.get('model') != MODEL or
                    payload.get('chat_template_kwargs') != {'thinking': False} or
                    row['attempted_calls'] >= per_arm):
                raise ValueError('unexpected review request')
            request = deepcopy(payload)
            request['chat_template_kwargs']['thinking'] = thinking
            row['attempted_calls'] += 1
            attempt = {'index': row['attempted_calls'], 'returned': False}
            row['transport_attempts'].append(attempt)
            row['review_calls'] = _safe_calls(calls)
            emit()
            call_start = time.monotonic()
            try:
                raw = sender(request, api_key, timeout)
                attempt['returned'] = True
                return raw
            except AnalysisError as error:
                attempt['error'] = safe_code(error.code)
                raise
            except Exception:
                attempt['error'] = 'ANALYSIS_FAILURE'
                raise
            finally:
                attempt['elapsed_ms'] = round((time.monotonic() - call_start) * 1000)
                emit()

        def observe(stage, state):
            if stage == 'reviewed':
                reviewed.update(state)

        try:
            verdict = review_candidates_separately(case.text, deepcopy(frozen), deepcopy(labels),
                key, review_model=MODEL, field_semantics='explicit-v1', reasoned_review=True,
                transport=send, review_calls=calls, review_reasons=reasons)
            stage = 'PROJECTION_FAILED'
            projected = finalize_candidate_analysis(case.text, case.id, frozen, labels,
                                                     verdict, observer=observe)
            score = score_profile(projected['profile'], case.checks)
            actual = {label['id']: label['status'] == 'confirmed' for label in reviewed['labels']}
            failed = [item for item, keep in expected_keep.items() if actual[item] != keep]
            row.update(outcome=projected['outcome'], verdict=verdict,
                unresolved_fields=projected['unresolvedFields'],
                review_issue_count=projected['reviewIssueCount'],
                reviewed_refs=_references(frozen, reviewed['labels']),
                fields=_field_summaries(case.text, frozen, labels, reviewed['labels'], projected['profile']),
                suggestion_matched=score['matched'], suggestion_checked=score['total'],
                suggestion_failed_check_ids=score['failed_check_ids'],
                audit_matched=len(expected_keep) - len(failed), audit_total=len(expected_keep),
                audit_failed_ids=failed)
        except _ObserverFailure:
            raise
        except Exception as error:
            row.update(_failure(error, stage))
        row['review_elapsed_ms'] = round((time.monotonic() - started) * 1000)
        row['review_calls'] = _safe_calls(calls)
        emit()
    result.update(state='finished', active_thinking=None)
    emit()
    return result
