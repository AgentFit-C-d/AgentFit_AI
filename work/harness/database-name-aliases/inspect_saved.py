"""Local inspection only; no transport or environment loading."""
import json
from pathlib import Path

root = Path('E:/AgentFit/output/semantic-role-service-path-v1')
trace = json.loads((root / 'live-documenso-before/trace.json').read_text(encoding='utf-8'))
document = (root / 'documenso.md').read_text(encoding='utf-8')
print('trace keys', list(trace))
print('stages', {k: list(v) if isinstance(v, dict) else type(v).__name__ for k, v in trace['stages'].items()})
stage = trace['stages']['reviewed']
labels = {r['id']: r for r in stage['labels']}
for c in stage['frozen']['candidates']:
    if labels[c['id']]['field'] == 'database':
        print(json.dumps({'candidate': c, 'label': labels[c['id']],
                          'context': document[max(0, c['start']-100):c['end']+100]}, ensure_ascii=False))
response = json.loads((root / 'live-documenso-before/response.json').read_text(encoding='utf-8'))
print('response keys', list(response['body']))
print('database', response['body']['profile']['data']['database'])
print('field states', response['body']['fieldStates'])
