"""Independent classification routing through the real shared pipeline meter."""
import json
import unittest
from unittest.mock import patch

from agentfit_ai import candidate_analysis_pipeline as pipeline
from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.deepseek_evaluation import NvidiaAnalyzer
from agentfit_ai.langextract_solar_trial import candidate_payload
from agentfit_ai.solar import AnalysisError
from test_candidate_analysis_pipeline import (ProviderFixture, FACTS, extraction,
                                              SOLAR_KEY, NVIDIA_KEY, DEEPSEEK, GLM)
from test_candidate_feature_curation import response


def nvidia_run(case, **options):
    # Fake SDK extraction/generation only; adapter, meter and all later stages stay real.
    def extract(document, key, *, transport, nvidia_model, **kwargs):
        assert key == NVIDIA_KEY and document == case.document
        NvidiaAnalyzer(key, model=nvidia_model, transport=transport)._send_payload(
            candidate_payload(document, max_tokens=kwargs['max_tokens']),
            ('extractions',), timeout=600)
        return [extraction(value) for value, _ in FACTS] + [extraction(case.values[0])]

    def send(payload, key, timeout):
        if payload['response_format']['json_schema']['name'] == 'agentfit_langextract_candidates':
            assert key == NVIDIA_KEY and timeout == 600
            case.requests.append(payload)
            return response({'extractions': []}, model=payload['model'])
        return case.transport(payload, key, timeout)

    with patch('agentfit_ai.langextract_solar_trial.extract_candidates', extract):
        return pipeline.analyze_nvidia_candidates(case.document, 'DOC', NVIDIA_KEY,
            **dict({'nvidia_transport': send}, **options))


