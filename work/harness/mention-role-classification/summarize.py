"""Summarize frozen observations locally; never imports a model transport."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path('E:/AgentFit/output/mention-role-classification-v1')


def totals(rows):
    keys = ('candidates', 'normal_information', 'false_confirmations', 'normal_misses',
            'needs_confirmation', 'unpreserved_ambiguity')
    return {key: sum(row[key] for row in rows) for key in keys}


def function(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    return ast.dump(next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name))


live = json.loads((OUT / 'live-summary.json').read_text(encoding='utf-8'))
fixed = json.loads((OUT / 'fixed.json').read_text(encoding='utf-8'))
freeze = json.loads((OUT / 'freeze.json').read_text(encoding='utf-8'))
report = {'live': {}, 'fixed': {side: totals([row[side] for row in fixed['rows']]) for side in ('before', 'after')},
          'calls': len(live['calls']), 'completed_calls': sum(row['completed'] for row in live['calls']),
          'call_seconds': round(sum(row['elapsed_seconds'] for row in live['calls']), 3)}
for version in ('before', 'after_prompt', 'after_structured'):
    rows = [row for row in live['rows'] if row['version'] == version]
    assert len(rows) == 6 and all(row['status'] == 'valid' for row in rows)
    summary = totals([row['metrics'] for row in rows])
    summary['status_counts'] = dict(Counter(label['status'] for row in rows for label in row['labels']))
    summary['false_observations'] = [{'case': row['case'], **label} for row in rows for label in row['labels']
                                   if label['id'] in row['metrics']['false_ids']]
    summary['excluded_roles'] = dict(Counter(record['mentionKind'] for row in rows
        for record in row['modelDecisions'] if record['decision'] == 'excluded'))
    report['live'][version] = summary

# The discarded prompt experiment is preserved byte-for-byte. The adopted
# structured classifier and all its frozen dependencies still match the run.
changed = [path for path, digest in freeze['files'].items()
           if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest]
first = ROOT / 'ai_service/agentfit_ai/candidate_first_profile.py'
tested = OUT / 'tested_candidate_first_profile.py'
assert changed == [str(first)], changed
assert hashlib.sha256(tested.read_bytes()).hexdigest() == freeze['files'][str(first)]
assert function(first, '_source_mention') == function(tested, '_source_mention')
report['post_run_change'] = 'Only legacy prompt addition withdrawn; structured runtime/dependencies unchanged.'
with (OUT / 'summary.json').open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps(report, ensure_ascii=False))
