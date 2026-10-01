"""Read saved responses and candidate identities; performs no model calls."""
from collections import Counter
import json
from pathlib import Path

OUT = Path('E:/AgentFit/output/semantic-role-service-path-v1')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def inspect(folder):
    result = read(folder / 'response.json')
    body = result['body']
    trace = read(folder / 'trace.json') if (folder / 'trace.json').exists() else {}
    stages = trace.get('stages', {})
    grounded = stages.get('grounded', {}).get('candidates', [])
    reviewed = stages.get('reviewed', {}).get('frozen', {}).get('candidates', grounded)
    records = body.get('modelDecisions', [])
    questions = {q['field'] for q in body.get('questions', [])}
    unassigned = {i for q in body.get('unassignedQuestions', []) for i in q['candidateIds']}
    held = [r for r in records if r['decision'] == 'needs_confirmation']
    missing_questions = [r['id'] for r in held if
        (r['id'] not in unassigned if r['field'] == 'other' else r['field'] not in questions)]
    record_ids = {r['id'] for r in records}
    row = {
        'name': folder.name, 'status': result['status_code'], 'outcome': body.get('outcome'),
        'error': body.get('error'), 'seconds': result['elapsed_seconds'],
        'trace_available': bool(trace),
        'grounded': len(grounded) if trace else None,
        'reviewed': len(reviewed) if trace else None, 'final_records': len(records),
        'grounded_ids_absent_from_reviewed': sorted({c['id'] for c in grounded} - {c['id'] for c in reviewed}) if trace else None,
        'reviewed_ids_without_final_record': sorted({c['id'] for c in reviewed} - record_ids) if trace else None,
        'decision_counts': dict(Counter(r['decision'] for r in records)),
        'held_without_question': missing_questions,
        'started_calls': len(list(folder.glob('*-call-started.json'))),
        'returned_calls': len(list(folder.glob('*-call.json'))),
    }
    if folder.name.startswith('live-'):
        name = folder.name.split('-')[1]
        document = (OUT / (name + '.md')).read_text(encoding='utf-8')
        row['bad_source_values'] = [r['id'] for r in records if
            r['sourceValue'] != document[r['candidate']['start']:r['candidate']['end']]]
        row['held'] = [{k: r[k] for k in ('id', 'sourceValue', 'mentionKind', 'field', 'modelStatus', 'decision')}
                       for r in held]
        row['profile'] = body.get('profile', {}).get('data')
    return row


if __name__ == '__main__':
    fixed = read(OUT / 'fixed-summary.json')['rows']
    for version in ('before', 'after'):
        rows = [r for r in fixed if r['version'] == version]
        print(json.dumps({'fixed': version, 'seconds': round(sum(r['elapsed_seconds'] for r in rows), 3),
            **{key: sum(r['metrics'][key] for r in rows) for key in
               ('false_proposals', 'normal_misses', 'lost_ambiguity', 'questions', 'held_candidates', 'final_records')}},
            ensure_ascii=False))
    for folder in sorted(OUT.iterdir()):
        if folder.is_dir() and (folder / 'response.json').exists():
            print(json.dumps(inspect(folder), ensure_ascii=False))
