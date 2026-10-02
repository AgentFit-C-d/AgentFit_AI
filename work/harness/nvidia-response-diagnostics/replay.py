"""Offline replay only. Stored assembled envelopes are NOT original SSE captures."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'ai_service'))
from agentfit_ai.nvidia_streaming import _assemble_sse
from agentfit_ai.nvidia_response_diagnostics import encode_diagnostic, decode_diagnostic
from agentfit_ai.solar import AnalysisError


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def forbidden(*args, **kwargs):
    raise AssertionError('NETWORK_FORBIDDEN_IN_OFFLINE_REPLAY')


def frame(events):
    return b''.join(b'data: ' + json.dumps(e, ensure_ascii=False).encode() + b'\n\n' for e in events) + b'data: [DONE]\n\n'


def run(saved, output):
    if output.exists():
        raise FileExistsError(output)
    # No .env is loaded. Also disable sockets so imported code cannot make a call.
    socket.socket = socket.create_connection = socket.getaddrinfo = forbidden
    original_files = {str(p.relative_to(saved)): sha(p.read_bytes()) for p in saved.rglob('*') if p.is_file()}
    baseline_path = 'ai_service/agentfit_ai/nvidia_streaming.py'
    old_source = subprocess.run(['rtk', 'proxy', 'git', '-c', f'safe.directory={ROOT.as_posix()}',
        'show', '39fd07c:' + baseline_path], cwd=ROOT, capture_output=True, check=True).stdout
    # RTK proxy sends its own notices to stderr; stdout must be the actual source.
    baseline = types.ModuleType('agentfit_ai.offline_streaming_baseline')
    baseline.__package__ = 'agentfit_ai'
    exec(compile(old_source, 'baseline_39fd07c_nvidia_streaming.py', 'exec'), baseline.__dict__)
    experiment = load(ROOT/'work/harness/status-model-comparison/experiment.py', 'offline_diagnostic_comparison')
    package = json.loads((saved/'package.json').read_bytes())
    records_by_arm = {a: ([], []) for a in ('D', 'G')}
    replayed = []
    for sequence in range(1, 5):
        path = saved/'calls'/f'{sequence:02d}-response.json'
        original = path.read_bytes()
        envelope = json.loads(original)
        choice = envelope['choices'][0]
        events = [{'model': envelope['model'], 'choices': [{'index': 0,
            'delta': {'content': choice['message']['content']}, 'finish_reason': choice['finish_reason']}]},
            {'model': envelope['model'], 'choices': [], 'usage': envelope['usage']}]
        stream = frame(events)
        before = baseline._assemble_sse([stream], envelope['model'])
        # Split every byte, including Korean UTF-8, without assuming original chunk boundaries.
        after = _assemble_sse((bytes([b]) for b in stream), envelope['model'])
        assert before == after == original, 'ASSEMBLED_RESPONSE_CHANGED'
        job = package['jobs'][sequence-1]
        source = package['documents'][job['docId']]
        sender = experiment.FixedPayloadSender('offline-placeholder', lambda *args: after)
        reply, _, _, _ = sender._send_payload(job['payload'], ('decisions',))
        candidates = source['frozen']['candidates'][(job['batch']-1)*8:job['batch']*8]
        records, evidence = experiment.compare.baseline.normalize('U', source['document'],
            source['pair']['registry'], candidates, reply['decisions'])
        name = f"{job['docId']}-{job['arm']}-{job['batch']:02d}"
        prior = json.loads((saved/(name + '-validated.json')).read_bytes())
        assert records == prior['records'] and evidence == prior['evidence'], 'SERVER_VERDICT_CHANGED'
        records_by_arm[job['arm']][0].extend(records)
        records_by_arm[job['arm']][1].extend(evidence)
        replayed.append({'sequence': sequence, 'batch': name, 'bytes_identical': True,
                         'response_sha256': sha(after), 'decisions': len(records), 'verdicts_identical': True})
    summary = json.loads((saved/'summary.json').read_bytes())
    metrics = {}
    for arm, (records, evidence) in records_by_arm.items():
        measured = experiment.compare.score_instruction_rows(records, evidence, package['documents']['FR']['gold'])
        assert measured == summary['documents']['FR'][arm]['metrics'], 'SCORE_CHANGED'
        metrics[arm] = measured
    model = package['jobs'][0]['payload']['model']
    synthetic = [b'data: {"choices":]}\n\n', b'data: \xff\n\n',
        b'data: {"choices":[],"choices":[]}\n\n', frame([[]]), frame([{'error': 'synthetic'}]),
        frame([{'choices': 'wrong'}]), frame([{'choices': [{'index': 1}]}]),
        frame([{'choices': [{'index': 0, 'delta': {'content': 7}}]}]),
        frame([{'model': 'wrong', 'choices': []}]), b'data: [DONE]\n\n', b'']
    errors, example = [], None
    for number, stream in enumerate(synthetic, 1):
        codes = []
        for assemble in (baseline._assemble_sse, _assemble_sse):
            try:
                assemble([stream], model)
            except AnalysisError as exc:
                codes.append(exc.code)
                if assemble is _assemble_sse and exc.code == 'INVALID_RESPONSE' and example is None:
                    example = decode_diagnostic(encode_diagnostic(exc, 200, 'text/event-stream', 'offline-placeholder'),
                                                'offline-placeholder')
            else:
                raise AssertionError('SYNTHETIC_ERROR_ACCEPTED')
        assert codes[0] == codes[1], 'ERROR_CODE_CHANGED'
        errors.append({'case': number, 'before': codes[0], 'after': codes[1]})
    frozen = json.loads((saved/'freeze.json').read_bytes())['sha256']
    changes = []
    for filename, expected in frozen.items():
        p = Path(filename)
        if sha(p.read_bytes()) != expected:
            changes.append(p.relative_to(ROOT).as_posix())
    assert set(changes) == {baseline_path, 'ai_service/agentfit_ai/nvidia_stream_worker.py',
                            'work/harness/status-model-comparison/experiment.py'}, changes
    unchanged = original_files == {str(p.relative_to(saved)): sha(p.read_bytes())
                                   for p in saved.rglob('*') if p.is_file()}
    assert unchanged, 'SAVED_OUTPUT_CHANGED'
    failure = json.loads((saved/'calls/05-finished.json').read_bytes())
    assert not (saved/'calls/05-response.json').exists() and failure['error'] == 'INVALID_RESPONSE'
    report = {'mode': 'offline_reconstructed_sse', 'model_calls': 0, 'baseline_commit': '39fd07c',
        'replayed': replayed, 'unchanged_FR_metrics': metrics, 'synthetic_error_parity': errors,
        'synthetic_diagnostic_example': example, 'original_files_unchanged': unchanged,
        'preserved_file_count': len(original_files), 'preserved_sha256': original_files,
        'old_freeze_changed_sources': changes,
        'classification_schema_gold_server_files_unchanged': True,
        'fifth_failure': {'error': failure['error'], 'historical_root_cause': 'unknown',
                          'reason': 'No original HTTP headers or SSE event bytes were saved.'},
        'service_deployed': False, 'large_goal_resumed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'responses': len(replayed), 'decisions': sum(r['decisions'] for r in replayed),
                      'error_parity_cases': len(errors), 'preserved_files': len(original_files),
                      'calls': 0, 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--saved', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.saved, args.output)
