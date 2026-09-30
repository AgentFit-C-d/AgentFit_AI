"""Synthetic child only: no API/network access."""
import json
import os
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agentfit_ai.independent_profile_evaluation import score_confirmation
from tests.test_independent_profile_evaluation import outcome_fixture

packet = json.load(sys.stdin)
mode = sys.argv[1]
if mode == 'hang':
    time.sleep(60)
elif mode == 'oversized':
    sys.stdout.write('x' * 1_500_001)
elif mode == 'malformed':
    sys.stdout.write('private provider response')
elif mode == 'exit':
    sys.stderr.write(packet['solarKey'])
    raise SystemExit(9)
elif mode == 'valid':
    assert packet['solarKey'] not in json.dumps(dict(os.environ))
    assert packet['nvidiaKey'] not in json.dumps(sys.argv)
    result = score_confirmation(packet['document'], packet['documentId'], packet['gold'],
                                outcome_fixture('frontend', ['React'], [(0, 5)]))
    print(json.dumps(result))
