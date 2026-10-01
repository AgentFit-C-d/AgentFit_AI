"""Captured live assessments are regression inputs, not a claim of model accuracy."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.candidate_semantic_assessment import semantic_labels
from agentfit_ai.candidate_confirmation import project_candidate_confirmation, validate_candidate_confirmation
from agentfit_ai.semantic_confirmation_metadata import unresolved_decision_fields
from agentfit_ai.profile import FIELDS
from contract_mock.store import MockStore
from contract_mock.schema import check_review, ContractError

FIXTURES = Path(__file__).parents[1] / 'tests' / 'fixtures'
CASES = {r['id']: r for r in json.loads((FIXTURES / 'semantic_confirmation_cases.json').read_text(encoding='utf-8'))['cases']}
OBSERVED = json.loads((FIXTURES / 'semantic_confirmation_observed.json').read_text(encoding='utf-8'))


def replay(case, observed, document_id):
    records = deepcopy(observed['records'])
    result = finalize_candidate_analysis(case['document'], document_id, case['frozen'], semantic_labels(records),
        {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
    held = [r for r in records if r['decision'] == 'needs_confirmation']
    result.update(modelDecisions=records, reviewIssueCount=len(held),
                  unresolvedFields=[f for f in FIELDS if f in
                      set(result['unresolvedFields']) | unresolved_decision_fields(records)])
    if held: result['outcome'] = 'needs_confirmation'
    return project_candidate_confirmation(case['document'], document_id, result)


class ObservedRegressionTests(unittest.TestCase):
    def test_original_real_failures_are_present_and_frozen_source_is_intact(self):
        actual = CASES['actual-readme']
        self.assertEqual(hashlib.sha256(actual['document'].encode()).hexdigest(), actual['sourceSha256'])
        negative = {r['id'] for r in actual['gold'] if not r['confirmed']}
        self.assertEqual(sum(r['id'] in negative and r['status'] == 'confirmed'
                             for r in actual['recordedLabels']), 2)
        self.assertEqual(sum(r['confirmed'] for r in actual['gold']), 8)

    def test_real_rejected_invitation_cannot_be_smuggled_back_using_wide_evidence(self):
        case = CASES['actual-readme']
        observation = next(r for r in OBSERVED if r['case'] == case['id'] and r['repetition'] == 0)
        draft = replay(case, observation, 'DOC')
        negative = {r['id'] for r in case['gold'] if not r['confirmed']}
        for candidate in case['frozen']['candidates']:
            if candidate['id'] not in negative: continue
            bad = deepcopy(draft)
            value = case['document'][candidate['start']:candidate['end']]
            bad['profile']['data']['features'].append(value)
            end = max(s['end'] for s in draft['profile']['evidence']['features'])
            bad['profile']['evidence']['features'] = [{'documentId': 'DOC', 'start': candidate['start'], 'end': end}]
            with self.subTest(candidate=candidate['id']):
                with self.assertRaises(ValueError): validate_candidate_confirmation(case['document'], 'DOC', bad)
                review = {k: bad[k] for k in ('contract', 'fieldStates', 'questions', 'modelDecisions')}
                with self.assertRaises(ContractError): check_review(bad['profile'], review)

    def test_all_live_replays_preserve_proposals_and_never_approve_without_user(self):
        for observed in OBSERVED:
            case = CASES[observed['case']]
            with self.subTest(case=case['id'], repetition=observed['repetition']):
                store = MockStore(); project = store.create('owner', 'regression')['project']['id']
                attempt = store.begin('owner', project, {'kind': 'TEXT', 'displayName': None,
                    'byteSize': len(case['document'].encode()), 'characterCount': len(case['document']), 'pageCount': None})
                draft = replay(case, observed, attempt['document']['id'])
                review = {k: v for k, v in draft.items() if k in
                          ('contract', 'fieldStates', 'questions', 'modelDecisions', 'unassignedQuestions')}
                store.finish('owner', project, attempt['id'], draft['profile'], review)
                self.assertIsNone(store.detail('owner', project)['confirmed'])
                self.assertEqual(store.confirmation_provenance('owner', project)['confirmations'], [])
                self.assertEqual(len(draft['questions']) + len(draft.get('unassignedQuestions', [])),
                                 observed['metrics']['question_groups_total'])
                # A scalar conflict must stay visible as a question with all source proposals.
                # It still counts as a Profile omission in quality metrics, never a success.
                positive = {r['id'] for r in case['gold'] if r['confirmed']}
                for r in draft['modelDecisions']:
                    if r['id'] in positive and r['decision'] == 'supported':
                        values = draft['profile']['data'][r['field']]
                        if r['sourceValue'] not in (values if isinstance(values, list) else [values]):
                            self.assertEqual(draft['fieldStates'][r['field']], 'unresolved')
                            self.assertIn(r['field'], [q['field'] for q in draft['questions']])
                        saved_records = store.confirmation_provenance('owner', project)['draftReview']['modelDecisions']
                        self.assertIn(r, saved_records)

    def test_observed_wrong_deployment_causes_real_positive_omission_not_quality_pass(self):
        case = CASES['actual-readme']
        draft = replay(case, OBSERVED[1], 'DOC')
        self.assertIsNone(draft['profile']['data']['deployment'])
        self.assertEqual(draft['fieldStates']['deployment'], 'unresolved')
        self.assertTrue(any(r['sourceValue'] == 'Docker' and r['decision'] == 'supported'
                            for r in draft['modelDecisions']))


if __name__ == '__main__': unittest.main()
