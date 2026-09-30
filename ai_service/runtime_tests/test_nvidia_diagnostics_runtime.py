"""Real SDK/worker diagnostic mode; synthetic loopback endpoints only."""
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
    def reply(self, payload):
        body = super().reply(payload)
        if payload['response_format']['json_schema']['name'] == 'agentfit_candidate_labels':
            self.failure_status = 503
        return body


class Malformed(Provider):
    def reply(self, payload):
        super().reply(payload)
        return {'private_response': 'private-marker'}


class NvidiaDiagnosticsRuntimeTests(unittest.TestCase):
    def run_provider(self, provider, enabled=True):
        report = {} if enabled else None
        with provider_server(provider) as endpoint, patch.dict(os.environ, {
                'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
            result = asyncio.run(run_scored_process(DOCUMENT, 'PUBLIC-01', gold_fixture(), NVIDIA_KEY,
                timeout_seconds=30, command=[sys.executable, str(SHIM), endpoint, 'nvidia-only'],
                call_diagnostics=report))
        self.assertEqual(provider.errors, [])
        for private in (DOCUMENT, NVIDIA_KEY, SOLAR_KEY, 'private-marker', 'TestApp', 'React'):
            self.assertNotIn(json.dumps(private)[1:-1], json.dumps([result, report]))
        return result, report

    def test_real_diagnostic_mode_preserves_score_and_five_calls(self):
        plain_provider, diagnostic_provider = Provider(), Provider()
        plain, _ = self.run_provider(plain_provider, False)
        measured, report = self.run_provider(diagnostic_provider)
        self.assertEqual(plain, measured)
        self.assertEqual(measured['status'], 'valid')
        self.assertEqual(plain_provider.names, diagnostic_provider.names)
        self.assertEqual(diagnostic_provider.kinds, ['nvidia'] * 5)
        self.assertEqual(report['status'], 'available')
        self.assertIsNone(report['failureStage'])
        self.assertEqual([r['call_index'] for r in report['calls']], [1, 2, 3, 4, 5])
        self.assertEqual([r['requested_model'] for r in report['calls']], [DEEPSEEK] * 3 + [GLM] * 2)
        self.assertEqual([r['stage'] for r in report['calls']], ['EXTRACTION_FAILED',
            'OPERATION_EXTRACTION_FAILED', 'CLASSIFICATION_FAILED', 'COVERAGE_REVIEW_FAILED', 'COVERAGE_REVIEW_FAILED'])
        self.assertTrue(all(r['transport_completed'] and r['provider_error'] is None for r in report['calls']))

    def test_review_503_reports_requested_glm_and_stops_at_fourth_call(self):
        provider = ReviewFailure()
        score, report = self.run_provider(provider)
        self.assertEqual(score['error'], 'PROVIDER_UNAVAILABLE')
        self.assertEqual(report['failureStage'], 'COVERAGE_REVIEW_FAILED')
        self.assertEqual(len(provider.kinds), 4)
        self.assertEqual(len(report['calls']), 4)
        last = report['calls'][-1]
        self.assertEqual((last['requested_model'], last['provider_error'], last['attempt']),
                         (GLM, 'PROVIDER_UNAVAILABLE', 1))
        self.assertFalse(last['transport_completed'])
        self.assertIsNone(last['response_bytes'])

    def test_initial_rate_limit_and_semantic_failure_have_distinct_transport_evidence(self):
        for provider, expected, completed in ((Provider(failure_status=429), 'PROVIDER_RATE_LIMIT', False),
                                             (Malformed(), 'INVALID_RESPONSE', True)):
            with self.subTest(error=expected):
                score, report = self.run_provider(provider)
                self.assertEqual(score['error'], expected)
                self.assertEqual(report['failureStage'], 'EXTRACTION_FAILED')
                self.assertEqual(len(provider.kinds), 1)
                self.assertEqual(len(report['calls']), 1)
                row = report['calls'][0]
                self.assertEqual(row['requested_model'], DEEPSEEK)
                self.assertEqual(row['transport_completed'], completed)
                self.assertEqual(row['provider_error'], None if completed else expected)

    def test_timeout_and_cancel_leave_unknown_trace_and_reap_actual_child(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                provider, children, report = Provider(hold='nvidia'), [], {}
                original = asyncio.create_subprocess_exec
                async def create(*args, **kwargs):
                    self.assertNotIn(NVIDIA_KEY, repr(args) + repr(kwargs['env']))
                    child = await original(*args, **kwargs)
                    children.append(child)
                    return child
                async def execute(endpoint):
                    task = asyncio.create_task(run_scored_process(DOCUMENT, 'PUBLIC-01', gold_fixture(), NVIDIA_KEY,
                        timeout_seconds=30 if cancel else 10, call_diagnostics=report,
                        command=[sys.executable, str(SHIM), endpoint, 'nvidia-only']))
                    self.assertTrue(await asyncio.to_thread(provider.started.wait, 8))
                    if cancel:
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    else:
                        result = await task
                        self.assertEqual(result['error'], 'ANALYSIS_DEADLINE')
                        self.assertEqual(report['unavailableReason'], 'ANALYSIS_DEADLINE_EXCEEDED')
                    self.assertEqual(report['status'], 'unavailable')
                    self.assertEqual(report['calls'], [])
                    self.assertEqual(len(children), 1)
                    self.assertIsNotNone(children[0].returncode)
                    self.assertTrue(await asyncio.to_thread(provider.closed.wait, 3))
                    self.assertEqual(provider.kinds, ['nvidia'])  # A call DID start, despite no returned trace.
                    self.assertEqual(provider.errors, [])
                with provider_server(provider) as endpoint, patch.dict(os.environ, {
                        'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}), patch.object(
                        asyncio, 'create_subprocess_exec', side_effect=create):
                    asyncio.run(execute(endpoint))


if __name__ == '__main__':
    unittest.main()
