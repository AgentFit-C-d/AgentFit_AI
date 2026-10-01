"""Model certainty is never persisted as the authenticated user's approval."""
from copy import deepcopy
import unittest

from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.candidate_semantic_assessment import validate_assessments, semantic_labels
from agentfit_ai.profile import FIELDS
from contract_mock.schema import ContractError
from contract_mock.store import MockStore

DOC = 'Moss uses React for its client.'


class ConfirmationProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.store = MockStore()
        self.project = self.store.create('alice', 'Moss')['project']['id']

    def draft(self):
        attempt = self.store.begin('alice', self.project, {'kind': 'TEXT', 'displayName': None,
            'byteSize': len(DOC), 'characterCount': len(DOC), 'pageCount': None})
        frozen = {'candidates': [{'id': 'C007', 'start': 10, 'end': 15}], 'rejected': []}
        rows = validate_assessments(DOC, frozen, [{'id': 'C007', 'field': 'frontend',
            'modelStatus': 'confirmed', 'scope': 'target', 'time': 'current', 'polarity': 'positive',
            'commitment': 'adopted', 'role': 'product_fact', 'conflictsChecked': True,
            'support': [{'quote': DOC, 'occurrence': 0}], 'counterEvidence': []}])
        result = finalize_candidate_analysis(DOC, attempt['document']['id'], frozen, semantic_labels(rows),
            {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
        result['modelDecisions'] = rows
        outcome = project_candidate_confirmation(DOC, attempt['document']['id'], result)
        review = {k: outcome[k] for k in ('contract', 'fieldStates', 'questions', 'modelDecisions')}
        return self.store.finish('alice', self.project, attempt['id'], outcome['profile'], review)['draft']

    def test_draft_never_approves_and_explicit_save_records_actor_and_both_versions(self):
        draft = self.draft()
        pending = self.store.confirmation_provenance('alice', self.project)
        self.assertEqual(pending['confirmations'], [])
        self.assertEqual(pending['draftReview']['modelDecisions'][0]['modelStatus'], 'confirmed')
        self.assertIsNone(self.store.detail('alice', self.project)['confirmed'])
        self.store.save('alice', self.project, {'expectedVersion': 0, 'draftId': draft['id'],
                        'draftVersion': draft['version'], 'data': draft['data']})
        proof = self.store.confirmation_provenance('alice', self.project)['confirmations'][0]
        self.assertEqual(proof['actor'], 'alice')
        self.assertEqual(proof['action'], 'USER_SAVE_PROFILE')
        self.assertEqual(proof['draft'], {'id': draft['id'], 'version': 1})
        self.assertEqual(proof['profileVersion'], 1)
        self.assertEqual(proof['fields']['frontend']['action'], 'accepted')
        self.assertEqual(proof['fields']['frontend']['userDecision'], 'confirmed')
        self.assertEqual(proof['fields']['frontend']['source'], 'DOCUMENT')
        self.assertEqual(proof['modelDecisions'][0]['modelStatus'], 'confirmed')
        self.assertEqual(proof['source']['documentId'], draft['evidence']['frontend'][0]['documentId'])
        self.assertTrue(proof['source']['attemptId'])

    def test_edit_reanalysis_and_failed_write_cannot_rewrite_approval_history(self):
        draft = self.draft()
        changed = deepcopy(draft['data']); changed['frontend'] = ['Vue']
        self.store.save('alice', self.project, {'expectedVersion': 0, 'draftId': draft['id'],
            'draftVersion': 1, 'data': changed})
        old = self.store.confirmation_provenance('alice', self.project)['confirmations']
        self.assertEqual(old[0]['fields']['frontend']['action'], 'edited')
        self.assertEqual(old[0]['fields']['frontend']['source'], 'USER')
        self.draft()
        self.assertEqual(self.store.confirmation_provenance('alice', self.project)['confirmations'], old)
        self.assertEqual(old[0]['source']['documentId'], draft['evidence']['frontend'][0]['documentId'])
        self.store.fail_next_write = True
        with self.assertRaises(ContractError):
            self.store.save('alice', self.project, {'expectedVersion': 1, 'data': changed})
        self.assertEqual(self.store.confirmation_provenance('alice', self.project)['confirmations'], old)

    def test_wrong_owner_stale_version_and_forged_user_flags_cannot_approve(self):
        draft = self.draft()
        base = {'expectedVersion': 0, 'draftId': draft['id'], 'draftVersion': 1, 'data': draft['data']}
        for owner, changes in [('bob', {}), ('alice', {'draftVersion': 0}),
                                ('alice', {'userConfirmed': True}), ('alice', {'modelDecisions': []})]:
            with self.subTest(owner=owner, changes=changes), self.assertRaises(ContractError):
                self.store.save(owner, self.project, dict(base, **changes))
        with self.assertRaises(ContractError): self.store.confirmation_provenance('bob', self.project)
        self.assertEqual(self.store.confirmation_provenance('alice', self.project)['confirmations'], [])

    def test_old_draft_approval_never_uses_new_pending_or_failed_attempt_source(self):
        draft = self.draft()
        attempt = self.store.begin('alice', self.project, {'kind': 'TEXT', 'displayName': None,
            'byteSize': 15, 'characterCount': 15, 'pageCount': None})
        self.store.fail('alice', self.project, attempt['id'], 'INTERNAL_ERROR')
        self.store.save('alice', self.project, {'expectedVersion': 0, 'draftId': draft['id'],
            'draftVersion': 1, 'data': draft['data']})
        proof = self.store.confirmation_provenance('alice', self.project)['confirmations'][0]
        self.assertEqual(proof['source']['documentId'], draft['evidence']['frontend'][0]['documentId'])
        self.assertNotEqual(proof['source']['attemptId'], attempt['id'])

    def test_storage_boundary_rejects_added_value_even_without_original_document(self):
        draft = self.draft()
        review = self.store.confirmation_provenance('alice', self.project)['draftReview']
        profile = {k: deepcopy(draft[k]) for k in ('data', 'sources', 'evidence', 'unknownFields')}
        profile['data']['frontend'].append('Vue')
        from contract_mock.schema import check_review
        with self.assertRaises(ContractError): check_review(profile, review)


if __name__ == '__main__': unittest.main()
