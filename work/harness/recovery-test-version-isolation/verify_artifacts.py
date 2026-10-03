"""Audit immutability and original assertions; no test expectation rewriting."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path('E:/AgentFit/output/recovery-test-version-isolation-20261003-v1')


def methods(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ReviewRecoveryTests')
    return {node.name: ast.dump(node, include_attributes=False) for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')}


protected = json.loads((OUT/'protected-before.json').read_bytes())
for name, expected in protected.items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
before = methods(OUT/'test_review_recovery.before.py')
after = methods(ROOT/'ai_service/tests/recovery_preserved_cases.py')
assert before == after, 'Original recovery test bodies or expectations changed'
reports = []
for path in sorted(OUT.glob('cases-*/*-preserved-results.json')):
    data = json.loads(path.read_bytes())
    assert sorted(data['cases']) == sorted(before)
    reports.append({'path': str(path), 'testsRun': data['testsRun'],
                    'outcomes': {key: sum(row['status'] == key for row in data['cases'].values())
                                 for key in ('success', 'failure', 'error', 'skip')},
                    'networkBlocked': data['networkBlocked']})
summary = {'protectedFilesUnchanged': len(protected), 'originalTestBodiesUnchanged': len(before),
           'preservedRuns': reports, 'modelCalls': 0, 'realResume': False, 'automaticMigration': False}
stamp = datetime.now(timezone.utc).strftime('%H%M%S%f')
with (OUT/('integrity-'+stamp+'.json')).open('x', encoding='utf-8') as stream:
    json.dump(summary, stream, ensure_ascii=False, indent=2)
print(json.dumps(summary, ensure_ascii=False, indent=2))
