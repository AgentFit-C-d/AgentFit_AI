"""Actual HTTP/child path comparison, with fixed-provider and live runs separated."""
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
from time import monotonic, sleep, time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
OUT = Path('E:/AgentFit/output/semantic-role-service-path-v1')
sys.path[:0] = [str(ROOT / 'ai_service'), str(ROOT / 'ai_service/runtime_tests')]
import httpx
import uvicorn
from agentfit_ai.analysis_process import run_analysis_process
from agentfit_ai.http_service import create_app
from agentfit_ai.nvidia_evaluation_inputs import validate_free_access, load_nvidia_key
from test_integrated_service import provider_server, NVIDIA_KEY, HEADERS
from test_mention_role_service_path import RoleProvider, CASES

ACCESS = Path('E:/AgentFit/output/independent-profile-v1/nvidia-free-access-20261001-user-confirmation.json')
CHILD = Path(__file__).with_name('evaluation_child.py')


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def identity():
    files = list((ROOT / 'ai_service/agentfit_ai').glob('*.py'))
    files += list((OUT / 'baseline/agentfit_ai').glob('*.py'))
    files += [Path(__file__), CHILD, OUT / 'gold.json', OUT / 'documents.json',
              OUT / 'documenso.md', OUT / 'linkding.md']
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


@contextmanager
def server(version, folder, endpoint, key):
    async def process(*args, **kwargs):
        return await run_analysis_process(*args, **kwargs,
            command=[sys.executable, str(CHILD), version, str(folder), endpoint])
    with patch.dict(os.environ, {'AGENTFIT_ANALYSIS_MODE': 'integrated-nvidia',
            'AGENTFIT_INTERNAL_TOKEN': 'local-evaluation-only', 'NVIDIA_API_KEY': key,
            'UPSTAGE_API_KEY': '', 'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}), patch(
            'agentfit_ai.http_service.run_analysis_process', side_effect=process):
        app = create_app(request_timeout_seconds=1800, max_inflight=1)
        host = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=0, access_log=False, log_level='error'))
        thread = threading.Thread(target=host.run, daemon=True)
        thread.start()
        try:
            until = monotonic() + 10
            while not host.started and monotonic() < until:
                sleep(.02)
            if not host.started:
                raise ValueError('local service did not start')
            yield f'http://127.0.0.1:{host.servers[0].sockets[0].getsockname()[1]}'
        finally:
            host.should_exit = True
            thread.join(10)
            if thread.is_alive():
                raise ValueError('local service did not stop')


def run(document, name, version, endpoint, key):
    folder = OUT / name
    folder.mkdir(exist_ok=False)
    write(folder / 'request-started.json', {'version': version, 'time': time(),
        'documentSha256': hashlib.sha256(document.encode()).hexdigest()})
    with server(version, folder, endpoint, key) as url, httpx.Client(trust_env=False, timeout=1810) as http:
        start = monotonic()
        response = http.post(url + '/internal/v1/analyze', content=document.encode(),
            headers=dict(HEADERS, Authorization='Bearer local-evaluation-only',
                **{'X-Document-Kind': 'MARKDOWN', 'Content-Type': 'text/markdown'}))
        result = {'status_code': response.status_code, 'body': response.json(),
                  'elapsed_seconds': round(monotonic() - start, 3)}
    write(folder / 'response.json', result)
    return result, json.loads((folder / 'trace.json').read_text(encoding='utf-8')) if (folder / 'trace.json').exists() else None


def preservation(body, trace):
    stages = (trace or {}).get('stages', {})
    counts = {'grounded': len(stages.get('grounded', {}).get('candidates', [])),
              'classified': len(stages.get('classified', {}).get('labels', [])),
              'reviewed': len(stages.get('reviewed', {}).get('labels', [])),
              'final_records': len(body.get('modelDecisions', []))}
    counts['held_candidates'] = sum(r['decision'] == 'needs_confirmation' for r in body.get('modelDecisions', []))
    counts['unassigned_candidates'] = sum(len(q['candidateIds']) for q in body.get('unassignedQuestions', []))
    return counts


def atoms(body):
    return [(field, value) for field, values in body.get('profile', {}).get('data', {}).items()
            if values is not None for value in (values if type(values) is list else [values])]


