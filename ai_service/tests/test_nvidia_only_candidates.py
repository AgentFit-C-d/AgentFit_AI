"""NVIDIA-only routing, cost-stop boundaries and shared pipeline contracts."""

import json
import unittest
from unittest.mock import patch

from agentfit_ai import candidate_analysis_pipeline as pipeline
from agentfit_ai.candidate_first_profile import CandidatePipelineError, classify_profile_candidates
from agentfit_ai.deepseek_evaluation import NvidiaAnalyzer
from agentfit_ai.langextract_solar_trial import candidate_payload
from agentfit_ai.solar import AnalysisError
from test_candidate_analysis_pipeline import (ProviderFixture, FACTS, extraction,
                                              NVIDIA_KEY, DEEPSEEK, GLM, KIMI)


class NvidiaOnlyTests(unittest.TestCase):
    def invoke(self, case, **options):
        self.assertTrue(callable(getattr(pipeline, 'analyze_nvidia_candidates', None)),
                        'NVIDIA-only entry point is missing')
        def extract(document, key, *, transport, nvidia_model, **kwargs):
            self.assertEqual((document, key), (case.document, NVIDIA_KEY))
            # SDK resolution is exercised separately; generation/parser/meter stay real.
            NvidiaAnalyzer(key, transport=transport, model=nvidia_model)._send_payload(
                candidate_payload(document, max_tokens=kwargs['max_tokens']),
                ('extractions',), timeout=600)
            return [extraction(value) for value, _ in FACTS] + [extraction(case.values[0])]
        original = case.transport
        def transport(payload, key, timeout):
            name = payload['response_format']['json_schema']['name']
            if name == 'agentfit_langextract_candidates':
                from test_candidate_feature_curation import response
                self.assertEqual(key, NVIDIA_KEY)
                case.requests.append(payload)
                return response({'extractions': []}, model=payload['model'])
            return original(payload, key, timeout)
        with (patch('agentfit_ai.langextract_solar_trial.extract_candidates', extract),
              patch.object(pipeline, 'post_solar', side_effect=AssertionError('Solar forbidden'))):
            return pipeline.analyze_nvidia_candidates(
                case.document, 'DOC', NVIDIA_KEY,
                **dict({'nvidia_transport': transport}, **options))

    def test_one_key_routes_all_stages_and_preserves_profile_and_private_trace(self):
        for model in (DEEPSEEK, GLM, KIMI):
            case, trace = ProviderFixture(1), []
            with self.subTest(model=model):
                result = self.invoke(case, candidate_model=model, call_trace=trace)
                self.assertEqual(result['outcome'], 'candidate_profile')
                self.assertEqual(result['profile']['data']['frontend'], ['React'])
                self.assertEqual(result['profile']['evidence']['project_name'],
                                 [{'documentId': 'DOC', 'start': 0, 'end': 7}])
                self.assertEqual([p['model'] for p in case.requests],
                                 [model, DEEPSEEK, model, GLM, GLM])
                self.assertEqual([r['provider'] for r in trace], ['nvidia'] * 5)
                self.assertEqual([r['call_index'] for r in trace], [1, 2, 3, 4, 5])
                self.assertNotIn(NVIDIA_KEY, json.dumps(trace))
                self.assertNotIn('TestApp', json.dumps(trace))

    def test_new_default_transport_is_nvidia_streaming(self):
        case = ProviderFixture(1)
        # Exercise classifier's own default selection without any pipeline wiring.
        with (patch('agentfit_ai.nvidia_streaming.post_nvidia_streaming', case.transport),
              patch('agentfit_ai.candidate_first_profile.post_solar',
                    side_effect=AssertionError('Solar forbidden'))):
            labels = classify_profile_candidates(case.document,
                {'candidates': [{'id': 'C000', 'start': 0, 'end': 7}], 'rejected': []},
                NVIDIA_KEY, nvidia_model=DEEPSEEK)
        self.assertEqual(labels, [{'id': 'C000', 'field': 'project_name', 'status': 'confirmed'}])
        self.assertEqual(case.requests[0]['model'], DEEPSEEK)

    def test_invalid_options_and_mixed_secrets_fail_before_any_extraction(self):
        bad = [('solar_key', 'other-secret'), ('solar_transport', lambda *a: b''),
               ('candidate_model', 'solar-pro4'), ('candidate_model', []),
               ('nvidia_key', ''), ('nvidia_retry_limit', 1),
               ('document', NVIDIA_KEY), ('document_id', NVIDIA_KEY)]
        for name, value in bad:
            options = dict(document='Synthetic app', document_id='DOC', solar_key=None,
                           nvidia_key=NVIDIA_KEY, candidate_model=DEEPSEEK,
                           nvidia_retry_limit=0)
            options[name] = value
            with self.subTest(name=name), patch.object(
                    pipeline, 'extract_profile_candidates', side_effect=AssertionError('too early')):
                with self.assertRaises(ValueError):
                    pipeline.analyze_integrated_candidates(**options)

    def test_budget_includes_extraction_and_stops_before_next_send(self):
        case, trace = ProviderFixture(1), []
        with self.assertRaises(CandidatePipelineError) as caught:
            self.invoke(case, max_calls=1, call_trace=trace)
        self.assertEqual((caught.exception.stage, caught.exception.detail),
                         ('OPERATION_EXTRACTION_FAILED', 'CALL_BUDGET_EXCEEDED'))
        self.assertEqual(len(case.requests), 1)
        self.assertEqual(len(trace), 1)

    def test_rate_limit_or_outage_is_not_retried_even_when_extractor_swallows_it(self):
        for code in ('PROVIDER_RATE_LIMIT', 'PROVIDER_UNAVAILABLE', 'PROVIDER_AUTH',
                     'PROVIDER_REQUEST', 'PROVIDER_TIMEOUT'):
            calls, trace = [], []
            def fail(payload, key, timeout):
                calls.append(True)
                raise AnalysisError(code)
            def swallowing(document, key, *, transport, **kwargs):
                for _ in range(2):
                    try:
                        transport({'model': DEEPSEEK}, key, 600)
                    except AnalysisError:
                        pass
                return [extraction('Synthetic app')]
            with self.subTest(code=code), patch(
                    'agentfit_ai.langextract_solar_trial.extract_candidates', swallowing):
                self.assertTrue(callable(getattr(pipeline, 'analyze_nvidia_candidates', None)))
                with self.assertRaises(CandidatePipelineError) as caught:
                    pipeline.analyze_nvidia_candidates('Synthetic app', 'DOC', NVIDIA_KEY,
                        nvidia_transport=fail, call_trace=trace)
                self.assertEqual((caught.exception.stage, caught.exception.provider_code),
                                 ('EXTRACTION_FAILED', code))
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(trace), 1)
                self.assertEqual(trace[0]['attempt'], 1)


if __name__ == '__main__':
    unittest.main()
