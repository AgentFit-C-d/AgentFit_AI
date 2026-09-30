"""Preserve grounded suggestions while making confirmation obligations explicit."""
from copy import deepcopy
import unittest

from agentfit_ai.candidate_confirmation import (
    project_candidate_confirmation, validate_candidate_confirmation,
)
from agentfit_ai.profile import FIELDS, ProfileValidationError, check_profile_snapshot, validate_profile


DOCUMENT = 'Alpha\nReact\n기록 저장\n외부 연동 없음'
DOCUMENT_ID = 'DOC'


def result():
    data = dict.fromkeys(FIELDS)
    data.update(project_name='Alpha', frontend=['React'], features=['기록 저장'],
                external_integrations=[])
    evidence = {field: [] for field in FIELDS}
    for field, start, end in (('project_name', 0, 5), ('frontend', 6, 11),
                              ('features', 12, 17), ('external_integrations', 18, len(DOCUMENT))):
        evidence[field] = [{'start': start, 'end': end}]
    return {'outcome': 'candidate_profile',
            'profile': validate_profile(DOCUMENT, DOCUMENT_ID, {'data': data, 'evidence': evidence}),
            'unresolvedFields': [], 'rejectedCandidateCount': 0, 'candidateCount': 4,
            'rejectedReasons': {}, 'reviewIssueCount': 0}