class ClassificationRoutingTests(unittest.TestCase):
    def test_mixed_mode_uses_nvidia_key_only_for_selected_classification_route(self):
        for model in (None, GLM):
            case, trace = ProviderFixture(22), []
            result = case.run(classification_model=model, classification_batch_size=15,
                              review_model=DEEPSEEK, call_trace=trace)
            self.assertEqual(result['profile']['data']['project_name'], 'TestApp')
            self.assertEqual(result['profile']['data']['features'],
                             [f'기록 작업 {i:02}' for i in range(22)])
            self.assertEqual(result['profile']['evidence']['project_name'],
                             [{'documentId': 'DOC', 'start': 0, 'end': 7}])
            classified = [r for r in trace if r['stage'] == 'CLASSIFICATION_FAILED']
            self.assertEqual([r['requested_model'] for r in classified],
                             [GLM if model else 'solar-pro4'] * 3)
            self.assertEqual([r['provider'] for r in classified],
                             ['nvidia' if model else 'solar'] * 3)
            self.assertTrue(all(r['requested_model'] == DEEPSEEK
                for r in trace if r['stage'] != 'CLASSIFICATION_FAILED'))

    def test_nvidia_wrapper_changes_only_classification_and_keeps_default_inheritance(self):
        for options, sizes, model in (({}, [30, 1], DEEPSEEK),
                ({'classification_model': GLM, 'classification_batch_size': 15}, [15, 15, 1], GLM)):
            case, trace, events = ProviderFixture(22), [], []
            result = nvidia_run(case, review_model=DEEPSEEK, call_trace=trace,
                observer=lambda stage, state: events.append(stage), **options)
            self.assertEqual(result['outcome'], 'candidate_profile')
            self.assertEqual(result['profile']['data']['frontend'], ['React'])
            self.assertEqual(result['profile']['evidence']['project_name'],
                             [{'documentId': 'DOC', 'start': 0, 'end': 7}])
            self.assertEqual(events, ['grounded', 'classified', 'reviewed', 'projected'])
            requests = [p for p in case.requests if
                p['response_format']['json_schema']['name'] == 'agentfit_candidate_labels']
            self.assertEqual([p['model'] for p in requests], [model] * len(sizes))
            self.assertEqual([len(json.loads(p['messages'][1]['content'])['candidates'])
                              for p in requests], sizes)
            self.assertTrue(all(r['requested_model'] == DEEPSEEK
                for r in trace if r['stage'] != 'CLASSIFICATION_FAILED'))
            self.assertEqual([r['call_index'] for r in trace], list(range(1, len(trace) + 1)))

    def test_bad_options_stop_before_extraction_in_both_entry_points(self):
        calls = []
        def forbidden(*args, **kwargs):
            calls.append(True)
            raise AssertionError('external work before option validation')
        bad = [('classification_model', value) for value in ('solar-pro4', '', [], True)]
        bad += [('classification_batch_size', value) for value in (0, 16, True, 15.0, '15', None)]
        for mode in ('mixed', 'nvidia'):
            for key, value in bad:
                with self.subTest(mode=mode, key=key, value=value), patch.object(
                        pipeline, 'extract_profile_candidates', forbidden), self.assertRaises(ValueError):
                    if mode == 'mixed':
                        pipeline.analyze_integrated_candidates('App', 'DOC', SOLAR_KEY, NVIDIA_KEY,
                            solar_transport=forbidden, nvidia_transport=forbidden, **{key: value})
                    else:
                        pipeline.analyze_nvidia_candidates('App', 'DOC', NVIDIA_KEY,
                            nvidia_transport=forbidden, **{key: value})
        self.assertEqual(calls, [])

    def test_falsey_selected_transport_cannot_fall_back_to_network(self):
        case = ProviderFixture(1)
        class Local:
            def __bool__(self): return False
            def __call__(self, payload, key, timeout):
                return case.transport(payload, key, timeout)
        with patch.object(pipeline, 'post_nvidia_streaming',
                          side_effect=AssertionError('unexpected external transport')):
            result = case.run(classification_model=GLM, classification_batch_size=15,
                              nvidia_transport=Local())
        self.assertEqual(result['profile']['data']['project_name'], 'TestApp')

    def test_shared_budget_counts_each_smaller_batch_and_blocks_before_next_send(self):
        case, trace = ProviderFixture(22), []
        with self.assertRaises(CandidatePipelineError) as caught:
            nvidia_run(case, classification_model=GLM, classification_batch_size=15,
                       max_calls=4, call_trace=trace)
        self.assertEqual((caught.exception.stage, caught.exception.detail),
                         ('CLASSIFICATION_FAILED', 'CALL_BUDGET_EXCEEDED'))
        self.assertEqual(len(trace), 4)
        self.assertEqual(len(case.requests), 4)
        self.assertEqual([r['stage'] for r in trace],
                         ['EXTRACTION_FAILED', 'OPERATION_EXTRACTION_FAILED',
                          'CLASSIFICATION_FAILED', 'CLASSIFICATION_FAILED'])

    def test_last_classification_failure_stops_review_without_retry_or_partial_profile(self):
        for code in ('PROVIDER_RATE_LIMIT', 'PROVIDER_UNAVAILABLE', 'invalid_labels'):
            case, trace, events, sent = ProviderFixture(22), [], [], []
            original = case.transport
            def transport(payload, key, timeout):
                name = payload['response_format']['json_schema']['name']
                if name == 'agentfit_candidate_labels':
                    sent.append(True)
                    if len(sent) == 3:
                        if code == 'invalid_labels':
                            return response({'labels': []}, model=payload['model'])
                        raise AnalysisError(code)
                return original(payload, key, timeout)
            case.transport = transport
            with self.subTest(code=code), self.assertRaises(CandidatePipelineError) as caught:
                nvidia_run(case, classification_model=GLM, classification_batch_size=15,
                    call_trace=trace, observer=lambda stage, state: events.append(stage))
            self.assertEqual(caught.exception.stage, 'CLASSIFICATION_FAILED')
            self.assertEqual(caught.exception.detail if code == 'invalid_labels'
                else caught.exception.provider_code,
                'LABEL_COUNT_MISMATCH' if code == 'invalid_labels' else code)
            self.assertEqual(events, ['grounded'])
            self.assertEqual(len(sent), 3)
            self.assertEqual(len(trace), 5)
            self.assertTrue(all(r['attempt'] == 1 for r in trace))
            for forbidden in (NVIDIA_KEY, SOLAR_KEY, 'TestApp', '기록 작업'):
                self.assertNotIn(forbidden, json.dumps(trace, ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
