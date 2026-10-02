"""Never makes network calls. Used only by offline supervisor tests."""
import json
import os
from pathlib import Path
import sys
from time import monotonic, sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagnostic_tools import document_profile_live as live

mode, output, deadline = sys.argv[1], Path(sys.argv[2]), float(sys.argv[3])
if mode == 'replay':
    from test_document_profile_v3_observer import observed_replay
    with observed_replay():
        live.child(output, deadline)
else:
    from review_preservation_fixture import offline
    with offline():
        raw = json.loads(sys.stdin.buffer.read())
        assert raw['mode'] == 'integrated-nvidia' and raw['contract'] == 'confirmation-v3'
        row = {'index': 1, 'model': live.MODEL,
            'state': 'started', 'pid': os.getpid(), 'requestDeadlineMonotonic':
                monotonic()+.3 if mode == 'request-timeout' else deadline+100}
        live.save(output/'request-journal.json', [row])
        live.save(output/'deadline-001.json', row)
        live.save(output/'active-request.json', {'synthetic': True, 'state': 'started'})
        live.save(output/'trace-checkpoint.json', {'status': 'partial', 'stages': {}, 'calls': []})
        sleep(60)
        raise AssertionError('supervisor failed to terminate request')
