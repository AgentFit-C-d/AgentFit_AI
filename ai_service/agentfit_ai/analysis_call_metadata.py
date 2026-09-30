"""Strict bounded call metadata. Never accepts source, response text, or secrets."""
from copy import deepcopy

from .diagnostics import PIPELINE_FAILURE_CODES, SAFE_CODES

METADATA_VERSION = 'analysis-call-metadata-v1'
MODELS = frozenset(('deepseek-ai/deepseek-v4.1-flash', 'z-ai/glm-5.3'))
REASONS = frozenset(('NOT_RETURNED', 'ANALYSIS_WORKER_FAILED', 'ANALYSIS_DEADLINE_EXCEEDED'))
ROW_KEYS = frozenset(('stage', 'provider', 'requested_model', 'call_index', 'elapsed_ms',
                     'response_bytes', 'transport_completed', 'attempt',
                     'retry_of_call_index', 'provider_error'))


def validate_metadata(value):
    try:
        if (type(value) is not dict or set(value) != {'version', 'status', 'unavailableReason', 'failureStage', 'calls'}
                or value['version'] != METADATA_VERSION or type(value['status']) is not str
                or type(value['calls']) is not list or len(value['calls']) > 64):
            raise ValueError
        stage, reason, calls = value['failureStage'], value['unavailableReason'], value['calls']
        if value['status'] == 'unavailable':
            if type(reason) is not str or reason not in REASONS or stage is not None or calls:
                raise ValueError
        elif value['status'] == 'available':
            if reason is not None or (stage is not None and (type(stage) is not str or stage not in PIPELINE_FAILURE_CODES)):
                raise ValueError
        else:
            raise ValueError
        for index, row in enumerate(calls, 1):
            if (type(row) is not dict or set(row) != ROW_KEYS
                    or type(row['stage']) is not str or row['stage'] not in PIPELINE_FAILURE_CODES
                    or row['provider'] != 'nvidia' or type(row['requested_model']) is not str
                    or row['requested_model'] not in MODELS or type(row['call_index']) is not int
                    or row['call_index'] != index or type(row['elapsed_ms']) is not int
                    or not 0 <= row['elapsed_ms'] <= 3_600_000
                    or type(row['transport_completed']) is not bool
                    or type(row['attempt']) is not int or row['attempt'] != 1
                    or row['retry_of_call_index'] is not None):
                raise ValueError
            size, error = row['response_bytes'], row['provider_error']
            if row['transport_completed']:
                if type(size) is not int or not 0 <= size <= 1_000_000_000 or error is not None:
                    raise ValueError
            elif size is not None:
                raise ValueError
            if error is not None:
                if (type(error) is not str or error not in SAFE_CODES or row['transport_completed']
                        or index != len(calls) or stage != row['stage']):
                    raise ValueError
        return deepcopy(value)
    except (ValueError, TypeError, KeyError, RecursionError):
        raise ValueError('INVALID_CALL_METADATA') from None


def unavailable_metadata(reason):
    return validate_metadata({'version': METADATA_VERSION, 'status': 'unavailable',
        'unavailableReason': reason, 'failureStage': None, 'calls': []})


def build_metadata(calls, failure_stage=None):
    return validate_metadata({'version': METADATA_VERSION, 'status': 'available',
        'unavailableReason': None, 'failureStage': failure_stage, 'calls': calls})