def fixed_score(case, result, trace):
    body = result['body']
    values = atoms(body)
    records = body.get('modelDecisions', [])
    bad, missing, lost = [], [], []
    for candidate, gold in zip(case['frozen']['candidates'], case['gold']):
        value = case['document'][candidate['start']:candidate['end']]
        fields = [field for field, actual in values if actual == value]
        record = next((r for r in records if r['candidate'] == {'start': candidate['start'], 'end': candidate['end']}), None)
        if gold['constraint'] == 'positive' and gold['field'] not in fields:
            missing.append(gold['id'])
        if fields and ((gold['constraint'] == 'positive' and any(f != gold['field'] for f in fields)) or
                (gold['constraint'] == 'not_external' and any(f != 'features' for f in fields)) or
                gold['constraint'] in ('hold', 'not_confirmed')):
            bad.append(gold['id'])
        if gold['constraint'] == 'hold' and not (record and record['decision'] == 'needs_confirmation'):
            lost.append(gold['id'])
    return {'false_proposals': len(bad), 'normal_misses': len(missing), 'lost_ambiguity': len(lost),
            'questions': len(body.get('questions', [])) + len(body.get('unassignedQuestions', [])),
            **preservation(body, trace)}


def matches(value, aliases):
    return any(alias.casefold() in value.casefold() for alias in aliases)


def document_score(gold, result, trace):
    body = result['body']
    values = atoms(body)
    matched = [r['id'] for r in gold['positive'] if any(f == r['field'] and matches(v, r['aliases']) for f, v in values)]
    false, review = [], []
    for field, value in values:
        wrong = any(field in r['fields'] and matches(value, r['aliases']) for r in gold['forbidden'])
        correct = any(field == r['field'] and matches(value, r['aliases']) for r in gold['positive'])
        if wrong:
            false.append({'field': field, 'value': value})
        elif not correct:
            reasons = [r['reason'] for r in gold['humanReview'] if matches(value, r['aliases'])]
            review.append({'field': field, 'value': value, 'reasons': reasons or ['not covered by preregistered gold']})
    return {'valid': result['status_code'] == 200 and 'profile' in body,
            'normal_information': len(gold['positive']), 'normal_matched': len(matched),
            'normal_misses': len(gold['positive']) - len(matched), 'false_proposals': len(false),
            'false_details': false, 'human_review_count': len(review), 'human_review': review,
            'missing_ids': [r['id'] for r in gold['positive'] if r['id'] not in matched],
            'questions': len(body.get('questions', [])) + len(body.get('unassignedQuestions', [])),
            'unresolved_fields': sum(s == 'unresolved' for s in body.get('fieldStates', {}).values()),
            'elapsed_seconds': result['elapsed_seconds'], **preservation(body, trace)}


def main():
    mode = sys.argv[1]
    if mode == 'freeze':
        validate_free_access(ACCESS, reserved_calls=256)
        write(OUT / 'freeze.json', {'files': identity(), 'max_calls': 256, 'request_seconds': 1800,
            'total_seconds': 7200, 'retries': 0, 'requests': 4, 'repetitions': 1})
        print('frozen; model calls=0')
        return
    rows = []
    if mode == 'fixed':
        for case in CASES:
            for version in ('before', 'after'):
                provider = RoleProvider(case)
                with provider_server(provider) as endpoint:
                    result, trace = run(case['document'], f'fixed-{case["id"]}-{version}', version, endpoint, NVIDIA_KEY)
                if provider.errors:
                    raise ValueError('fixed provider error: ' + repr(provider.errors))
                row = {'case': case['id'], 'version': version, 'elapsed_seconds': result['elapsed_seconds'],
                       'metrics': fixed_score(case, result, trace)}
                rows.append(row)
                print(json.dumps(row), flush=True)
        write(OUT / 'fixed-summary.json', {'rows': rows, 'kind': 'fixed role assertions, actual HTTP path; not model accuracy'})
        return
    if mode != 'live':
        raise ValueError('invalid mode')
    freeze = json.loads((OUT / 'freeze.json').read_text(encoding='utf-8'))
    if identity() != freeze['files']:
        raise ValueError('FROZEN_FILE_CHANGED')
    validate_free_access(ACCESS, reserved_calls=256)
    key = load_nvidia_key(Path('E:/AgentFit/.env'))
    gold = json.loads((OUT / 'gold.json').read_text(encoding='utf-8'))['documents']
    write(OUT / 'live-started.json', {'time': time()})
    for name in ('linkding', 'documenso'):
        for version in ('before', 'after'):
            validate_free_access(ACCESS, reserved_calls=256)
            document = (OUT / (name + '.md')).read_text(encoding='utf-8')
            result, trace = run(document, f'live-{name}-{version}', version, 'live', key)
            row = {'case': name, 'version': version, 'metrics': document_score(gold[name], result, trace),
                   'error': result['body'].get('error'), 'calls': len((trace or {}).get('calls', []))}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            if not row['metrics']['valid'] or any('error' in c for c in (trace or {}).get('calls', [])):
                write(OUT / 'live-summary.json', {'rows': rows, 'stopped': True})
                return
    write(OUT / 'live-summary.json', {'rows': rows, 'stopped': False})


if __name__ == '__main__': main()
