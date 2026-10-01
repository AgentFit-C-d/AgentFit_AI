"""Freeze a single comparison and enforce existing free-only, no-retry transport."""
import importlib.util
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ADAPTER_SPEC = importlib.util.spec_from_file_location('b_evidence_adapter', Path(__file__).with_name('experiment.py'))
adapter = importlib.util.module_from_spec(ADAPTER_SPEC)
ADAPTER_SPEC.loader.exec_module(adapter)
from agentfit_ai.deepseek_evaluation import MODEL, ENDPOINT, NvidiaAnalyzer
from agentfit_ai.nvidia_evaluation_inputs import validate_free_access, load_nvidia_key
from agentfit_ai.nvidia_streaming import post_nvidia_streaming, ENDPOINT as STREAM_ENDPOINT

ROOT = adapter.ROOT
SOURCE = Path('E:/AgentFit/output/direct-field-comparison-v1')
FREE = Path('E:/AgentFit/output/independent-profile-v1/nvidia-free-access-20261001-user-confirmation.json')
AUDIT = ROOT / 'specs/ai-developer/evidence-relation-repair/audit.json'
GOLD = ROOT / 'specs/ai-developer/direct-field-comparison/gold.json'
DEFAULT_OUTPUT = Path('E:/AgentFit/output/b-evidence-selection-v1')


def read_json(path):
    return json.loads(Path(path).read_bytes().decode('utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_free(path):
    scope = validate_free_access(path, reserved_calls=18)
    if STREAM_ENDPOINT != ENDPOINT or scope['endpoint'] != ENDPOINT or MODEL not in scope['models']:
        raise ValueError('FREE_ACCESS_UNCONFIRMED')


def check_identity(output, identity=None):
    identity = read_json(output / 'freeze.json')['sha256'] if identity is None else identity
    for path, sha in identity.items():
        if digest(path) != sha:
            raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')


def freeze(output, *, source=None, free=None):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    source, free = Path(source or SOURCE), Path(free or FREE)
    check_free(free)
    manifest = read_json(AUDIT)
    input_path = source / 'inputs.json'
    if digest(input_path) != manifest['input_sha256']['inputs.json']:
        raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')
    inputs = read_json(input_path)
    gold = read_json(GOLD)
    if inputs['gold'] != gold or gold['human_reviewed'] is not True:
        raise ValueError('INVALID_GOLD')
    document, frozen = inputs['document'], inputs['frozen']
    if (len(document) != 4558 or len(frozen['candidates']) != 68 or len(frozen['rejected']) != 24
            or hashlib.sha256(document.encode('utf-8')).hexdigest() != manifest['source_sha256']):
        raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')
    pair = adapter.build_pair(document, frozen)
    for q, u in zip(pair['payloads']['Q'], pair['payloads']['U'], strict=True):
        if q['messages'][1] != u['messages'][1]:
            raise ValueError('CONTEXT_MISMATCH')
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'inputs.json').open('xb') as handle:
        handle.write(input_path.read_bytes())
    adapter.write_json(output / 'pair.json', pair)
    paths = [*sorted((ROOT / 'ai_service/agentfit_ai').glob('*.py')),
             *sorted(Path(__file__).parent.glob('*.py')),
             ROOT / 'work/harness/direct-field-comparison/comparison.py',
             ROOT / 'work/harness/evidence-relation-repair/source_registry.py',
             ROOT / 'work/harness/evidence-relation-repair/legacy_audit.py',
             AUDIT, GOLD, input_path, output / 'inputs.json', output / 'pair.json', free]
    result = {'version': 'b-evidence-selection-v1', 'sha256': {str(p.resolve()): digest(p) for p in paths},
              'scope': 'one Q-then-U pair; only B evidence representation changes',
              'model': MODEL, 'endpoint': ENDPOINT, 'max_calls': 18, 'retries': 0,
              'temperature': 0, 'thinking': False, 'max_tokens': 8192, 'batch_size': 8,
              'calls_per_arm': 9, 'source_code_points': len(document), 'candidates': 68,
              'rejected_preserved': 24, 'gold': 10, 'positive_gold': 6,
              'context': 'identical full document + original +/-240 code point candidate context + all source units',
              'free_record': str(free.resolve()), 'utc': datetime.now(timezone.utc).isoformat()}
    adapter.write_json(output / 'freeze.json', result)
    print(json.dumps({'frozen': True, 'model_calls': 0, 'max_calls': 18, 'paired_batches': 9}), flush=True)
    return result


def live(output):
    output = Path(output)
    if (output / 'live-started.json').exists():
        raise FileExistsError(output / 'live-started.json')
    frozen = read_json(output / 'freeze.json')
    identity = dict(frozen['sha256'])
    identity[str((output / 'freeze.json').resolve())] = digest(output / 'freeze.json')
    free = Path(frozen['free_record'])
    check_identity(output, identity)
    check_free(free)
    # The durable marker precedes keys and transport, preventing replay after crashes.
    adapter.write_json(output / 'live-started.json', {'utc': datetime.now(timezone.utc).isoformat(),
                        'max_calls': 18, 'retries': 0, 'freeze_sha256': digest(output / 'freeze.json')})
    key = load_nvidia_key(Path('E:/AgentFit/.env'))
    gate = adapter.CallGate(output / 'calls', check_free=lambda: check_free(free),
                           check_identity=lambda: check_identity(output, identity),
                           transport=post_nvidia_streaming)
    result = adapter.run_pair(output, read_json(output / 'inputs.json'), read_json(output / 'pair.json'),
                              gate, NvidiaAnalyzer(key, transport=gate, model=MODEL))
    unchanged = True
    try:
        check_identity(output, identity)
    except (ValueError, OSError):
        unchanged = False
    adapter.write_json(output / 'verification.json', {'frozen_files_unchanged': unchanged,
        'calls_started': gate.started, 'retries': 0, 'service_applied': False, 'large_goal_resumed': False})
    if not unchanged:
        raise ValueError('FROZEN_INPUT_OR_CODE_CHANGED')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('freeze', 'live'))
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze(args.output)
    else:
        result = live(args.output)
        raise SystemExit(0 if result['comparable'] else 1)
