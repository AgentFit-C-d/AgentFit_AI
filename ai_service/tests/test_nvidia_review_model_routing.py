"""Explicit diagnostic reviewer selection must survive every process boundary."""
import asyncio
import json
import sys
import unittest
from unittest.mock import patch

from agentfit_ai.analysis_call_metadata import METADATA_VERSION, build_metadata, unavailable_metadata
from agentfit_ai.analysis_process import AnalysisProcessError, run_analysis_process
from agentfit_ai.analysis_worker import FAILED, execute_request
from agentfit_ai.candidate_first_profile import CandidatePipelineError
from tests.test_analysis_call_metadata import call

DEEPSEEK = 'deepseek-ai/deepseek-v4.1-flash'
GLM = 'z-ai/glm-5.3'
FAILURE = {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_UNAVAILABLE'}


def envelope(model):
    row = dict(call(), stage='COVERAGE_REVIEW_FAILED', requested_model=model)
    return {'version': METADATA_VERSION, 'result': FAILURE,
            'diagnostics': build_metadata([row], 'COVERAGE_REVIEW_FAILED')}


class ParentReviewRoutingTests(unittest.IsolatedAsyncioTestCase):
    def command(self, body, expected_model):
        expected = {'document', 'documentId', 'key', 'mode', 'diagnostics'}
        if expected_model is not None:
            expected.add('reviewModel')
        script = ('import json,sys; r=json.load(sys.stdin); '
                  f'assert set(r)=={expected!r}; '
                  f'assert r.get("reviewModel")=={expected_model!r}; '
                  'print('+repr(json.dumps(body))+')')
        return [sys.executable, '-c', script]

    async def test_selected_model_crosses_stdin_and_default_packet_stays_unchanged(self):
        for selected in (None, DEEPSEEK, GLM):
            report = {}
            options = {} if selected is None else {'nvidia_review_model': selected}
            body = envelope(GLM if selected is None else selected)
            with self.subTest(model=selected):
                result = await run_analysis_process('source', 'DOC', 'key',
                    asyncio.get_running_loop().time()+5, nvidia_only=True, call_diagnostics=report,
                    command=self.command(body, selected), **options)
                self.assertEqual(result, FAILURE)
                self.assertEqual(report['calls'][0]['requested_model'], GLM if selected is None else selected)

    async def test_invalid_selection_never_spawns_or_changes_collector(self):
        options = [{'nvidia_only': True, 'call_diagnostics': {}, 'nvidia_review_model': model}
                   for model in ('', 'private-model', True, [], 'moonshotai/kimi-k3')]
        options += [{'nvidia_only': True, 'nvidia_review_model': DEEPSEEK},
                    {'call_diagnostics': {}, 'nvidia_review_model': DEEPSEEK},
                    {'recoverable_solar': True, 'call_diagnostics': {}, 'nvidia_review_model': DEEPSEEK}]
        for value in options:
            with self.subTest(options=value), patch('asyncio.create_subprocess_exec',
                    side_effect=AssertionError('spawned invalid request')):
                with self.assertRaisesRegex(AnalysisProcessError, '^ANALYSIS_WORKER_FAILED$'):
                    await run_analysis_process('source', 'DOC', 'key',
                        asyncio.get_running_loop().time()+5, **value)
                if 'call_diagnostics' in value:
                    self.assertEqual(value['call_diagnostics'], {})

    async def test_selected_model_rejects_mismatched_review_or_other_stage_trace(self):
        wrong_review = envelope(GLM)
        wrong_extraction = envelope(DEEPSEEK)
        wrong_extraction['diagnostics'] = build_metadata([
            dict(call(), requested_model=GLM)], 'EXTRACTION_FAILED')
        for body in (wrong_review, wrong_extraction):
            report = {}
            with self.assertRaisesRegex(AnalysisProcessError, '^ANALYSIS_WORKER_FAILED$'):
                await run_analysis_process('source', 'DOC', 'key', asyncio.get_running_loop().time()+5,
                    nvidia_only=True, nvidia_review_model=DEEPSEEK, call_diagnostics=report,
                    command=self.command(body, DEEPSEEK))
            self.assertEqual(report, unavailable_metadata('ANALYSIS_WORKER_FAILED'))


class WorkerReviewRoutingTests(unittest.TestCase):
    def request(self, **changes):
        return {'document': 'source', 'documentId': 'DOC', 'key': 'key',
                'mode': 'integrated-nvidia', 'diagnostics': METADATA_VERSION, **changes}

    def test_worker_routes_both_allowed_models_and_preserves_default(self):
        # Only the external pipeline is replaced; packet validation, forwarding,
        # failure projection and diagnostic serialization stay real.
        def failed_pipeline(*args, **options):
            model = options.get('review_model', GLM)
            options['call_trace'].append(dict(call(), stage='COVERAGE_REVIEW_FAILED', requested_model=model))
            raise CandidatePipelineError('COVERAGE_REVIEW_FAILED', 'PROVIDER_UNAVAILABLE')
        with patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()), patch(
                'agentfit_ai.candidate_service_worker.analyze_nvidia_candidates', side_effect=failed_pipeline):
            for selected in (None, DEEPSEEK, GLM):
                options = {} if selected is None else {'reviewModel': selected}
                result = json.loads(execute_request(json.dumps(self.request(**options)).encode()))
                self.assertEqual(result.get('result'), FAILURE)
                self.assertEqual(result['diagnostics']['calls'][0]['requested_model'],
                                 GLM if selected is None else selected)

    def test_worker_rejects_invalid_model_mode_or_missing_diagnostics_before_pipeline(self):
        cases = [self.request(reviewModel=model) for model in ('private-model', '', True, [], 'moonshotai/kimi-k3')]
        missing = self.request(reviewModel=DEEPSEEK)
        missing.pop('diagnostics')
        cases += [missing, self.request(mode='recoverable-solar', reviewModel=DEEPSEEK),
                  self.request(mode='integrated-candidates', nvidiaKey='key2', reviewModel=DEEPSEEK)]
        with patch('agentfit_ai.candidate_service_worker.execute_nvidia_analysis',
                   side_effect=AssertionError('invalid selection entered analyzer')):
            for request in cases:
                self.assertEqual(execute_request(json.dumps(request).encode()), FAILED)


if __name__ == '__main__':
    unittest.main()
