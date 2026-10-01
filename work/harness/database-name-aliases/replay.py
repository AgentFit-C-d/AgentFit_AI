"""Compare frozen projection responses locally; no model or network calls."""
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
from time import perf_counter

repo = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(repo / 'ai_service'), str(repo / 'ai_service/tests')]
from agentfit_ai.candidate_first_profile import project_candidate_profile
from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.profile import FIELDS
from test_database_name_aliases import CASES, inputs

out = Path('E:/AgentFit/output/database-name-aliases-v1')
manifest = json.loads((out / 'freeze.json').read_text(encoding='utf-8'))
for name, row in manifest.items():
    # Only the implementation is expected to change. Prior result files are immutable.
    if name != 'baseline':
        assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['sha256'], name
    suffix = '.py' if name == 'baseline' else '.md' if name == 'document' else '.json'
    assert hashlib.sha256((out / (name + suffix)).read_bytes()).hexdigest() == row['sha256'], name
spec = importlib.util.spec_from_file_location('agentfit_ai._alias_baseline', out / 'baseline.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

def no_network(*args, **kwargs):
    raise AssertionError('network is forbidden for frozen response replay')

socket.socket = no_network
socket.create_connection = no_network
document = (out / 'document.md').read_text(encoding='utf-8')
trace = json.loads((out / 'trace.json').read_text(encoding='utf-8'))
body = json.loads((out / 'response.json').read_text(encoding='utf-8'))['body']
document_id = next(s['documentId'] for spans in body['profile']['evidence'].values() for s in spans)
reviewed = trace['stages']['reviewed']
reports, profiles = {}, {}
for version, projector in [('before', baseline.project_candidate_profile), ('after', project_candidate_profile)]:
    rows = []
    started = perf_counter()
    original = deepcopy(reviewed)
    projected = projector(document, document_id, reviewed['frozen'], reviewed['labels'], coverage_verified=False)
    assert original == reviewed
    profiles[version] = projected['profile']
    # The saved projection is replayed exactly; later review/curation is not invented.
    if version == 'before':
        assert projected['profile'] == trace['stages']['projected'] == body['profile']
    result = dict(projected, candidateCount=len(reviewed['frozen']['candidates']),
                  rejectedReasons=dict(Counter(r['reason'] for r in reviewed['frozen']['rejected'])),
                  reviewIssueCount=0)
    draft = project_candidate_confirmation(document, document_id, result)
    actual = {'database': draft['profile']['data']['database'],
              'alias_collision': int('database' in projected['unresolvedFields']),
              'normal_database_missing': int(draft['profile']['data']['database'] is None),
              'database_final_state': draft['fieldStates']['database'],
              'final_questions': len(draft['questions']), 'seconds': perf_counter() - started,
              'candidates': len(reviewed['frozen']['candidates']),
              'rejected': len(reviewed['frozen']['rejected']),
              'scope': 'saved reviewed stage -> Profile -> confirmation-v2 validation'}
    for name, values, expected in CASES:
        doc, frozen, labels = inputs(values)
        row = projector(doc, 'DOC', frozen, labels, coverage_verified=True)
        value = row['profile']['data']['database']
        rows.append({'case': name, 'expected': expected, 'actual': value,
                     'false_merge': int(expected is None and value is not None),
                     'normal_missing': int(expected is not None and value is None),
                     'unresolved': int('database' in row['unresolvedFields']),
                     'correct': value == expected and ('database' in row['unresolvedFields']) == (expected is None)})
    reports[version] = {'saved_response': actual, 'controlled_cases': {
        'total': len(rows), 'normal': sum(expected is not None for _, _, expected in CASES),
        **{key: sum(r[key] for r in rows) for key in ('false_merge', 'normal_missing', 'unresolved', 'correct')},
        'rows': rows}}

assert all(profiles['before'][k][f] == profiles['after'][k][f]
           for k in ('data', 'sources', 'evidence') for f in FIELDS if f != 'database')
reports['invariants'] = {'other_fields_unchanged': True, 'source_hashes_unchanged': True,
                         'new_model_calls': 0, 'network_allowed': False,
                         'user_approval_added': False}
report_name = sys.argv[1] if len(sys.argv) == 2 else 'comparison.json'
if Path(report_name).name != report_name or not report_name.endswith('.json'):
    raise ValueError('report must be a new JSON filename within the experiment folder')
with (out / report_name).open('x', encoding='utf-8') as stream:
    json.dump(reports, stream, ensure_ascii=False, indent=2)
for version in ('before', 'after'):
    print(json.dumps({'version': version, 'saved_response': reports[version]['saved_response'],
        'controlled_cases': {k: v for k, v in reports[version]['controlled_cases'].items() if k != 'rows'}}, ensure_ascii=False))
print(json.dumps(reports['invariants']))
