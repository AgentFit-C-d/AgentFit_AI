"""Evaluation-only observation/cost guards around the actual request worker."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys
from time import time, monotonic
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
OUT = Path('E:/AgentFit/output/semantic-role-service-path-v1')
ACCESS = Path('E:/AgentFit/output/independent-profile-v1/nvidia-free-access-20261001-user-confirmation.json')


def write(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def main():
    version, folder, target = sys.argv[1:4]
    if version not in ('before', 'after'):
        raise ValueError('invalid version')
    output = Path(folder).resolve()
    if not output.is_relative_to(OUT.resolve()):
        raise ValueError('invalid output directory')
    base = OUT / 'baseline' if version == 'before' else ROOT / 'ai_service'
    sys.path.insert(0, str(base))
    from agentfit_ai import candidate_service_worker as service_worker, nvidia_streaming
    from agentfit_ai import analysis_worker
    from agentfit_ai.nvidia_evaluation_inputs import validate_free_access, ENDPOINT
    from agentfit_ai.solar import AnalysisError
    trace, stages, calls = [], {}, []
    real_analyze = service_worker.analyze_nvidia_candidates
    real_transport = service_worker.post_nvidia_streaming_inline
    live = target == 'live'
    if not live:
        parsed = urlsplit(target)
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port:
            raise ValueError('loopback only')
        connect = socket.socket.connect
        def local_connect(sock, address):
            if address != ('127.0.0.1', parsed.port):
                raise ValueError('external network forbidden')
            return connect(sock, address)
        socket.socket.connect = local_connect
        nvidia_streaming.ENDPOINT = target + '/nvidia'
    else:
        freeze = json.loads((OUT / 'freeze.json').read_text(encoding='utf-8'))
        for path, digest in freeze['files'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                raise ValueError('FROZEN_FILE_CHANGED')
        if nvidia_streaming.ENDPOINT != ENDPOINT:
            raise ValueError('ENDPOINT_CHANGED')
    stopped = False

    def transport(payload, key, timeout):
        nonlocal stopped
        if stopped:
            raise AnalysisError('PROVIDER_FAILURE')
        if live:
            access = validate_free_access(ACCESS, reserved_calls=256)
            started = json.loads((OUT / 'live-started.json').read_text(encoding='utf-8'))
            if time() - started['time'] >= 7200 or payload['model'] not in access['models']:
                raise ValueError('EVALUATION_LIMIT')
            if len(list(OUT.glob('live-*/*-call-started.json'))) >= 256:
                raise ValueError('CALL_LIMIT')
        index = len(calls) + 1
        name = payload['response_format']['json_schema']['name']
        row = {'index': index, 'model': payload['model'], 'schema': name, 'completed': False}
        write(output / f'{index:03}-call-started.json', row)
        calls.append(row)
        start = monotonic()
        try:
            raw = real_transport(payload, key, timeout)
            row['completed'] = True
            return raw
        except Exception as error:
            stopped = True
            row['error'] = error.code if isinstance(error, AnalysisError) else type(error).__name__
            raise
        finally:
            row['elapsed_seconds'] = round(monotonic() - start, 3)
            write(output / f'{index:03}-call.json', row)

    def observe(stage, state):
        stages[stage] = deepcopy(state)

    def analyze(*args, **kwargs):
        kwargs['observer'] = observe
        kwargs['call_trace'] = trace
        return real_analyze(*args, **kwargs)

    service_worker.post_nvidia_streaming_inline = transport
    service_worker.analyze_nvidia_candidates = analyze
    raw = sys.stdin.buffer.read(analysis_worker.MAX_INPUT_BYTES + 1)
    result = analysis_worker.execute_request(raw)
    write(output / 'trace.json', {'stages': stages, 'calls': calls, 'pipeline_calls': trace})
    sys.stdout.buffer.write(result)


if __name__ == '__main__': main()
