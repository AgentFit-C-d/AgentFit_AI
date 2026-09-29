"""Run from ai_service with its editable install; synthetic documents only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

from agentfit_ai.candidate_first_profile import (
    classify_profile_candidates, _MENTION_INSTRUCTION)
from agentfit_ai.langextract_solar_trial import load_key
from agentfit_ai.solar import post_solar

CASES = [
    ('P01', '비교 제품 Old는 Go를 사용한다. 현재 제품 New의 서버 언어는 Go를 검토 중이며 아직 채택하지 않았다.', ['irrelevant', 'tentative']),
    ('P02', '현재 제품 New의 서버 언어는 Go로 확정했다. 과거 실험 제품 Old의 서버는 Go를 사용했다.', ['confirmed', 'irrelevant']),
    ('P03', '현재 제품 New의 서버에는 Go를 사용하지 않기로 확정했다. 비교 제품 Old의 서버는 Go를 사용한다.', ['negated', 'irrelevant']),
    ('P04', '과거 폐기한 실험 제품 Old는 Go를 사용했다. 현재 제품 New의 서버 언어는 Go로 확정했다.', ['irrelevant', 'confirmed']),
]


def main():
    parser = argparse.ArgumentParser(description='Fixed repeated-mention probe')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reasoning-effort', choices=('none', 'medium'), required=True)
    args = parser.parse_args()
    if not args.live or args.output.exists():
        parser.error('--live and a new output path are required')
    # Output is created before loading the key; never overwrite existing data.
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write('{}\n')
    key = load_key(args.env_file)
    rows = []
    report = {
        'reasoning_effort': args.reasoning_effort,
        'cases_sha256': hashlib.sha256(json.dumps(CASES, ensure_ascii=False).encode()).hexdigest(),
        'rows': rows,
    }
    for case_index, (case_id, document, statuses) in enumerate(CASES):
        starts = [document.index('Go'), document.rindex('Go')]
        for reverse in (False, True):
            order = [1, 0] if reverse else [0, 1]
            frozen = {'candidates': [
                {'id': f'C{i:03d}', 'start': starts[n], 'end': starts[n] + 2}
                for i, n in enumerate(order)], 'rejected': []}
            expected = {f'C{i:03d}': statuses[n] for i, n in enumerate(order)}
            variants = ['baseline', 'context'] if (case_index + reverse) % 2 == 0 else ['context', 'baseline']
            for variant in variants:
                calls = 0

                def transport(payload, api_key, timeout):
                    nonlocal calls
                    calls += 1
                    payload = copy.deepcopy(payload)
                    payload['reasoning_effort'] = args.reasoning_effort
                    if variant == 'baseline':
                        payload['messages'][0]['content'] = payload['messages'][0]['content'].replace(_MENTION_INSTRUCTION, '')
                        body = json.loads(payload['messages'][1]['content'])
                        body['candidates'] = [
                            {name: row[name] for name in ('id', 'value')}
                            for row in body['candidates']]
                        payload['messages'][1]['content'] = json.dumps(body, ensure_ascii=False)
                    return post_solar(payload, api_key, timeout)

                started = time.monotonic()
                row = {'case_id': case_id, 'reverse': reverse, 'variant': variant}
                try:
                    labels = classify_profile_candidates(document, frozen, key, transport=transport)
                    row.update(outcome='complete', checked=len(labels), matched=sum(
                        label['status'] == expected[label['id']] and
                        (label['status'] == 'irrelevant' or label['field'] == 'backend')
                        for label in labels), false_confirmed=sum(
                            label['status'] == 'confirmed' and expected[label['id']] != 'confirmed'
                            for label in labels))
                except Exception:
                    row.update(outcome='failed')
                row.update(calls=calls, elapsed_ms=round((time.monotonic() - started) * 1000))
                rows.append(row)
                args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
                print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
