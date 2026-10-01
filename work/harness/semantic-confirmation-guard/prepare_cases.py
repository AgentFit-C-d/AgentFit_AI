"""Read-only extraction of old diagnostic cases; never changes old gold/output."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = Path('E:/AgentFit/output/independent-profile-v1')
raw = (BASE / 'PUBLIC-01.md').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '5d26fe9a49507c3937d1a7950e0c4e620b1db08c741f8a36b98a83c90529e87b'
document = raw.decode('utf-8')
trace = json.loads((BASE / 'capability-occurrences-full-v1/PUBLIC-01-run-0.trace.json').read_text())['trace']
old = json.loads((BASE / 'classification-full-batch15-v1/PUBLIC-01-deepseek.json').read_text())
expected = {'C019': ('features', False), 'C026': ('features', False),
            **{i: ('features', True) for i in ('C059', 'C061', 'C066', 'C069', 'C071', 'C073')},
            'C113': ('deployment', True), 'C115': ('deployment', True)}
selected = [r for r in trace['stages']['grounded']['candidates'] if r['id'] in expected]
actual = {'id': 'actual-readme', 'document': document,
          'source': 'https://github.com/documenso/documenso/blob/a1d4bec1430a937395db9a4aae28979cd71c2831/README.md',
          'sourceSha256': hashlib.sha256(raw).hexdigest(),
          'frozen': {'candidates': selected, 'rejected': []},
          'gold': [{'id': r['id'], 'field': expected[r['id']][0], 'confirmed': expected[r['id']][1]}
                   for r in selected],
          'recordedLabels': [r for r in old['labels'] if r['id'] in expected],
          'recordedReviewed': [r for r in trace['stages']['reviewed']['labels'] if r['id'] in expected]}
units = [
 ('이번 Harbor 웹 서비스의 프런트엔드는 React로 확정했다.', 'React', 'frontend', True),
 ('현재 범위의 서버는 FastAPI를 채택했다. 구현은 다음 달 시작한다.', 'FastAPI', 'backend', True),
 ('데이터베이스로 PostgreSQL을 사용하기로 최종 결정했다.', 'PostgreSQL', 'database', True),
 ('이번 출시의 필수 기능: 감사 기록 내보내기. 아직 개발 전이다.', '감사 기록 내보내기', 'features', True),
 ('이번 서비스는 결제 처리를 제공한다.', '결제 처리', 'features', True),
 ('다른 팀의 Orion은 Vue를 사용한다. Harbor의 기술 선택이 아니다.', 'Vue', 'frontend', False),
 ('과거 폐기된 Harbor 시제품은 MongoDB를 썼다.', 'MongoDB', 'database', False),
 ('Harbor는 Redis를 사용하지 않기로 결정했다.', 'Redis', 'database', False),
 ('Kafka 도입은 검토 중이며 아직 결정되지 않았다.', 'Kafka', 'backend', False),
 ('벡터 검색은 차기 버전의 선택적 아이디어이며 이번 범위에서 제외한다.', '벡터 검색', 'features', False),
 ('초안에는 S3 저장소를 채택한다고 적혀 있다. 그러나 회의에서는 S3 채택 여부를 미정으로 남겼고 어느 문서가 최종인지 정하지 않았다.', 'S3', 'external_integrations', False),
 ('이전 제품의 프런트엔드는 React였다. 이 문장은 이번 제품의 채택 근거가 아니다.', 'React', 'frontend', False),
]
source = '# Harbor 기획서\n' + '\n'.join(r[0] for r in units)
rows, gold, offset = [], [], len('# Harbor 기획서\n')
for i, (sentence, value, field, confirmed) in enumerate(units):
    start = offset + sentence.index(value)
    rows.append({'id': f'C{i:03}', 'start': start, 'end': start + len(value)})
    gold.append({'id': f'C{i:03}', 'field': field, 'confirmed': confirmed})
    offset += len(sentence) + 1
synthetic = {'id': 'scope-regression', 'document': source, 'source': 'authored-regression',
             'sourceSha256': hashlib.sha256(source.encode()).hexdigest(),
             'frozen': {'candidates': rows, 'rejected': []}, 'gold': gold}
output = ROOT / 'ai_service/tests/fixtures/semantic_confirmation_cases.json'
with output.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump({'human_reviewed': False, 'cases': [actual, synthetic]}, stream, ensure_ascii=False, indent=2)
print('fixed actual 10 (8 positive/2 negative), synthetic 12 (5 positive/7 negative)')