class CandidateConfirmationTests(unittest.TestCase):
    def test_reviewed_values_still_require_confirmation_and_empty_array_is_not_unknown(self):
        original = result()
        saved = deepcopy(original)
        draft = project_candidate_confirmation(DOCUMENT, DOCUMENT_ID, original)
        self.assertEqual(draft['contract'], 'confirmation-v2')
        self.assertEqual(draft['outcome'], 'needs_confirmation')
        self.assertEqual(draft['error'], 'REVIEW_CONFIRMATION_REQUIRED')
        self.assertEqual(draft['profile'], original['profile'])
        self.assertEqual(draft['fieldStates'], {
            'project_name': 'suggested', 'project_type': 'unknown', 'domain': 'unknown',
            'frontend': 'suggested', 'backend': 'unknown', 'ai': 'unknown',
            'database': 'unknown', 'deployment': 'unknown', 'features': 'suggested',
            'external_integrations': 'suggested'})
        self.assertEqual(draft['questions'], [
            {'field': field, 'reason': 'CONFIRM_SUGGESTION', 'questionId': 'confirm_' + field}
            for field in ('project_name', 'frontend', 'features', 'external_integrations')])
        self.assertEqual(set(draft), {'contract', 'outcome', 'profile', 'fieldStates', 'questions', 'error'})
        self.assertEqual(original, saved)
        self.assertEqual(validate_candidate_confirmation(DOCUMENT, DOCUMENT_ID, draft), draft)
        draft['profile']['data']['frontend'].append('untrusted modification')
        self.assertEqual(original, saved)

    def test_unresolved_nonnull_and_null_fields_keep_their_distinct_proposals_and_evidence(self):
        original = result()
        original.update(outcome='needs_confirmation', unresolvedFields=['frontend', 'backend'],
                        reviewIssueCount=2)
        draft = project_candidate_confirmation(DOCUMENT, DOCUMENT_ID, original)
        self.assertEqual(draft['profile']['data']['frontend'], ['React'])
        self.assertEqual(draft['profile']['evidence']['frontend'],
                         [{'documentId': 'DOC', 'start': 6, 'end': 11}])
        self.assertIsNone(draft['profile']['data']['backend'])
        self.assertEqual(draft['fieldStates']['frontend'], 'unresolved')
        self.assertEqual(draft['fieldStates']['backend'], 'unresolved')
        self.assertEqual([q for q in draft['questions'] if q['reason'] == 'REVIEW_ISSUE'], [
            {'field': 'frontend', 'reason': 'REVIEW_ISSUE', 'questionId': 'confirm_frontend'},
            {'field': 'backend', 'reason': 'REVIEW_ISSUE', 'questionId': 'confirm_backend'}])
        self.assertEqual(validate_candidate_confirmation(DOCUMENT, DOCUMENT_ID, draft), draft)

    def test_unlocated_issue_requires_all_fields_without_erasing_values(self):
        for changes in (
                {'outcome': 'needs_confirmation'},
                {'outcome': 'needs_confirmation', 'unresolvedFields': ['features'],
                 'rejectedCandidateCount': 1, 'rejectedReasons': {'source_quote_absent': 1}}):
            with self.subTest(changes=changes):
                original = result()
                original.update(changes)
                draft = project_candidate_confirmation(DOCUMENT, DOCUMENT_ID, original)
                self.assertEqual(draft['profile'], original['profile'])
                self.assertEqual(set(draft['fieldStates'].values()), {'unresolved'})
                self.assertEqual([q['field'] for q in draft['questions']], list(FIELDS))
                self.assertEqual({q['reason'] for q in draft['questions']}, {'REVIEW_ISSUE'})
                self.assertEqual(validate_candidate_confirmation(DOCUMENT, DOCUMENT_ID, draft), draft)

    def test_empty_candidates_require_missing_questions_for_all_fields(self):
        original = result()
        original.update(outcome='needs_confirmation', candidateCount=0,
            profile=validate_profile(DOCUMENT, DOCUMENT_ID, {
                'data': dict.fromkeys(FIELDS), 'evidence': {f: [] for f in FIELDS}}))
        draft = project_candidate_confirmation(DOCUMENT, DOCUMENT_ID, original)
        self.assertEqual(set(draft['fieldStates'].values()), {'unresolved'})
        self.assertEqual(len(draft['questions']), 10)
        self.assertEqual({q['reason'] for q in draft['questions']}, {'CANDIDATE_MISSING'})

    def test_inconsistent_or_untrusted_pipeline_metadata_is_rejected(self):
        for changes in (
                {'outcome': 'complete'}, {'outcome': 'candidate_profile', 'unresolvedFields': ['features']},
                {'candidateCount': 0}, {'candidateCount': True}, {'candidateCount': -1},
                {'outcome': 'needs_confirmation', 'candidateCount': 0},
                {'candidateCount': 241}, {'reviewIssueCount': 1}, {'reviewIssueCount': False},
                {'rejectedCandidateCount': -1}, {'rejectedCandidateCount': 1},
                {'rejectedReasons': {'source_quote_absent': True}}, {'rejectedReasons': []},
                {'outcome': 'needs_confirmation', 'unresolvedFields': ['features', 'features']},
                {'unresolvedFields': [None]}, {'unresolvedFields': 'features'},
                {'unresolvedFields': ['outside']}, {'rawResponse': 'private fixture'},
                {'featureCuration': {'candidateCount': 4, 'selectedCount': 31, 'uncoveredCount': 0}},
                {'featureCuration': {'candidateCount': 4, 'selectedCount': 1, 'uncoveredCount': 1}},
                {'featureCuration': {'candidateCount': 4, 'selectedCount': 1, 'extra': 'private'}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                original = result()
                original.update(changes)
                project_candidate_confirmation(DOCUMENT, DOCUMENT_ID, original)

    def test_curation_metadata_is_validated_then_not_exposed(self):
        original = result()
        original['featureCuration'] = {'candidateCount': 1, 'selectedCount': 1, 'uncoveredCount': 0}
        draft = project_candidate_confirmation(DOCUMENT, DOCUMENT_ID, original)
        self.assertNotIn('featureCuration', draft)
        self.assertNotIn('rejectedReasons', draft)

    def test_profile_snapshot_rejects_wrong_source_identity_span_and_derived_metadata(self):
        for mutate in (
                lambda p: p['evidence']['project_name'][0].update(documentId='OTHER'),
                lambda p: p['evidence']['project_name'][0].update(start=1),
                lambda p: p['evidence']['project_name'][0].update(extra='private'),
                lambda p: p['evidence']['project_name'].__setitem__(0, None),
                lambda p: p['sources'].update(project_name='UNKNOWN'),
                lambda p: p['unknownFields'].append('project_name'),
                lambda p: p.update(raw='private'),
                lambda p: p.update(evidence=[])):
            with self.subTest(mutation=mutate):
                original = result()
                mutate(original['profile'])
                with self.assertRaises(ProfileValidationError):
                    check_profile_snapshot(DOCUMENT, DOCUMENT_ID, original['profile'])
                with self.assertRaises(ProfileValidationError):
                    project_candidate_confirmation(DOCUMENT, DOCUMENT_ID, original)

    def test_boundary_rejects_contract_state_and_question_mismatches(self):
        base = project_candidate_confirmation(DOCUMENT, DOCUMENT_ID, result())
        for mutate in (
                lambda d: d.update(contract='confirmation-v1'),
                lambda d: d.update(outcome='complete'),
                lambda d: d.update(error='PRIVATE_ERROR'),
                lambda d: d.update(raw='private'),
                lambda d: d['questions'].pop(),
                lambda d: d['questions'].append(deepcopy(d['questions'][0])),
                lambda d: d['questions'][0].update(reason='REVIEW_ISSUE'),
                lambda d: d['questions'][0].update(questionId='arbitrary'),
                lambda d: d['questions'][0].update(text='private'),
                lambda d: d['questions'][0].update(field='outside'),
                lambda d: d['questions'].__setitem__(0, None),
                lambda d: d['fieldStates'].update(project_name='unknown'),
                lambda d: d['fieldStates'].update(backend='suggested'),
                lambda d: d['fieldStates'].update(backend='unresolved'),
                lambda d: d['fieldStates'].update(backend=[]),
                lambda d: d['fieldStates'].pop('ai'),
                lambda d: d.update(profile=[])):
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                draft = deepcopy(base)
                mutate(draft)
                validate_candidate_confirmation(DOCUMENT, DOCUMENT_ID, draft)

    def test_unresolved_question_cannot_claim_a_reviewed_suggestion(self):
        original = result()
        original.update(outcome='needs_confirmation', unresolvedFields=['features'], reviewIssueCount=1)
        draft = project_candidate_confirmation(DOCUMENT, DOCUMENT_ID, original)
        next(q for q in draft['questions'] if q['field'] == 'features')['reason'] = 'CONFIRM_SUGGESTION'
        with self.assertRaises(ValueError):
            validate_candidate_confirmation(DOCUMENT, DOCUMENT_ID, draft)


if __name__ == '__main__':
    unittest.main()
