"""Stage failures survive worker, HTTP and evaluation boundaries without raw detail."""
import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agentfit_ai.analysis_process import run_analysis_process
from agentfit_ai.analysis_worker import execute_request
from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.candidate_service_worker import execute_integrated_analysis
from agentfit_ai.http_service import create_app
from agentfit_ai.independent_evaluation_worker import execute_request as evaluate
from test_candidate_confirmation import DOCUMENT, DOCUMENT_ID
from test_candidate_service_worker import NVIDIA_KEY, SOLAR_KEY, request
from test_independent_evaluation_worker import packet_fixture
from test_integrated_confirmation_http import HEADERS


STAGES = ('EXTRACTION_FAILED', 'GROUNDING_FAILED', 'OPERATION_EXTRACTION_FAILED',
          'MERGE_FAILED', 'CLASSIFICATION_FAILED', 'COVERAGE_REVIEW_FAILED',
          'FEATURE_CURATION_FAILED', 'PROJECTION_FAILED', 'DIAGNOSTIC_FAILED')
PRIVATE = 'synthetic-private-detail'
FIXTURE = Path(__file__).parent / 'fixtures' / 'failing_candidate_worker.py'


def failed(code):
    return {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': code}


@contextmanager
def pipeline_failure(error):
    with patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()), patch(
            'agentfit_ai.candidate_service_worker.analyze_integrated_candidates', side_effect=error):
        yield


class PipelineFailureStageTests(unittest.TestCase):
    def test_all_nine_stages_survive_serialized_worker_without_detail_or_keys(self):
        for stage in STAGES:
            with self.subTest(stage=stage), pipeline_failure(CandidatePipelineError(stage, detail=PRIVATE)):
                output = execute_request(request())
                self.assertEqual(json.loads(output), failed(stage))
                for sentinel in (PRIVATE, DOCUMENT, SOLAR_KEY, NVIDIA_KEY):
                    self.assertNotIn(sentinel.encode(), output)

    def test_call_budget_and_provider_priority_are_preserved(self):
        cases = ((CandidatePipelineError('CLASSIFICATION_FAILED', 'PROVIDER_TIMEOUT'), 'PROVIDER_TIMEOUT'),
                 (CandidatePipelineError('CLASSIFICATION_FAILED', 'PROVIDER_TIMEOUT', 'CALL_BUDGET_EXCEEDED'), 'CALL_LIMIT'),
                 (CandidatePipelineError('CLASSIFICATION_FAILED', PRIVATE, PRIVATE), 'CLASSIFICATION_FAILED'),
                 (CandidatePipelineError('CLASSIFICATION_FAILED', None, PRIVATE), 'CLASSIFICATION_FAILED'))
        for error, code in cases:
            with self.subTest(code=code, provider=error.provider_code), pipeline_failure(error):
                self.assertEqual(json.loads(execute_request(request())), failed(code))

    def test_unknown_and_nonstring_stage_or_provider_never_escape(self):
        for stage in (PRIVATE, None, [], {}, 7, True):
            for provider in (PRIVATE, None, [], {}):
                with self.subTest(stage=stage, provider=provider), pipeline_failure(
                        CandidatePipelineError(stage, provider, PRIVATE)):
                    self.assertEqual(json.loads(execute_request(request())), failed('ANALYSIS_FAILURE'))

    def test_evaluation_failure_preserves_gold_denominator_and_release_flags(self):
        for stage in STAGES:
            with self.subTest(stage=stage), pipeline_failure(CandidatePipelineError(stage, detail=PRIVATE)):
                score = evaluate(packet_fixture())
            self.assertEqual((score['status'], score['error']), ('failed', stage))
            self.assertEqual(sum(field['missing'] for field in score['fields'].values()), 2)
            self.assertEqual(score['items'], [])
            self.assertFalse(score['human_reviewed'])
            self.assertFalse(score['release_gate_passed'])
            self.assertNotIn(PRIVATE, json.dumps(score))

    def test_real_child_and_parent_preserve_stage_or_safe_fallback(self):
        async def run(stage):
            return await run_analysis_process(DOCUMENT, DOCUMENT_ID, SOLAR_KEY,
                asyncio.get_running_loop().time() + 10, integrated_candidates=True,
                nvidia_key=NVIDIA_KEY, command=[sys.executable, str(FIXTURE.resolve()), stage])
        for stage in (*STAGES, PRIVATE):
            with self.subTest(stage=stage):
                self.assertEqual(asyncio.run(run(stage)), failed(stage if stage in STAGES else 'ANALYSIS_FAILURE'))

    def test_actual_http_boundary_accepts_stage_failure_without_profile_or_questions(self):
        def analyze(document, document_id):
            return execute_integrated_analysis(document, document_id, SOLAR_KEY, NVIDIA_KEY)
        with TestClient(create_app(internal_token='synthetic-internal',
                                  analysis_mode='integrated-candidates', analyze=analyze)) as client:
            for stage in STAGES:
                with self.subTest(stage=stage), pipeline_failure(CandidatePipelineError(stage, detail=PRIVATE)):
                    response = client.post('/internal/v1/analyze', content=DOCUMENT.encode(), headers=HEADERS)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), dict(failed(stage), requestId='REQ'))


if __name__ == '__main__':
    unittest.main()
