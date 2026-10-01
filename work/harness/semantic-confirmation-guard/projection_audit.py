"""Audit captured classifications through projection; never calls a model or edits gold."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ai_service'))
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.candidate_semantic_assessment import _decision, semantic_labels
from agentfit_ai.semantic_confirmation_metadata import unresolved_decision_fields
from agentfit_ai.profile import FIELDS
from compare import metrics


def project(case, labels, records):
    result = finalize_candidate_analysis(case['document'], case['id'], case['frozen'], labels,
        {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
    if records:
        held = [r for r in records if r['decision'] == 'needs_confirmation']
        unresolved = set(result['unresolvedFields']) | unresolved_decision_fields(records)
        result.update(modelDecisions=records, reviewIssueCount=len(held),
                      unresolvedFields=[f for f in FIELDS if f in unresolved])
        if held: result['outcome'] = 'needs_confirmation'
    return project_candidate_confirmation(case['document'], case['id'], result)


def main():
    cases = json.loads((ROOT / 'ai_service/tests/fixtures/semantic_confirmation_cases.json').read_text(encoding='utf-8'))['cases']
    rows = []
    for experiment in ('semantic-confirmation-guard-v1', 'semantic-confirmation-guard-v2', 'semantic-confirmation-guard-glm-v1'):
        for case in cases:
            candidates = {r['id']: r for r in case['frozen']['candidates']}
            # Deduplicate repeated occurrences only for an additional Profile-value metric.
            # Original occurrence-based classifier metrics and gold remain unchanged.
            expected = {(g['field'], case['document'][candidates[g['id']]['start']:candidates[g['id']]['end']])
                        for g in case['gold'] if g['confirmed']}
            for repetition in range(2):
                for mode in ('baseline', 'guarded'):
                    path = Path('E:/AgentFit/output') / experiment / f"{case['id']}-{mode}-{repetition}.json"
                    observed = json.loads(path.read_text(encoding='utf-8'))
                    assert observed['status'] == 'valid'
                    records = deepcopy(observed['modelDecisions'] or [])
                    for record in records: record['decision'] = _decision(record)
                    labels = semantic_labels(records) if records else observed['labels']
                    draft = project(case, labels, records)
                    values = {(field, value) for field, data in draft['profile']['data'].items()
                              for value in (data if isinstance(data, list) else [] if data is None else [data])}
                    score = metrics(case, labels, records)
                    score.update(profile_expected_unique_values=len(expected),
                        profile_missing_unique_values=len(expected - values),
                        profile_unexpected_unique_values=len(values - expected),
                        missing_values=sorted(expected - values), unexpected_values=sorted(values - expected),
                        field_questions=len(draft['questions']),
                        unassigned_question_groups=len(draft.get('unassignedQuestions', [])),
                        question_groups_total=len(draft['questions']) + len(draft.get('unassignedQuestions', [])),
                        unresolved_fields=[f for f, state in draft['fieldStates'].items() if state == 'unresolved'])
                    rows.append({'experiment': experiment, 'case': case['id'], 'mode': mode,
                                 'repetition': repetition, 'sourceSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                 'metrics': score})
                    print(json.dumps({k: v for k, v in rows[-1].items() if k != 'sourceSha256'}))
    out = Path('E:/AgentFit/output/semantic-confirmation-projection-audit-v1')
    out.mkdir(exist_ok=True)
    with (out / 'summary.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'new_model_calls': 0, 'human_reviewed': False,
            'scope': 'fixed candidate labels through projection only; no live extraction or downstream model review',
            'rows': rows}, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


if __name__ == '__main__': main()
