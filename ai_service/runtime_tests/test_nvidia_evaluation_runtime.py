"""NVIDIA evaluator against the actual service child, SDK, and loopback HTTP."""
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


class NvidiaEvaluationRuntimeTests(unittest.TestCase):
    def run_provider(self, provider, *, timeout=30):
        with provider_server(provider) as endpoint, patch.dict(os.environ, {
                'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
            return asyncio.run(run_scored_process(DOCUMENT, 'PUBLIC-01', gold_fixture(), NVIDIA_KEY,
                timeout_seconds=timeout, command=[sys.executable, str(SHIM), endpoint, 'nvidia-only']))

    def test_real_nvidia_child_scores_all_ten_fields_without_private_text(self):
        provider = Provider()
        result = self.run_provider(provider)
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(result['questions'], 10)
        self.assertEqual(sum(f['matched'] for f in result['fields'].values()), 10)
        self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 0)
        self.assertEqual(provider.kinds, ['nvidia']*6)
        self.assertEqual(provider.errors, [])
        self.assertFalse(result['release_gate_passed'])
        for value in (DOCUMENT, NVIDIA_KEY, SOLAR_KEY, 'TestApp', 'React'):
            self.assertNotIn(value, json.dumps(result))

    def test_malformed_and_rate_limited_responses_keep_gold_after_single_call(self):
        class Malformed(Provider):
            def reply(self, payload):
                super().reply(payload)
                return {'private_response': 'private-marker'}
        for provider, expected in ((Malformed(), 'INVALID_RESPONSE'), (Provider(failure_status=429), 'PROVIDER_RATE_LIMIT')):
            with self.subTest(error=expected):
                result = self.run_provider(provider)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['error'], expected)
                self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 10)
                self.assertEqual(provider.kinds, ['nvidia'])
                self.assertEqual(provider.errors, [])
                self.assertNotIn('private-marker', json.dumps(result))

    def test_timeout_and_cancellation_reap_child_after_actual_provider_entry(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                provider = Provider(hold='nvidia')
                children = []
                original = asyncio.create_subprocess_exec
                async def create(*args, **kwargs):
                    self.assertNotIn(NVIDIA_KEY, repr(args))
                    self.assertNotIn(NVIDIA_KEY, repr(kwargs['env']))
                    child = await original(*args, **kwargs)
                    children.append(child)
                    return child
                async def execute(endpoint):
                    task = asyncio.create_task(run_scored_process(DOCUMENT, 'PUBLIC-01', gold_fixture(), NVIDIA_KEY,
                        timeout_seconds=30 if cancel else 10,
                        command=[sys.executable, str(SHIM), endpoint, 'nvidia-only']))
                    self.assertTrue(await asyncio.to_thread(provider.started.wait, 8))
                    if cancel:
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError): await task
                    else:
                        result = await task
                        self.assertEqual(result['error'], 'ANALYSIS_DEADLINE')
                        self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 10)
                    self.assertEqual(len(children), 1)
                    self.assertIsNotNone(children[0].returncode)
                    self.assertTrue(await asyncio.to_thread(provider.closed.wait, 3))
                    self.assertEqual(provider.kinds, ['nvidia'])
                    self.assertEqual(provider.errors, [])
                with provider_server(provider) as endpoint, patch.dict(os.environ, {
                        'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
                    with patch.object(asyncio, 'create_subprocess_exec', side_effect=create):
                        asyncio.run(execute(endpoint))
