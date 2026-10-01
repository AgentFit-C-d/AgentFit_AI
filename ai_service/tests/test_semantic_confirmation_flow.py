from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agentfit_ai.candidate_analysis_pipeline import analyze_integrated_candidates
from agentfit_ai.candidate_confirmation import project_candidate_confirmation, validate_candidate_confirmation
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.candidate_semantic_assessment import validate_assessments, semantic_labels
from agentfit_ai.profile import FIELDS
from agentfit_ai.profile import validate_profile
from agentfit_ai.candidate_service_worker import execute_nvidia_analysis
from test_semantic_confirmation_guard import DOCUMENT, FROZEN, assessment
from test_candidate_feature_curation import response


def pipeline_result(held=False):
    records = validate_assessments(DOCUMENT, FROZEN, [assessment(scope='unclear' if held else 'target')])
    result = finalize_candidate_analysis(DOCUMENT, 'DOC', FROZEN, semantic_labels(records),
        {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
    result['modelDecisions'] = records
    if held:
        result.update(outcome='needs_confirmation', unresolvedFields=['frontend'], reviewIssueCount=1)
    return result


class SemanticFlowTests(unittest.TestCase):
    def test_model_confirmed_claim_is_preserved_without_granting_user_approval(self):
        for held in (False, True):
            result = pipeline_result(held)
            draft = project_candidate_confirmation(DOCUMENT, 'DOC', result)
            self.assertEqual(draft['modelDecisions'][0]['modelStatus'], 'confirmed')
            self.assertEqual(draft['fieldStates']['frontend'], 'unresolved' if held else 'suggested')
            self.assertEqual(len(draft['questions']), 1)
            self.assertEqual(draft['outcome'], 'needs_confirmation')
            self.assertEqual(validate_candidate_confirmation(DOCUMENT, 'DOC', draft), draft)
            draft['modelDecisions'][0]['decision'] = 'user_confirmed'
            with self.assertRaises(ValueError):
                validate_candidate_confirmation(DOCUMENT, 'DOC', draft)

    def test_metadata_cannot_hide_review_obligation_or_smuggle_unsupported_profile(self):
        held = project_candidate_confirmation(DOCUMENT, 'DOC', pipeline_result(True))
        for mutate in ('hide', 'smuggle'):
            draft = deepcopy(held)
            if mutate == 'hide':
                draft['fieldStates']['frontend'] = 'unknown'; draft['questions'] = []
            else:
                draft['profile'] = pipeline_result(False)['profile']
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate_candidate_confirmation(DOCUMENT, 'DOC', draft)

    def test_free_text_cannot_be_smuggled_as_a_candidate_id_at_the_http_boundary(self):
        draft = project_candidate_confirmation(DOCUMENT, 'DOC', pipeline_result())
        draft['modelDecisions'][0]['id'] = 'private text instead of an opaque candidate id'
        with self.assertRaises(ValueError):
            validate_candidate_confirmation(DOCUMENT, 'DOC', draft)

    def test_nvidia_worker_explicitly_enables_guard_and_returns_records(self):
        with patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()), patch(
                'agentfit_ai.candidate_service_worker.analyze_nvidia_candidates', return_value=pipeline_result()) as analyze:
            result = execute_nvidia_analysis(DOCUMENT, 'DOC', 'test-key', semantic_assessment=True)
        self.assertTrue(analyze.call_args.kwargs['semantic_assessment'])
        self.assertEqual(result['modelDecisions'][0]['modelStatus'], 'confirmed')

    def test_full_pipeline_uses_assessment_not_legacy_classification_and_holds_ambiguity(self):
        names = []
        def transport(payload, key, timeout):
            name = payload['response_format']['json_schema']['name']; names.append(name)
            if name == 'agentfit_operation_candidates': body = {'mentions': []}
            elif name == 'agentfit_semantic_assessment': body = {'assessments': [assessment(scope='unclear')]}
            elif name == 'agentfit_candidate_source_coverage': body = {'checkedFields': list(FIELDS), 'missingFields': []}
            else: raise AssertionError(name)
            return response(body, model=payload['model'])
        result = analyze_integrated_candidates(DOCUMENT, 'DOC', None, 'test-key',
            candidate_model='deepseek-ai/deepseek-v4.1-flash', nvidia_retry_limit=0,
            semantic_assessment=True, nvidia_transport=transport,
            extractor=lambda *a, **k: [SimpleNamespace(extraction_class='candidate', extraction_text='React')])
        self.assertEqual(result['modelDecisions'][0]['decision'], 'needs_confirmation')
        self.assertEqual(result['unresolvedFields'], ['frontend'])
        self.assertIsNone(result['profile']['data']['frontend'])
        self.assertNotIn('agentfit_candidate_labels', names)

    def test_wide_span_cannot_smuggle_rejected_value_into_supported_field(self):
        document = 'Cedar uses React. Cedar does not use Vue.'
        frozen = {'candidates': [{'id': 'C000', 'start': 11, 'end': 16},
                                {'id': 'C001', 'start': 36, 'end': 39}], 'rejected': []}
        records = validate_assessments(document, frozen, [
            assessment(support=[{'quote': 'Cedar uses React.', 'occurrence': 0}]),
            assessment(id='C001', polarity='negative', modelStatus='negated',
                       support=[{'quote': 'Cedar does not use Vue.', 'occurrence': 0}])])
        result = finalize_candidate_analysis(document, 'DOC', frozen, semantic_labels(records),
            {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
        result['modelDecisions'] = records
        draft = project_candidate_confirmation(document, 'DOC', result)
        draft['profile']['data']['frontend'].append('Vue')
        draft['profile']['evidence']['frontend'] = [{'documentId': 'DOC', 'start': 0, 'end': len(document)}]
        with self.assertRaises(ValueError): validate_candidate_confirmation(document, 'DOC', draft)

    def test_full_pipeline_keeps_unassigned_question_as_needs_confirmation(self):
        def transport(payload, key, timeout):
            name = payload['response_format']['json_schema']['name']
            if name == 'agentfit_operation_candidates': body = {'mentions': []}
            elif name == 'agentfit_semantic_assessment': body = {'assessments': [assessment(field='other', role='unclear')]}
            elif name == 'agentfit_candidate_source_coverage': body = {'checkedFields': list(FIELDS), 'missingFields': []}
            else: raise AssertionError(name)
            return response(body, model=payload['model'])
        result = analyze_integrated_candidates(DOCUMENT, 'DOC', None, 'test-key',
            candidate_model='deepseek-ai/deepseek-v4.1-flash', nvidia_retry_limit=0,
            semantic_assessment=True, nvidia_transport=transport,
            extractor=lambda *a, **k: [SimpleNamespace(extraction_class='candidate', extraction_text='React')])
        self.assertEqual(result['outcome'], 'needs_confirmation')
        draft = project_candidate_confirmation(DOCUMENT, 'DOC', result)
        self.assertEqual(draft['questions'], [])
        self.assertEqual(draft['unassignedQuestions'][0]['candidateIds'], ['C000'])

    def test_supported_value_cannot_be_split_into_unstated_values(self):
        document = 'React Native'
        frozen = {'candidates': [{'id': 'C000', 'start': 0, 'end': 12}], 'rejected': []}
        records = validate_assessments(document, frozen, [assessment(support=[{'quote': document, 'occurrence': 0}])])
        result = finalize_candidate_analysis(document, 'DOC', frozen, semantic_labels(records),
            {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
        result['modelDecisions'] = records
        draft = project_candidate_confirmation(document, 'DOC', result)
        draft['profile']['data']['frontend'] = ['React', 'Native']
        with self.assertRaises(ValueError): validate_candidate_confirmation(document, 'DOC', draft)

    def test_source_written_name_expression_survives_only_as_unresolved(self):
        document = 'Cedar (시더)'
        frozen = {'candidates': [{'id': 'C000', 'start': 0, 'end': 5},
                                {'id': 'C001', 'start': 7, 'end': 9}], 'rejected': []}
        records = validate_assessments(document, frozen, [assessment(id=c['id'], field='project_name',
                    support=[{'quote': document, 'occurrence': 0}]) for c in frozen['candidates']])
        result = finalize_candidate_analysis(document, 'DOC', frozen, semantic_labels(records),
            {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
        result['modelDecisions'] = records
        draft = project_candidate_confirmation(document, 'DOC', result)
        self.assertEqual(draft['profile']['data']['project_name'], document)
        self.assertEqual(draft['fieldStates']['project_name'], 'unresolved')
        validate_candidate_confirmation(document, 'DOC', draft)
        draft['fieldStates']['project_name'] = 'suggested'
        draft['questions'][0]['reason'] = 'CONFIRM_SUGGESTION'
        with self.assertRaises(ValueError): validate_candidate_confirmation(document, 'DOC', draft)

    def test_unassigned_ambiguity_keeps_explicit_question_without_flagging_all_fields(self):
        records = validate_assessments(DOCUMENT, FROZEN, [assessment(field='other', role='unclear')])
        result = finalize_candidate_analysis(DOCUMENT, 'DOC', FROZEN, semantic_labels(records),
            {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
        result.update(modelDecisions=records, outcome='needs_confirmation', reviewIssueCount=1)
        draft = project_candidate_confirmation(DOCUMENT, 'DOC', result)
        self.assertEqual(set(draft['fieldStates'].values()), {'unknown'})
        self.assertEqual(draft['questions'], [])
        self.assertEqual(draft['unassignedQuestions'], [{'questionId': 'review_unassigned', 'candidateIds': ['C000']}])
        self.assertEqual(draft['modelDecisions'][0]['decision'], 'needs_confirmation')
        for replacement in ([], [{'questionId': 'review_unassigned', 'candidateIds': ['C123']}],
                            [{'questionId': 'review_unassigned', 'candidateIds': ['C000', 'C000']}]):
            bad = deepcopy(draft); bad['unassignedQuestions'] = replacement
            with self.assertRaises(ValueError): validate_candidate_confirmation(DOCUMENT, 'DOC', bad)


if __name__ == '__main__': unittest.main()
