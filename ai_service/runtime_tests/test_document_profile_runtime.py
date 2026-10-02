"""Fresh SDK extraction through current worker; fixed local provider replies only."""
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

from agentfit_ai.analysis_process import run_analysis_process
from test_integrated_service import Provider, SHIM, provider_server, service, HEADERS
from test_integrated_runtime import NVIDIA_KEY
import httpx

FIXTURE = Path(__file__).with_name('document_profile_fixture.py')


def require_worker():
    try:
        return importlib.import_module('diagnostic_tools.document_profile_worker')
    except ModuleNotFoundError as error:
        if error.name != 'diagnostic_tools.document_profile_worker':
            raise
        raise AssertionError('document profile observation worker is missing') from None


class CaptureProvider(Provider):
    def __init__(self, **options):
        super().__init__(**options)
        self.payloads = []

    def reply(self, payload):
        self.payloads.append(deepcopy(payload))
        return super().reply(payload)


class DocumentProfileRuntimeTests(unittest.TestCase):
    def observed(self, provider, path):
        with provider_server(provider) as endpoint, patch.dict(os.environ, {
                'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
            async def run():
                return await run_analysis_process(provider.document, 'PUBLIC-01', NVIDIA_KEY,
                    asyncio.get_running_loop().time() + 40, nvidia_only=True,
                    command=[sys.executable, str(FIXTURE), endpoint, str(path)])
            result = asyncio.run(run())
        self.assertEqual(provider.errors, [])
        return result, json.loads(path.read_text(encoding='utf-8'))

    def test_actual_api_and_observed_child_keep_identical_requests_and_results(self):
        require_worker()
        baseline, observed = CaptureProvider(), CaptureProvider()
        with service(baseline, analysis_mode='integrated-nvidia') as (_, url, processes):
            with httpx.Client(trust_env=False, timeout=40) as client:
                response = client.post(url + '/internal/v1/analyze',
                    headers={**HEADERS, 'X-Document-Id': 'PUBLIC-01', 'X-Document-Kind': 'MARKDOWN',
                             'Content-Type': 'text/markdown'}, content=baseline.document.encode())
            self.assertEqual(response.status_code, 200)
            expected = response.json()
            expected.pop('requestId')
        with tempfile.TemporaryDirectory() as folder:
            result, trace = self.observed(observed, Path(folder) / 'trace.json')
        self.assertEqual(result, expected)
        self.assertEqual(observed.payloads, baseline.payloads)
        self.assertEqual(trace['status'], 'complete')
        self.assertEqual(trace['stages']['final_response'], expected)
        self.assertEqual(trace['provenance']['status'], 'complete')
        self.assertEqual(len(trace['stages']['general_extracted']), 10)
        self.assertEqual(len(trace['stages']['semantic_assessed']['modelDecisions']), 10)
        self.assertEqual(len(trace['calls']), 6)
        self.assertEqual([r['request']['model'] for r in trace['calls']],
                         ['deepseek-ai/deepseek-v4.1-flash'] * 4 + ['z-ai/glm-5.3'] * 2)
        self.assertNotIn(NVIDIA_KEY, json.dumps(trace))

    def test_existing_curation_is_fully_recorded_without_adding_model_steps(self):
        require_worker()
        provider = CaptureProvider(many_features=True)
        with tempfile.TemporaryDirectory() as folder:
            result, trace = self.observed(provider, Path(folder) / 'trace.json')
        self.assertEqual(trace['status'], 'complete')
        curation = trace['stages']['feature_curated']['curation']
        self.assertEqual(len(curation['groups'][0]['memberIds']), 31)
        self.assertEqual(len(result['profile']['data']['features']), 1)
        self.assertIn('agentfit_feature_relations', provider.names)
        self.assertEqual(len(trace['calls']), len(provider.payloads))

    def test_first_provider_failure_stops_and_cannot_be_reported_as_zero_omissions(self):
        require_worker()
        provider = CaptureProvider(failure_status=503)
        with tempfile.TemporaryDirectory() as folder:
            result, trace = self.observed(provider, Path(folder) / 'trace.json')
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(trace['status'], 'partial')
        self.assertEqual(len(trace['calls']), 1)
        self.assertEqual(trace['calls'][0]['error'], 'PROVIDER_UNAVAILABLE')
        self.assertNotIn('grounded', trace['stages'])
        self.assertNotIn('synthetic-private-provider-error', json.dumps(trace))


if __name__ == '__main__':
    unittest.main()
