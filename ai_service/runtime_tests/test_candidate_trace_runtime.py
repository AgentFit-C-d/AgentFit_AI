"""Actual SDK/child/SSE proves observation preserves analysis and cancellation."""
import asyncio
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from agentfit_ai.analysis_process import AnalysisProcessError, run_analysis_process
from test_integrated_service import Provider, SHIM, provider_server
from test_integrated_runtime import DOCUMENT, NVIDIA_KEY, SOLAR_KEY

MODEL = 'deepseek-ai/deepseek-v4.1-flash'
PROBE = Path(__file__).with_name('candidate_trace_fixture.py')


def worker_module():
    try:
        return importlib.import_module('diagnostic_tools.candidate_trace_worker')
    except ModuleNotFoundError as error:
        if error.name != 'diagnostic_tools.candidate_trace_worker':
            raise
        raise AssertionError('candidate trace worker is not implemented') from None


class CapturingProvider(Provider):
    def __init__(self, **options):
        super().__init__(**options)
        self.payloads = []
    def reply(self, payload):
        self.payloads.append(deepcopy(payload))
        return super().reply(payload)


class StageFailure(Provider):
    def __init__(self, after, **options):
        super().__init__(**options)
        self.after = after
    def reply(self, payload):
        body = super().reply(payload)
        if payload['response_format']['json_schema']['name'] == self.after:
            self.failure_status = 503
        return body


class CandidateTraceRuntimeTests(unittest.TestCase):
    def execute(self, provider, trace_path=None):
        diagnostics = {}
        with provider_server(provider) as endpoint, patch.dict(os.environ, {
                'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
            command = ([sys.executable, str(PROBE), endpoint, str(trace_path)] if trace_path else
                       [sys.executable, str(SHIM), endpoint, 'nvidia-only'])
            async def run():
                return await run_analysis_process(provider.document, 'PUBLIC-01', NVIDIA_KEY,
                    asyncio.get_running_loop().time() + 30, nvidia_only=True,
                    nvidia_review_model=MODEL, call_diagnostics=diagnostics, command=command)
            result = asyncio.run(run())
        self.assertEqual(provider.errors, [])
        return result, diagnostics

    def read_trace(self, document, path):
        report = worker_module().validate_probe_report(document, 'PUBLIC-01', json.loads(path.read_text(encoding='utf-8')))
        for private in (document, NVIDIA_KEY, SOLAR_KEY, 'TestApp', 'React', '기록 저장', 'synthetic-private-provider-error'):
            self.assertNotIn(private, json.dumps(report, ensure_ascii=False))
        return report

    def test_real_sdk_payloads_results_and_calls_are_unchanged(self):
        worker_module()
        normal, observed = CapturingProvider(), CapturingProvider()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'trace.json'
            baseline, baseline_calls = self.execute(normal)
            actual, calls = self.execute(observed, path)
            self.assertEqual(actual, baseline)
            self.assertEqual(actual['profile']['data']['features'], ['기록 저장'])
            self.assertEqual(observed.payloads, normal.payloads)
            self.assertEqual(observed.kinds, ['nvidia'] * 5)
            self.assertEqual([row['stage'] for row in calls['calls']], [row['stage'] for row in baseline_calls['calls']])
            self.assertTrue(all(row['requested_model'] == MODEL and row['attempt'] == 1 for row in calls['calls']))
            report = self.read_trace(DOCUMENT, path)
            self.assertEqual(report['trace']['status'], 'complete')
            self.assertEqual(report['trace']['analysis']['candidateCount'], 10)
            self.assertEqual(report['trace']['stages']['projected']['fields']['features']['valueCount'], 1)

    def test_review_failure_keeps_classified_observation_without_retry(self):
        worker_module()
        provider = StageFailure('agentfit_candidate_labels')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'trace.json'
            result, calls = self.execute(provider, path)
            self.assertEqual(result['error'], 'PROVIDER_UNAVAILABLE')
            self.assertEqual(calls['failureStage'], 'COVERAGE_REVIEW_FAILED')
            self.assertEqual(provider.kinds, ['nvidia'] * 4)
            trace = self.read_trace(DOCUMENT, path)['trace']
            self.assertEqual(trace['status'], 'partial')
            self.assertIsNotNone(trace['stages']['classified'])
            self.assertIsNone(trace['stages']['reviewed'])

    def test_curation_failure_does_not_invent_reviewed_observation(self):
        worker_module()
        provider = StageFailure('agentfit_candidate_source_coverage', many_features=True)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'trace.json'
            result, calls = self.execute(provider, path)
            self.assertEqual(result['error'], 'PROVIDER_UNAVAILABLE')
            self.assertEqual(calls['failureStage'], 'FEATURE_CURATION_FAILED')
            self.assertIn('agentfit_candidate_source_coverage', provider.names)
            trace = self.read_trace(provider.document, path)['trace']
            self.assertEqual(len(trace['stages']['grounded']['candidates']), 40)
            self.assertIsNotNone(trace['stages']['classified'])
            self.assertIsNone(trace['stages']['reviewed'])
            self.assertIsNone(trace['stages']['projected'])

    def test_timeout_and_cancel_close_child_and_leave_no_complete_sidecar(self):
        worker_module()
        for cancel in (False, True):
            with self.subTest(cancel=cancel), tempfile.TemporaryDirectory() as folder:
                provider, children, calls = Provider(hold='nvidia'), [], {}
                path = Path(folder) / 'trace.json'
                spawn = asyncio.create_subprocess_exec
                async def capture(*args, **options):
                    for secret in (NVIDIA_KEY, SOLAR_KEY, DOCUMENT):
                        self.assertNotIn(secret, repr(args) + repr(options['env']))
                    child = await spawn(*args, **options)
                    children.append(child)
                    return child
                async def run(endpoint):
                    task = asyncio.create_task(run_analysis_process(DOCUMENT, 'PUBLIC-01', NVIDIA_KEY,
                        asyncio.get_running_loop().time() + (30 if cancel else 10), nvidia_only=True,
                        nvidia_review_model=MODEL, call_diagnostics=calls,
                        command=[sys.executable, str(PROBE), endpoint, str(path)]))
                    self.assertTrue(await asyncio.to_thread(provider.started.wait, 8))
                    if cancel:
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    else:
                        with self.assertRaisesRegex(AnalysisProcessError, 'ANALYSIS_DEADLINE_EXCEEDED'):
                            await task
                    self.assertEqual(len(children), 1)
                    self.assertIsNotNone(children[0].returncode)
                    self.assertTrue(await asyncio.to_thread(provider.closed.wait, 3))
                    self.assertEqual(path.read_bytes(), b'')
                    self.assertEqual(calls['status'], 'unavailable')
                    self.assertEqual(provider.kinds, ['nvidia'])
                with provider_server(provider) as endpoint, patch.dict(os.environ, {
                        'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1',
                        'NVIDIA_API_KEY': NVIDIA_KEY, 'UPSTAGE_API_KEY': SOLAR_KEY}), patch.object(
                        asyncio, 'create_subprocess_exec', side_effect=capture):
                    asyncio.run(run(endpoint))
                self.assertEqual(provider.errors, [])


if __name__ == '__main__':
    unittest.main()
