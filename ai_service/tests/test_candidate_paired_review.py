"""Same-source comparisons must preserve provider identity and input isolation."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.candidate_split_review import review_candidates_separately
from agentfit_ai.deepseek_evaluation import MODEL, NVIDIA_REVIEW_MODELS
from agentfit_ai.profile import FIELDS
from agentfit_ai.real_document_holdout import PreparedCase
from agentfit_ai.solar import AnalysisError
from tests.test_candidate_split_review import fixture, response


class CandidateReviewerRoutingTests(unittest.TestCase):
    def test_nvidia_receives_its_key_and_preserves_verified_model(self):
        document, frozen, labels = fixture(1)
        for model in NVIDIA_REVIEW_MODELS:
            calls = []
            def transport(payload, key, timeout):
                self.assertEqual(key, 'nvidia-secret')
                self.assertEqual(payload['model'], model)
                self.assertEqual(timeout, 600)
                data = json.loads(payload['messages'][1]['content'])
                self.assertEqual(data['document'], document)
                return response({'checkedCandidateIds': ['C000'], 'wrongCandidateIds': []}
                                if 'selections' in data else
                                {'checkedFields': list(FIELDS), 'missingFields': []}, model=model)
            result = review_candidates_separately(document, frozen, labels, 'nvidia-secret',
                review_model=model, transport=transport, review_calls=calls)
            self.assertEqual(result['wrongCandidateIds'], [])
            self.assertEqual([row['model'] for row in calls], [model, model])

    def test_nvidia_wrong_model_is_rejected_before_projection(self):
        document, frozen, labels = fixture(1)
        with self.assertRaises(AnalysisError) as caught:
            review_candidates_separately(document, frozen, labels, 'secret', review_model=MODEL,
                transport=lambda *args: response({'checkedCandidateIds': ['C000'],
                                                   'wrongCandidateIds': []}))
        self.assertEqual(caught.exception.code, 'PROVIDER_MODEL')

    def test_nvidia_length_never_enters_solar_adaptive_retries(self):
        document, frozen, labels = fixture(20)
        requests, calls = [], []
        def transport(payload, key, timeout):
            requests.append(payload)
            return response({}, finish='length', model=MODEL)
        with self.assertRaises(AnalysisError) as caught:
            review_candidates_separately(document, frozen, labels, 'secret', review_model=MODEL,
                transport=transport, review_calls=calls, adaptive_review=True)
        self.assertEqual(caught.exception.code, 'INCOMPLETE_RESPONSE')
        self.assertEqual(len(requests), 1)
        self.assertNotIn('recovered', calls[0])

    def test_unsupported_review_model_never_calls_transport(self):
        document, frozen, labels = fixture(1)
        with self.assertRaises(ValueError):
            review_candidates_separately(document, frozen, labels, 'secret', review_model='unknown',
                transport=lambda *args: self.fail('invalid model reached transport'))


class CandidateFinalizationTests(unittest.TestCase):
    def test_finalizer_removes_rejected_candidate_without_mutating_shared_input(self):
        from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
        document, frozen, labels = fixture(1)
        original = deepcopy((frozen, labels))
        events = []
        def observer(stage, state):
            events.append(stage)
            state.clear()
        result = finalize_candidate_analysis(document, 'case', frozen, labels,
            {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': ['C000']},
            observer=observer)
        self.assertEqual((frozen, labels), original)
        self.assertEqual(result['outcome'], 'needs_confirmation')
        self.assertIsNone(result['profile']['data']['backend'])
        self.assertEqual(result['unresolvedFields'], ['backend'])
        self.assertEqual(result['reviewIssueCount'], 1)
        self.assertEqual(events, ['reviewed', 'projected'])

    def test_finalizer_rejects_unknown_review_ids(self):
        from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
        document, frozen, labels = fixture(1)
        with self.assertRaises(ValueError):
            finalize_candidate_analysis(document, 'case', frozen, labels,
                {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': ['unknown']})


class CandidatePairedEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.document = 'Torus 토러스. 사용자 제출물의 기술 예: Java. 제품 구현 기술은 미정.'
        self.case = PreparedCase('synthetic', self.document,
            [{'id': 'C01', 'field': 'project_name', 'contains_any': ['Torus']},
             {'id': 'C02', 'field': 'backend', 'expect_null': True}],
            'a' * 64, 'b' * 64, None, 0, 0)
        self.extraction_count = self.classification_count = 0

    def extractor(self, document, key, **kwargs):
        self.extraction_count += 1
        self.assertEqual(key, 'solar-secret')
        return [SimpleNamespace(extraction_class='candidate', extraction_text=value)
                for value in ('Torus', '토러스', 'Java')]

    def classifier(self, document, frozen, key):
        self.classification_count += 1
        self.assertEqual(key, 'solar-secret')
        return [{'id': item['id'], 'field': 'backend' if index == 2 else 'project_name',
                 'status': 'confirmed'} for index, item in enumerate(frozen['candidates'])]

    def test_same_upstream_distinguishes_review_errors_and_projection_conflict(self):
        from agentfit_ai.candidate_paired_review import evaluate_paired
        inputs, updates = [], []
        def reviewer(document, frozen, labels, key, **kwargs):
            inputs.append(deepcopy((document, frozen, labels)))
            model = kwargs['review_model']
            self.assertEqual(key, 'solar-secret' if model == 'solar-pro4' else 'nvidia-secret')
            return {'checkedFields': list(FIELDS), 'missingFields': [],
                    'wrongCandidateIds': [] if model == 'solar-pro4' else ['C002']}
        result = evaluate_paired(self.case, 'solar-secret', 'nvidia-secret', ['solar-pro4', MODEL],
            extractor=self.extractor, classifier=self.classifier, reviewer=reviewer,
            on_update=lambda state: updates.append(deepcopy(state)))
        self.assertEqual(self.extraction_count, 1)
        self.assertEqual(self.classification_count, 1)
        self.assertEqual(inputs[0], inputs[1])
        self.assertEqual(len(updates), 3)  # frozen upstream, then each finished model
        solar, nvidia = result['models']
        self.assertEqual(result['review_settings']['solar-pro4']['reasoning_effort'], 'medium')
        self.assertEqual(result['review_settings'][MODEL]['chat_template_kwargs'], {'thinking': False})
        self.assertEqual(solar['suggestion_matched'], 0)
        self.assertEqual(nvidia['suggestion_matched'], 1)
        self.assertEqual(nvidia['fields']['project_name']['projection_reason'], 'multiple_scalar_values')
        self.assertEqual(nvidia['fields']['backend']['confirmed_after'], 0)
        self.assertEqual(solar['fields']['backend']['confirmed_after'], 1)
        self.assertEqual(result['classification_refs'][2]['start'], self.document.index('Java'))
        serialized = json.dumps(result, ensure_ascii=False)
        for private in ('Torus', '토러스', 'Java', self.document, 'solar-secret', 'nvidia-secret'):
            self.assertNotIn(private, serialized)

    def test_failed_mutating_review_does_not_pollute_next_model(self):
        from agentfit_ai.candidate_paired_review import evaluate_paired
        seen = []
        def reviewer(document, frozen, labels, key, **kwargs):
            seen.append(deepcopy((frozen, labels)))
            if len(seen) == 1:
                frozen['candidates'].clear()
                labels.clear()
                raise AnalysisError('PROVIDER_TIMEOUT')
            return {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': ['C002']}
        result = evaluate_paired(self.case, 'solar-secret', 'nvidia-secret', ['solar-pro4', MODEL],
            extractor=self.extractor, classifier=self.classifier, reviewer=reviewer)
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(result['models'][0]['outcome'], 'failed')
        self.assertEqual(result['models'][0]['provider_error'], 'PROVIDER_TIMEOUT')
        self.assertEqual(result['models'][1]['outcome'], 'needs_confirmation')
        self.assertEqual(result['failed'], 1)

    def test_either_key_in_source_is_rejected_before_any_model_call(self):
        from agentfit_ai.candidate_paired_review import evaluate_paired
        for key in ('solar-secret', 'nvidia-secret'):
            case = PreparedCase('synthetic', self.document + key, self.case.checks,
                                'a' * 64, 'b' * 64, None, 0, 0)
            result = evaluate_paired(case, 'solar-secret', 'nvidia-secret', ['solar-pro4', MODEL],
                extractor=lambda *a, **k: self.fail('secret reached provider'))
            self.assertEqual(result['common_error'], 'SENSITIVE_CONTENT')
            self.assertEqual(result['failed'], 2)
            self.assertTrue(all(row['outcome'] == 'failed' for row in result['models']))

    def test_common_extraction_failure_preserves_all_model_denominators(self):
        from agentfit_ai.candidate_paired_review import evaluate_paired
        def extractor(*args, **kwargs):
            raise AnalysisError('PROVIDER_NETWORK')
        result = evaluate_paired(self.case, 'solar-secret', 'nvidia-secret', ['solar-pro4', MODEL],
            extractor=extractor)
        self.assertEqual(result['common_error'], 'EXTRACTION_FAILED')
        self.assertEqual(result['failed'], 2)
        self.assertEqual([row['review_model'] for row in result['models']], ['solar-pro4', MODEL])

    def test_duplicate_models_rejected_before_extraction(self):
        from agentfit_ai.candidate_paired_review import evaluate_paired
        with self.assertRaises(ValueError):
            evaluate_paired(self.case, 'solar-secret', 'nvidia-secret', [MODEL, MODEL],
                extractor=lambda *a, **k: self.fail('bad comparison reached provider'))

    def test_cli_preserves_same_input_and_writes_safe_terminal_result(self):
        from agentfit_ai.candidate_paired_review import main
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, env, output = root / 'manifest.json', root / '.env', root / 'result.json'
            manifest.write_text(json.dumps({'cases': []}), encoding='utf-8')
            env.write_text('UPSTAGE_API_KEY=solar-secret\nNVIDIA_API_KEY=nvidia-secret\n', encoding='utf-8')
            digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
            argv = ['paired', '--live', '--manifest', str(manifest), '--manifest-sha256', digest,
                    '--env-file', str(env), '--output', str(output), '--case-id', 'H02']
            review = {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': ['C002']}
            with patch('sys.argv', argv), \
                 patch('agentfit_ai.candidate_paired_review.prepare_cases', return_value=[replace(self.case, id='H02')]), \
                 patch('agentfit_ai.candidate_paired_review.extract_profile_candidates', side_effect=self.extractor), \
                 patch('agentfit_ai.candidate_paired_review.classify_profile_candidates', side_effect=self.classifier), \
                 patch('agentfit_ai.candidate_paired_review.review_candidates_separately', return_value=review):
                self.assertEqual(main(), 0)
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['state'], 'finished')
            self.assertEqual(result['total_models'], 2)
            self.assertEqual(result['failed'], 0)
            self.assertEqual(self.extraction_count, 1)
            self.assertTrue(all(row['suggestion_matched'] == 1 for row in result['models']))
            serialized = output.read_text(encoding='utf-8')
            for secret in (self.document, 'solar-secret', 'nvidia-secret', 'Java'):
                self.assertNotIn(secret, serialized)


if __name__ == '__main__':
    unittest.main()
