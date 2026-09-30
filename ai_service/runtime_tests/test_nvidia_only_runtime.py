"""Real LangExtract adapter with synthetic provider envelopes; zero external calls."""

import json
import unittest
from unittest.mock import patch

import langextract

from agentfit_ai import candidate_analysis_pipeline as pipeline
from agentfit_ai.candidate_confirmation import (project_candidate_confirmation,
                                               validate_candidate_confirmation)
from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.deepseek_evaluation import MODEL, NVIDIA_REVIEW_MODELS
from agentfit_ai.langextract_solar_trial import extract_candidates
from agentfit_ai.solar import AnalysisError
from test_integrated_runtime import ProviderTransport, DOCUMENT, NVIDIA_KEY


class NvidiaRuntimeTests(unittest.TestCase):
    def run_pipeline(self, transport, **options):
        self.assertTrue(callable(getattr(pipeline, 'analyze_nvidia_candidates', None)),
                        'NVIDIA-only entry point is missing')
        return pipeline.analyze_nvidia_candidates(
            DOCUMENT, 'DOC', NVIDIA_KEY, nvidia_transport=transport, **options)

    def test_real_sdk_one_key_ten_fields_and_existing_v2_contract(self):
        for model in NVIDIA_REVIEW_MODELS:
            provider, trace = ProviderTransport(), []
            with self.subTest(model=model), patch.object(
                    pipeline, 'post_solar', side_effect=AssertionError('Solar forbidden')):
                result = self.run_pipeline(provider, candidate_model=model, call_trace=trace)
                self.assertEqual(result['profile']['data'], {
                    'project_name': 'TestApp', 'project_type': 'web app', 'domain': 'records',
                    'frontend': ['React'], 'backend': ['Go'], 'ai': ['ModelX'],
                    'database': 'SQLite', 'deployment': 'CloudZ',
                    'features': ['기록 저장'], 'external_integrations': ['MailSvc']})
                self.assertEqual(result['profile']['evidence']['features'],
                                 [{'documentId': 'DOC', 'start': 62, 'end': 67}])
                v2 = project_candidate_confirmation(DOCUMENT, 'DOC', result)
                self.assertEqual(validate_candidate_confirmation(DOCUMENT, 'DOC', v2), v2)
                self.assertEqual(v2['contract'], 'confirmation-v2')
                self.assertEqual(len(provider.names), 5)
                self.assertTrue(all(r['provider'] == 'nvidia' for r in trace))

    def test_both_new_stages_reject_wrong_response_model(self):
        for name, stage, count in (
                ('agentfit_langextract_candidates', 'EXTRACTION_FAILED', 1),
                ('agentfit_candidate_labels', 'CLASSIFICATION_FAILED', 3)):
            provider, trace = ProviderTransport(), []
            def transport(payload, key, timeout):
                raw = provider(payload, key, timeout)
                if payload['response_format']['json_schema']['name'] == name:
                    envelope = json.loads(raw)
                    envelope['model'] = 'solar-pro4'
                    return json.dumps(envelope).encode('utf-8')
                return raw
            with self.subTest(stage=stage):
                with self.assertRaises(CandidatePipelineError) as caught:
                    self.run_pipeline(transport, call_trace=trace)
                self.assertEqual((caught.exception.stage, caught.exception.provider_code),
                                 (stage, 'PROVIDER_MODEL'))
                self.assertEqual(len(provider.names), count)

    def test_extractor_default_uses_nvidia_streaming_and_preserves_anchors(self):
        from test_integrated_runtime import response
        calls = []
        def transport(payload, key, timeout):
            calls.append((payload['model'], key, timeout))
            return response({'extractions': [
                {'candidate': 'Y', 'candidate_attributes': {'anchor': 'Y 제안.'}},
                {'candidate': 'Y', 'candidate_attributes': {'anchor': 'Y 확정.'}}]}, MODEL)
        with (patch('agentfit_ai.nvidia_streaming.post_nvidia_streaming', transport),
              patch('agentfit_ai.langextract_solar_trial.post_solar',
                    side_effect=AssertionError('Solar forbidden'))):
            items = extract_candidates('Y 제안.\nY 확정.', NVIDIA_KEY, nvidia_model=MODEL)
        self.assertEqual([item.attributes for item in items],
                         [{'anchor': 'Y 제안.'}, {'anchor': 'Y 확정.'}])
        self.assertEqual(calls, [(MODEL, NVIDIA_KEY, 600)])

    def test_real_sdk_stops_on_rate_limit_without_other_provider(self):
        calls, trace = [], []
        def limited(payload, key, timeout):
            calls.append(payload['model'])
            raise AnalysisError('PROVIDER_RATE_LIMIT')
        with self.assertRaises(CandidatePipelineError) as caught:
            self.run_pipeline(limited, call_trace=trace)
        self.assertEqual((caught.exception.stage, caught.exception.provider_code),
                         ('EXTRACTION_FAILED', 'PROVIDER_RATE_LIMIT'))
        self.assertEqual(calls, [MODEL])
        self.assertEqual(len(trace), 1)


if __name__ == '__main__':
    unittest.main()
