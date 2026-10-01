"""Reapply final server/boundary rules to captured, grounded model assessments.

No generation or grounding re-run. Original metrics remain untouched.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ai_service'))
from agentfit_ai.candidate_semantic_assessment import _decision, semantic_labels, check_decision_records
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.semantic_confirmation_metadata import unresolved_decision_fields
from agentfit_ai.profile import FIELDS
from compare import metrics

cases = json.loads((ROOT / 'ai_service/tests/fixtures/semantic_confirmation_cases.json').read_text(encoding='utf-8'))['cases']
OUT = Path('E:/AgentFit/output/semantic-confirmation-guard-replay-v1')
OUT.mkdir(exist_ok=True)
rows, fixtures = [], []
for experiment in ('semantic-confirmation-guard-v1', 'semantic-confirmation-guard-v2', 'semantic-confirmation-guard-glm-v1'):
    for case in cases:
        for repetition in range(2):
            source = Path('E:/AgentFit/output') / experiment / f"{case['id']}-guarded-{repetition}.json"
            original = json.loads(source.read_text(encoding='utf-8'))
            assert original['status'] == 'valid'
            records = deepcopy(original['modelDecisions'])
            for record in records:
                record['decision'] = _decision(record)
            check_decision_records(records, document=case['document'])
            labels = semantic_labels(records)
            result = finalize_candidate_analysis(case['document'], case['id'], case['frozen'], labels,
                {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
            held = [r for r in records if r['decision'] == 'needs_confirmation']
            result.update(modelDecisions=records, reviewIssueCount=len(held),
                          unresolvedFields=[f for f in FIELDS if f in unresolved_decision_fields(records)])
            if held: result['outcome'] = 'needs_confirmation'
            draft = project_candidate_confirmation(case['document'], case['id'], result)
            score = metrics(case, labels, records)
            score['field_questions_projection_only'] = len(draft['questions'])
            score['unassigned_question_groups'] = len(draft.get('unassignedQuestions', []))
            score['question_groups_total'] = len(draft['questions']) + score['unassigned_question_groups']
            score['supported_candidates'] = sum(r['decision'] == 'supported' for r in records)
            rows.append({'experiment': experiment, 'case': case['id'], 'repetition': repetition,
                         'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                         'before_server_fix': original['metrics'], 'after_server_fix': score})
            if experiment == 'semantic-confirmation-guard-glm-v1':
                fixtures.append({'case': case['id'], 'repetition': repetition, 'records': records,
                                 'metrics': score, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
            print(json.dumps({'experiment': experiment, 'case': case['id'], 'repetition': repetition, **score}))

for path, data in [(OUT / 'summary.json', {'new_model_calls': 0, 'human_reviewed': False, 'rows': rows}),
                   (ROOT / 'ai_service/tests/fixtures/semantic_confirmation_observed.json', fixtures)]:
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
