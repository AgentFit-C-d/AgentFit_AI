"""One real integrated request; only preregistered counts leave the process."""
from contextlib import redirect_stdout
import json
import os
import sys

from .candidate_service_worker import execute_integrated_analysis
from .diagnostics import safe_code
from .independent_evaluation_corpus import validate_gold
from .independent_evaluation_protocol import validate_score
from .independent_profile_evaluation import score_confirmation
from .solar import AnalysisError

MAX_INPUT_BYTES = 1_000_000
MAX_OUTPUT_BYTES = 1_500_000


def validate_request(packet):
    try:
        if type(packet) is not dict or set(packet) != {'document', 'documentId', 'solarKey', 'nvidiaKey', 'gold'}:
            raise ValueError
        validate_gold(packet['document'], packet['gold'])
        if packet['documentId'] != packet['gold']['case_id'] or packet['solarKey'] == packet['nvidiaKey']:
            raise ValueError
        for key in (packet['solarKey'], packet['nvidiaKey']):
            if (type(key) is not str or not key.strip() or len(key) > 4096 or key != key.strip()
                    or any(ord(c) < 32 for c in key) or key in packet['document'] or key in packet['documentId']):
                raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ValueError('INVALID_EVALUATION_INPUT') from None


def execute_request(packet: dict) -> dict:
    validate_request(packet)
    with open(os.devnull, 'w') as sink, redirect_stdout(sink):
        try:
            outcome = execute_integrated_analysis(packet['document'], packet['documentId'],
                                                  packet['solarKey'], packet['nvidiaKey'])
        except AnalysisError as error:
            outcome = {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': safe_code(error.code)}
        except Exception:
            outcome = {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'ANALYSIS_FAILURE'}
    score = score_confirmation(packet['document'], packet['documentId'], packet['gold'], outcome)
    return validate_score(packet['document'], packet['gold'], score)


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError
        score = execute_request(json.loads(raw))
        output = json.dumps(score, separators=(',', ':')).encode('utf-8')
        if len(output) > MAX_OUTPUT_BYTES:
            raise ValueError
    except Exception:
        sys.stdout.buffer.write(b'{"error":"INVALID_EVALUATION_INPUT"}')
        return 1
    sys.stdout.buffer.write(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
