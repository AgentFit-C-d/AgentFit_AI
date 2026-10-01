"""Freeze existing local results for a zero-call projection comparison."""
import hashlib
import json
from pathlib import Path

repo = Path(__file__).resolve().parents[3]
source = Path('E:/AgentFit/output/semantic-role-service-path-v1')
out = Path('E:/AgentFit/output/database-name-aliases-v1')
out.mkdir(exist_ok=True)
paths = {'document': source / 'documenso.md',
         'trace': source / 'live-documenso-before/trace.json',
         'response': source / 'live-documenso-before/response.json',
         'baseline': repo / 'ai_service/agentfit_ai/candidate_first_profile.py'}
manifest = {}
for name, path in paths.items():
    payload = path.read_bytes()
    suffix = '.py' if name == 'baseline' else '.md' if name == 'document' else '.json'
    target = out / (name + suffix)
    with target.open('xb') as stream:
        stream.write(payload)
    manifest[name] = {'path': str(path), 'sha256': hashlib.sha256(payload).hexdigest()}
with (out / 'freeze.json').open('x', encoding='utf-8') as stream:
    json.dump(manifest, stream, indent=2)

document = paths['document'].read_text(encoding='utf-8')
trace = json.loads(paths['trace'].read_text(encoding='utf-8'))
reviewed = trace['stages']['reviewed']
labels = {r['id']: r for r in reviewed['labels']}
chosen = [c for c in reviewed['frozen']['candidates']
          if labels[c['id']]['field'] == 'database' and labels[c['id']]['status'] == 'confirmed']
assert [document[c['start']:c['end']] for c in chosen] == ['Postgres SQL Database', 'postgres database']
parts, candidates, origins = [], [], []
length = 0
for c in chosen:
    start = document.rfind('\n', 0, c['start']) + 1
    end = document.find('\n', c['end'])
    if end < 0:
        end = len(document)
    excerpt = document[start:end] + '\n'
    candidates.append({'id': c['id'], 'start': length + c['start'] - start,
                       'end': length + c['end'] - start})
    origins.append({'candidate': c, 'label': labels[c['id']], 'lineStart': start, 'lineEnd': end})
    parts.append(excerpt)
    length += len(excerpt)
fixture = {'origin': manifest, 'originalCandidates': origins,
           'document': ''.join(parts), 'documentId': 'saved-documenso-database',
           'frozen': {'candidates': candidates, 'rejected': []},
           'labels': [labels[c['id']] for c in chosen],
           'expectedValue': 'Postgres SQL Database'}
target = repo / 'ai_service/tests/fixtures/database_name_aliases.json'
target.parent.mkdir(exist_ok=True)
with target.open('x', encoding='utf-8') as stream:
    json.dump(fixture, stream, ensure_ascii=False, indent=2)
print(json.dumps({'frozen': str(out), 'actual_database_candidates': len(chosen),
                  'fixture': str(target), 'new_model_calls': 0}))
