"""Hash-locked saved responses. All provider and socket access is forbidden."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import socket
from threading import local
from types import SimpleNamespace
from unittest.mock import patch

DIRECTORY = Path(__file__).parent / 'fixtures/review_preservation'


def load(name):
    manifest = json.loads((DIRECTORY / 'manifest.json').read_text(encoding='utf-8'))
    raw = gzip.decompress((DIRECTORY / (name + '.gz')).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == manifest['files'][name], name
    text = raw.decode('utf-8')
    return json.loads(text) if name.endswith('.json') else text


@contextmanager
def offline(*, block_providers=True):
    # Windows asyncio implements its internal wake-up pipe using socketpair.
    # Permit only socketpair construction; all application connections stay blocked.
    connect, pair = socket.socket.connect, socket.socketpair
    state = local()
    def guarded_connect(sock, address):
        if getattr(state, 'internal_pair', False):
            return connect(sock, address)
        raise AssertionError('NETWORK_FORBIDDEN')
    def internal_pair(*args, **kwargs):
        state.internal_pair = True
        try:
            return pair(*args, **kwargs)
        finally:
            state.internal_pair = False
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket, 'connect', guarded_connect))
        stack.enter_context(patch.object(socket, 'socketpair', internal_pair))
        targets = ['socket.socket.connect_ex', 'socket.create_connection']
        if block_providers:
            targets += ['agentfit_ai.candidate_analysis_pipeline.post_nvidia_streaming',
                       'agentfit_ai.candidate_analysis_pipeline.post_solar',
                       'agentfit_ai.candidate_service_worker.post_nvidia_streaming_inline']
        for target in targets:
            stack.enter_context(patch(target, side_effect=AssertionError('NETWORK_FORBIDDEN')))
        yield


@contextmanager
def replay_providers():
    trace = load('trace.json')
    calls = trace['calls'][2:]
    seen = []

    def transport(payload, key, timeout):
        call = calls[len(seen)]
        assert payload == call['request'], 'frozen request changed'
        seen.append(call['index'])
        return call['response']['text'].encode('utf-8')

    def extract(document, key, **kwargs):
        assert document == load('document.txt')
        return [SimpleNamespace(**row) for row in trace['stages']['general_extracted']]

    # The optional SDK is not executed: its already-saved output is the boundary.
    with offline(), patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()), \
            patch('agentfit_ai.langextract_solar_trial.extract_candidates', side_effect=extract), \
            patch('agentfit_ai.candidate_service_worker.post_nvidia_streaming_inline', side_effect=transport):
        yield transport, seen
        assert seen == list(range(3, 26)), seen


def replay(contract='confirmation-v2'):
    from agentfit_ai.candidate_service_worker import execute_nvidia_analysis
    kwargs = {} if contract == 'confirmation-v2' else {'contract': contract}
    with replay_providers():
        return execute_nvidia_analysis(load('document.txt'), load('trace.json')['documentId'],
                                       'OFFLINE-NONCREDENTIAL', semantic_assessment=True, **kwargs)


def synthetic_result(*, independent=False):
    from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
    from agentfit_ai.profile import FIELDS
    document = 'The product does not provide bulk export.'
    if independent:
        document += ' The current product provides bulk export.'
    starts = [document.index('bulk export')]
    if independent:
        starts.append(document.rindex('bulk export'))
    candidates = [{'id': f'C{i:03}', 'start': start, 'end': start + len('bulk export')}
                  for i, start in enumerate(starts)]
    labels = [{'id': c['id'], 'field': 'features', 'status': 'confirmed'} for c in candidates]
    records = [{'id': c['id'], 'mentionKind': 'product_operation', 'field': 'features',
                'modelStatus': 'confirmed', 'scope': 'target', 'time': 'current',
                'polarity': 'positive', 'commitment': 'adopted', 'role': 'product_fact',
                'conflictsChecked': True, 'support': [{'start': 0, 'end': len(document)}],
                'counterEvidence': [], 'candidate': {k: c[k] for k in ('start', 'end')},
                'groundingValid': True, 'decision': 'supported'} for c in candidates]
    review = {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': ['C000']}
    result = finalize_candidate_analysis(document, 'synthetic', {'candidates': candidates, 'rejected': []},
                                         labels, review)
    result['modelDecisions'] = records
    result['reviewDispositions'] = [{'candidateId': 'C000', 'disposition': 'needs_confirmation',
                                     'reason': 'not_product_fact'}]
    return document, result
