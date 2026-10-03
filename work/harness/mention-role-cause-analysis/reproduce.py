"""Read-only saved-run audit. No provider, replay worker, or service execution."""
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'ai_service'), str(ROOT/'ai_service/tests')]
from test_mention_role_cause import (MentionRoleCauseTests, ROLES, recorded_batches,
                                   saved, stored_run, synthetic)
from review_preservation_fixture import offline
from agentfit_ai.candidate_mention_roles import MENTION_KINDS
from agentfit_ai.candidate_semantic_assessment import semantic_labels

RUNS = {'v2': Path('E:/AgentFit/output/document-profile-baseline-live-20261002-v1'),
        'v3': Path('E:/AgentFit/output/document-profile-v3-live-20261002-v1')}
OUT = Path('E:/AgentFit/output/mention-role-cause-analysis-20261003-v1')
POSITIONS = (2, 137, 168, 1857, 3570, 4020, 5122, 7266)
SOURCE_SHA = '9c0115a34e4ae90f905c3021569bc4b5c10284388c7bac264b76e2d3d077f451'
GOLD_SHA = '40ecc131c19fb8aa0e0127b67f9a5adf95885ed194a67350d3c89a9e9b328260'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_hash(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def snapshot():
    # Hash every saved file; the audit writes only to a new output directory.
    return {version: {p.relative_to(folder).as_posix(): sha(p.read_bytes())
                      for p in sorted(folder.rglob('*')) if p.is_file()}
            for version, folder in RUNS.items()}


def write(name, data):
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = snapshot()
    audit = {'scope': 'saved evidence only; no new model accuracy measurement',
             'networkOrModelCalls': 0, 'runs': {}, 'syntheticRoleMatrix': []}
    with offline():
        for version, folder in RUNS.items():
            document, trace = stored_run(version)
            assert folder.joinpath('document.txt').read_bytes() == document.encode('utf-8')
            assert json.loads(folder.joinpath('trace.json').read_bytes()) == trace
            assert before[version]['document.txt'] == SOURCE_SHA
            assert before[version]['gold.json'] == GOLD_SHA
            freeze = json.loads(folder.joinpath('freeze.json').read_bytes())
            run = {'sourcePath': str(folder), 'documentSha256': SOURCE_SHA,
                   'goldSha256': GOLD_SHA, 'traceSha256': before[version]['trace.json'],
                   'revision': freeze['revision'],
                   'execution': json.loads(folder.joinpath('execution.json').read_bytes()),
                   'classificationRequests': len(recorded_batches(version)), 'focus': [],
                   'reviewCompleted': 'review_completed' in trace['stages'],
                   'finalResponse': trace['stages']['final_response']}
            for start in POSITIONS:
                batch, candidate, raw, record = saved(version, start)
                call = batch['call']
                request_file = f'{version}-request-{call["index"]:03}.json'
                response_file = f'{version}-response-{call["index"]:03}.json'
                # Explicit safe allowlist. Credentials/headers are never read/exported.
                write(request_file, {k: call['request'][k] for k in
                      ('model', 'messages', 'response_format') if k in call['request']})
                write(response_file, {'content': json.loads(call['response']['text'])['choices'][0]['message']['content']})
                original = next(r for r in trace['stages']['semantic_assessed']['modelDecisions'] if r['id']==candidate['id'])
                assert record == original
                quote_audit = []
                for group in ('support', 'counterEvidence'):
                    for quote in raw[group]:
                        found, cursor = [], -1
                        while True:
                            cursor = document.find(quote['quote'], cursor+1)
                            if cursor < 0:
                                break
                            found.append(cursor)
                        quote_audit.append({'group': group, **quote, 'actualStarts': found,
                                            'occurrenceValid': quote['occurrence'] < len(found)})
                reviewed_in = []
                for review_call in trace['calls']:
                    response = review_call.get('response')
                    if not response or 'text' not in response:
                        continue
                    try:
                        reply = json.loads(json.loads(response['text'])['choices'][0]['message']['content'])
                    except (ValueError, KeyError, IndexError, TypeError):
                        continue
                    if candidate['id'] in reply.get('checkedCandidateIds', []):
                        reviewed_in.append({'call': review_call['index'],
                                            'rejected': candidate['id'] in reply['wrongCandidateIds']})
                run['focus'].append({'candidate': candidate,
                    'sourceValue': document[start:candidate['end']],
                    'line': document[:start].count('\n')+1,
                    'modelInput': next(c for c in batch['input']['candidates'] if c['id']==candidate['id']),
                    'requestIndex': call['index'], 'requestFile': request_file,
                    'responseFile': response_file, 'requestCanonicalSha256': json_hash(call['request']),
                    'raw': raw, 'validated': record, 'serverLabel': semantic_labels([record])[0],
                    'quoteAudit': quote_audit, 'successfulReviews': reviewed_in})
            audit['runs'][version] = run
        for field, allowed_kind in ROLES.items():
            for kind in MENTION_KINDS:
                record = synthetic('현재 대상 제품의 명시된 사실은 Value다.', 'Value', field, kind)
                audit['syntheticRoleMatrix'].append({'field': field, 'mentionKind': kind,
                                                     'decision': record['decision']})
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(MentionRoleCauseTests))
        expected = [{'test': test.id(), 'failure': failure} for test, failure in result.expectedFailures]
        # These are real semantic assertion failures, never fixture/import errors masked as expected.
        assert len(expected) == 5 and all('AssertionError:' in r['failure'] for r in expected)
        assert not result.errors and not result.failures and not result.unexpectedSuccesses
        audit['tests'] = {'run': result.testsRun, 'passed': result.testsRun-len(expected),
                          'historicalModelExpectedFailures': 4,
                          'separateSyntheticPolicyExpectedFailures': 1,
                          'expectedFailures': expected, 'unexpectedFailures': 0}
        (OUT/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
        assert before == snapshot(), 'original run artifacts changed'
        write('evidence.json', audit)
        focus_lines = ['run\tid\tposition\tvalue\tcall\tfield\tkind\tgrounded\tdecision\treview']
        for version, run in audit['runs'].items():
            for row in run['focus']:
                focus_lines.append('\t'.join(map(str, (version, row['candidate']['id'],
                    row['candidate']['start'], row['sourceValue'], row['requestIndex'],
                    row['raw']['field'], row['raw']['mentionKind'], row['validated']['groundingValid'],
                    row['validated']['decision'], row['successfulReviews']))))
        (OUT/'focus.tsv').write_text('\n'.join(focus_lines)+'\n', encoding='utf-8')
        write('input-integrity.json', {'before': before, 'afterMatchesBefore': True,
                                     'sourceAndGoldMatchBetweenRuns': True})
        print(json.dumps({'output': str(OUT), 'tests': result.testsRun,
                          'passed': result.testsRun-5, 'expectedFailures': 5,
                          'classificationRequests': {v:r['classificationRequests'] for v,r in audit['runs'].items()},
                          'newModelCalls': 0, 'originalArtifactsUnchanged': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
