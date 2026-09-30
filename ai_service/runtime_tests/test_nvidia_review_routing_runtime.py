"""Selected reviewer uses real SDK/child/SSE without reaching external APIs."""
import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch

from agentfit_ai.nvidia_evaluation_runner import run_scored_process
from test_independent_evaluation_runtime import gold_fixture
from test_integrated_runtime import DOCUMENT, NVIDIA_KEY, SOLAR_KEY
from test_integrated_service import Provider, SHIM, provider_server

DEEPSEEK = 'deepseek-ai/deepseek-v4.1-flash'
GLM = 'z-ai/glm-5.3'


class ReviewFailure(Provider):
    def __init__(self, status):
        super().__init__()
        self.next_status = status

    def reply(self, payload):
        body = super().reply(payload)
        if payload['response_format']['json_schema']['name'] == 'agentfit_candidate_labels':
            self.failure_status = self.next_status
        return body


class WrongReviewModel(Provider):
    def reply(self, payload):
        body = super().reply(payload)
        if payload['response_format']['json_schema']['name'] == 'agentfit_candidate_label_review':
            payload['model'] = GLM
        return body


class NvidiaReviewRoutingRuntimeTests(unittest.TestCase):
    def run_provider(self, provider, selected=DEEPSEEK):
        report = {}
        options = {} if selected is None else {'review_model': selected}
        with provider_server(provider) as endpoint, patch.dict(os.environ, {
                'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
            score = asyncio.run(run_scored_process(DOCUMENT, 'PUBLIC-01', gold_fixture(), NVIDIA_KEY,
                timeout_seconds=30, call_diagnostics=report,
                command=[sys.executable, str(SHIM), endpoint, 'nvidia-only'], **options))
        self.assertEqual(provider.errors, [])
        for private in (DOCUMENT, NVIDIA_KEY, SOLAR_KEY, 'synthetic-private-provider-error', 'TestApp', 'React'):
            self.assertNotIn(json.dumps(private)[1:-1], json.dumps([score, report]))
        return score, report

    def test_real_sdk_changes_only_two_review_calls_and_preserves_score(self):
        baseline, selected = Provider(), Provider()
        original, original_trace = self.run_provider(baseline, None)
        result, trace = self.run_provider(selected)
        self.assertEqual(result, original)
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(selected.names, baseline.names)
        self.assertEqual(selected.kinds, ['nvidia'] * 5)
        self.assertEqual([r['requested_model'] for r in original_trace['calls']], [DEEPSEEK]*3+[GLM]*2)
        self.assertEqual([r['requested_model'] for r in trace['calls']], [DEEPSEEK]*5)
        self.assertEqual([r['stage'] for r in trace['calls']], ['EXTRACTION_FAILED',
            'OPERATION_EXTRACTION_FAILED', 'CLASSIFICATION_FAILED', 'COVERAGE_REVIEW_FAILED', 'COVERAGE_REVIEW_FAILED'])
        self.assertTrue(all(r['transport_completed'] and r['attempt'] == 1 for r in trace['calls']))

    def test_selected_review_503_and_429_stop_after_one_failed_attempt(self):
        for status, error in ((503, 'PROVIDER_UNAVAILABLE'), (429, 'PROVIDER_RATE_LIMIT')):
            with self.subTest(status=status):
                provider = ReviewFailure(status)
                score, report = self.run_provider(provider)
                self.assertEqual(score['error'], error)
                self.assertEqual(report['failureStage'], 'COVERAGE_REVIEW_FAILED')
                self.assertEqual(len(provider.kinds), 4)
                self.assertEqual(len(report['calls']), 4)
                last = report['calls'][-1]
                self.assertEqual((last['requested_model'], last['provider_error'], last['attempt']),
                                 (DEEPSEEK, error, 1))
                self.assertFalse(last['transport_completed'])

    def test_different_returned_review_model_is_not_accepted(self):
        provider = WrongReviewModel()
        score, report = self.run_provider(provider)
        self.assertEqual(score['error'], 'PROVIDER_MODEL')
        self.assertEqual(report['failureStage'], 'COVERAGE_REVIEW_FAILED')
        self.assertEqual(len(provider.kinds), 4)
        self.assertEqual(report['calls'][-1]['requested_model'], DEEPSEEK)

    def test_selected_request_timeout_and_cancellation_reap_child_and_socket(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                provider, children, report = Provider(hold='nvidia'), [], {}
                spawn = asyncio.create_subprocess_exec
                async def capture(*args, **kwargs):
                    self.assertNotIn(NVIDIA_KEY, repr(args)+repr(kwargs['env']))
                    child = await spawn(*args, **kwargs)
                    children.append(child)
                    return child
                async def execute(endpoint):
                    task = asyncio.create_task(run_scored_process(DOCUMENT, 'PUBLIC-01', gold_fixture(), NVIDIA_KEY,
                        timeout_seconds=30 if cancel else 10, call_diagnostics=report, review_model=DEEPSEEK,
                        command=[sys.executable, str(SHIM), endpoint, 'nvidia-only']))
                    self.assertTrue(await asyncio.to_thread(provider.started.wait, 8))
                    if cancel:
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    else:
                        score = await task
                        self.assertEqual(score['error'], 'ANALYSIS_DEADLINE')
                    self.assertEqual(report['status'], 'unavailable')
                    self.assertEqual(report['calls'], [])
                    self.assertEqual(len(children), 1)
                    self.assertIsNotNone(children[0].returncode)
                    self.assertTrue(await asyncio.to_thread(provider.closed.wait, 3))
                    self.assertEqual(provider.kinds, ['nvidia'])
                    self.assertEqual(provider.errors, [])
                with provider_server(provider) as endpoint, patch.dict(os.environ, {
                        'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}), patch.object(
                        asyncio, 'create_subprocess_exec', side_effect=capture):
                    asyncio.run(execute(endpoint))


if __name__ == '__main__':
    unittest.main()
