"""The request worker owns the integrated analysis and both provider connections."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from agentfit_ai.analysis_worker import execute_request
from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.candidate_service_worker import execute_integrated_analysis
from agentfit_ai.solar import AnalysisError, post_solar_inline
from agentfit_ai.nvidia_streaming import post_nvidia_streaming_inline
from test_candidate_confirmation import DOCUMENT, DOCUMENT_ID, result


SOLAR_KEY = 'synthetic-solar-secret'
NVIDIA_KEY = 'synthetic-nvidia-secret'


def request(**changes):
    value = {'document': DOCUMENT, 'documentId': DOCUMENT_ID, 'key': SOLAR_KEY,
             'nvidiaKey': NVIDIA_KEY, 'mode': 'integrated-candidates'}
    value.update(changes)
    return json.dumps(value).encode()


class IntegratedWorkerTests(unittest.TestCase):
    def test_worker_selects_integrated_pipeline_with_inline_transports_and_v2_projection(self):
        supplied = result()
        saved = deepcopy(supplied)
        with patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()), patch(
                'agentfit_ai.candidate_service_worker.analyze_integrated_candidates', return_value=supplied) as pipeline, patch(
                'agentfit_ai.analysis_worker.SolarAnalyzer') as old:
            output = json.loads(execute_request(request()))
        self.assertEqual(output['contract'], 'confirmation-v2')
        self.assertEqual(output['outcome'], 'needs_confirmation')
        self.assertEqual(output['profile'], supplied['profile'])
        self.assertEqual(output['fieldStates']['frontend'], 'suggested')
        self.assertEqual(len(output['questions']), 4)
        self.assertEqual(supplied, saved)
        pipeline.assert_called_once_with(DOCUMENT, DOCUMENT_ID, SOLAR_KEY, NVIDIA_KEY,
            solar_transport=post_solar_inline, nvidia_transport=post_nvidia_streaming_inline)
        old.assert_not_called()
        self.assertNotIn(SOLAR_KEY, json.dumps(output))
        self.assertNotIn(NVIDIA_KEY, json.dumps(output))

    def test_missing_sdk_is_safe_configuration_error_before_pipeline(self):
        with patch('agentfit_ai.candidate_service_worker.find_spec', return_value=None), patch(
                'agentfit_ai.candidate_service_worker.analyze_integrated_candidates') as pipeline:
            output = json.loads(execute_request(request()))
        self.assertEqual(output, {'error': 'INTEGRATED_RUNTIME_UNAVAILABLE'})
        pipeline.assert_not_called()

    def test_pipeline_failure_emits_only_safe_v2_failure(self):
        cases = ((CandidatePipelineError('COVERAGE_REVIEW_FAILED', 'PROVIDER_TIMEOUT'), 'PROVIDER_TIMEOUT'),
                 (CandidatePipelineError('EXTRACTION_FAILED', detail='CALL_BUDGET_EXCEEDED'), 'CALL_LIMIT'),
                 (CandidatePipelineError('private stage', 'private code', 'private detail'), 'ANALYSIS_FAILURE'))
        for error, code in cases:
            with self.subTest(code=code), patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()), patch(
                    'agentfit_ai.candidate_service_worker.analyze_integrated_candidates', side_effect=error):
                output = json.loads(execute_request(request()))
            self.assertEqual(output, {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': code})

    def test_unexpected_exception_and_malformed_result_never_echo_private_material(self):
        for outcome in ('exception', 'invalid'):
            with self.subTest(outcome=outcome), patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()), patch(
                    'agentfit_ai.candidate_service_worker.analyze_integrated_candidates') as pipeline:
                if outcome == 'exception':
                    pipeline.side_effect = RuntimeError(DOCUMENT + SOLAR_KEY + NVIDIA_KEY)
                else:
                    pipeline.return_value = {'raw': DOCUMENT + SOLAR_KEY + NVIDIA_KEY}
                output = execute_request(request())
            self.assertEqual(json.loads(output), {'error': 'ANALYSIS_WORKER_FAILED'})

    def test_keys_inside_input_are_rejected_before_model_call(self):
        for key in (SOLAR_KEY, NVIDIA_KEY):
            with self.subTest(key=key), patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()), patch(
                    'agentfit_ai.candidate_service_worker.analyze_integrated_candidates') as pipeline:
                output = execute_request(request(document=DOCUMENT + key))
            self.assertEqual(json.loads(output), {'error': 'SENSITIVE_CONTENT'})
            pipeline.assert_not_called()

    def test_integrated_wire_request_rejects_missing_extra_or_conflicting_fields(self):
        base = json.loads(request())
        variants = [dict(base, mode='recoverable-solar'), dict(base, extra='private'),
                    dict(base, nvidiaKey=''), dict(base, nvidiaKey=None)]
        missing = dict(base)
        missing.pop('nvidiaKey')
        variants.append(missing)
        for raw in variants:
            with self.subTest(keys=sorted(raw)), patch(
                    'agentfit_ai.candidate_service_worker.execute_integrated_analysis') as integrated:
                output = execute_request(json.dumps(raw).encode())
                self.assertEqual(json.loads(output), {'error': 'ANALYSIS_WORKER_FAILED'})
                integrated.assert_not_called()

    def test_oversized_integrated_output_is_still_bounded(self):
        with patch('agentfit_ai.candidate_service_worker.execute_integrated_analysis',
                   return_value={'private': 'x' * 1_500_000}):
            self.assertEqual(json.loads(execute_request(request())), {'error': 'ANALYSIS_WORKER_FAILED'})


if __name__ == '__main__':
    unittest.main()
