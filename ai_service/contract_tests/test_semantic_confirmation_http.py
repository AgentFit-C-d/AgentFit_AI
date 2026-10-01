"""Real AI HTTP -> gateway -> mock draft -> explicit authenticated save."""
import unittest
from agentfit_ai.http_service import create_app
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.candidate_semantic_assessment import validate_assessments, semantic_labels
from agentfit_ai.profile import FIELDS
from contract_mock.server import create_mock_app
from contract_mock.store import MockStore
from test_mock_http import client


class SemanticHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_unassigned_questions_survive_save_as_pending_not_approved(self):
        store = MockStore()
        document = 'Aster mentions React.'
        def analyze(text, document_id):
            start = text.index('React')
            frozen = {'candidates': [{'id': 'C018', 'start': start, 'end': start + 5}], 'rejected': []}
            records = validate_assessments(text, frozen, [{'id': 'C018', 'field': 'other',
                'modelStatus': 'confirmed', 'mentionKind': 'unclear', 'scope': 'unclear', 'time': 'current', 'polarity': 'positive',
                'commitment': 'unclear', 'role': 'unclear', 'conflictsChecked': True,
                'support': [{'quote': text, 'occurrence': 0}], 'counterEvidence': []}])
            result = finalize_candidate_analysis(text, document_id, frozen, semantic_labels(records),
                {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
            result.update(modelDecisions=records, outcome='needs_confirmation', reviewIssueCount=1)
            return project_candidate_confirmation(text, document_id, result)
        app = create_mock_app(store=store, ai_app=create_app(internal_token='mock-internal',
                             analyze=analyze, analysis_mode='integrated-nvidia'))
        async with client(app) as http:
            project = (await http.post('/api/projects', json={'name': 'Aster'})).json()['project']['id']
            response = await http.post(f'/api/projects/{project}/analysis', content=document.encode(),
                                      headers={'Content-Type': 'text/plain'})
            self.assertEqual(response.status_code, 200, response.text)
            draft = response.json()['draft']
            review = store.confirmation_provenance('owner-a', project)['draftReview']
            self.assertEqual(review['questions'], [])
            self.assertEqual(review['unassignedQuestions'][0]['candidateIds'], ['C018'])
            saved = await http.patch(f'/api/projects/{project}/profile', json={'expectedVersion': 0,
                                    'draftId': draft['id'], 'draftVersion': 1, 'data': draft['data']})
            self.assertEqual(saved.status_code, 200, saved.text)
            approval = store.confirmation_provenance('owner-a', project)['confirmations'][0]
            self.assertEqual(approval['pendingModelQuestions'], review['unassignedQuestions'])
            self.assertEqual(approval['modelDecisions'][0]['decision'], 'needs_confirmation')
            self.assertEqual(approval['modelDecisions'][0]['mentionKind'], 'unclear')
            self.assertEqual(approval['modelDecisions'][0]['modelStatus'], 'confirmed')
            self.assertEqual({r['userDecision'] for r in approval['fields'].values()}, {'unknown'})

    async def test_model_decisions_survive_both_http_boundaries_without_approving(self):
        store = MockStore()
        document = 'Aster adopts React.'
        def analyze(text, document_id):
            frozen = {'candidates': [{'id': 'C018', 'start': 13, 'end': 18}], 'rejected': []}
            records = validate_assessments(text, frozen, [{'id': 'C018', 'field': 'frontend',
                'modelStatus': 'confirmed', 'mentionKind': 'other', 'scope': 'target', 'time': 'current', 'polarity': 'positive',
                'commitment': 'adopted', 'role': 'product_fact', 'conflictsChecked': True,
                'support': [{'quote': text, 'occurrence': 0}], 'counterEvidence': []}])
            result = finalize_candidate_analysis(text, document_id, frozen, semantic_labels(records),
                {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
            result['modelDecisions'] = records
            return project_candidate_confirmation(text, document_id, result)
        app = create_mock_app(store=store, ai_app=create_app(internal_token='mock-internal',
                             analyze=analyze, analysis_mode='integrated-nvidia'))
        async with client(app) as http:
            project = (await http.post('/api/projects', json={'name': 'Aster'})).json()['project']['id']
            response = await http.post(f'/api/projects/{project}/analysis', content=document.encode(),
                                      headers={'Content-Type': 'text/plain'})
            self.assertEqual(response.status_code, 200, response.text)
            draft = response.json()['draft']
            proof = store.confirmation_provenance('owner-a', project)
            self.assertEqual(proof['draftReview']['modelDecisions'][0]['modelStatus'], 'confirmed')
            self.assertEqual(proof['confirmations'], [])
            self.assertIsNone((await http.get(f'/api/projects/{project}')).json()['confirmed'])
            saved = await http.patch(f'/api/projects/{project}/profile', json={'expectedVersion': 0,
                                    'draftId': draft['id'], 'draftVersion': 1, 'data': draft['data']})
            self.assertEqual(saved.status_code, 200, saved.text)
            proof = store.confirmation_provenance('owner-a', project)['confirmations'][0]
            self.assertEqual(proof['actor'], 'owner-a')
            self.assertEqual(proof['modelDecisions'][0]['modelStatus'], 'confirmed')
            self.assertEqual(proof['modelDecisions'][0]['mentionKind'], 'other')
            self.assertEqual(proof['fields']['frontend']['userDecision'], 'confirmed')


if __name__ == '__main__': unittest.main()
