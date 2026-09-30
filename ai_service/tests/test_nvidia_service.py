"""Single-key service mode and disposable-worker contract; no live model calls."""

import asyncio
from copy import deepcopy
import json
import os
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agentfit_ai.analysis_process import AnalysisProcessError, run_analysis_process
from agentfit_ai.analysis_worker import execute_request
from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.http_service import create_app
from agentfit_ai.nvidia_streaming import post_nvidia_streaming_inline
from test_candidate_confirmation import DOCUMENT, DOCUMENT_ID, result
from test_integrated_confirmation_http import HEADERS, draft


KEY = 'synthetic-nvidia-secret'


def request(**changes):
    return json.dumps(dict(document=DOCUMENT, documentId=DOCUMENT_ID, key=KEY,
                           mode='integrated-nvidia', **changes)).encode()


class NvidiaWorkerTests(unittest.TestCase):
    def test_single_key_worker_selects_inline_nvidia_and_v2_projection(self):
        with (patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()),
              patch('agentfit_ai.candidate_service_worker.analyze_nvidia_candidates',
                    return_value=result(), create=True) as selected,
              patch('agentfit_ai.analysis_worker.SolarAnalyzer', side_effect=AssertionError('Solar forbidden'))):
            output = json.loads(execute_request(request()))
        self.assertEqual(output.get('contract'), 'confirmation-v2')
        self.assertEqual(output['outcome'], 'needs_confirmation')
        self.assertEqual(output['profile'], result()['profile'])
        selected.assert_called_once_with(DOCUMENT, DOCUMENT_ID, KEY,
                                         nvidia_transport=post_nvidia_streaming_inline)
        self.assertNotIn(KEY, json.dumps(output))

    def test_sdk_and_sensitive_input_fail_before_pipeline(self):
        for missing, document, expected in ((True, DOCUMENT, 'INTEGRATED_RUNTIME_UNAVAILABLE'),
                                            (False, DOCUMENT + KEY, 'SENSITIVE_CONTENT')):
            wire = json.loads(request())
            wire['document'] = document
            with (self.subTest(expected=expected),
                  patch('agentfit_ai.candidate_service_worker.find_spec', return_value=None if missing else object()),
                  patch('agentfit_ai.candidate_service_worker.analyze_nvidia_candidates', create=True) as selected):
                output = json.loads(execute_request(json.dumps(wire).encode()))
                self.assertEqual(output, {'error': expected})
                selected.assert_not_called()

    def test_pipeline_errors_keep_safe_stage_and_call_budget_priority(self):
        for error, code in (
                (CandidatePipelineError('CLASSIFICATION_FAILED'), 'CLASSIFICATION_FAILED'),
                (CandidatePipelineError('EXTRACTION_FAILED', 'PROVIDER_RATE_LIMIT'), 'PROVIDER_RATE_LIMIT'),
                (CandidatePipelineError('EXTRACTION_FAILED', 'PROVIDER_TIMEOUT', 'CALL_BUDGET_EXCEEDED'), 'CALL_LIMIT'),
                (CandidatePipelineError('private', 'private', 'private'), 'ANALYSIS_FAILURE')):
            with (self.subTest(code=code),
                  patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()),
                  patch('agentfit_ai.candidate_service_worker.analyze_nvidia_candidates',
                        side_effect=error, create=True)):
                self.assertEqual(json.loads(execute_request(request())),
                                 {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': code})

    def test_wire_rejects_second_key_missing_key_and_oversize(self):
        wire = json.loads(request())
        variants = [dict(wire, nvidiaKey=KEY), dict(wire, key=''), dict(wire, key=None),
                    dict(wire, mode='integrated-candidates'), dict(wire, document='x' * 500_001)]
        with patch('agentfit_ai.candidate_service_worker.analyze_nvidia_candidates', create=True) as selected:
            for value in variants:
                with self.subTest(fields=list(value)):
                    self.assertEqual(json.loads(execute_request(json.dumps(value).encode())),
                                     {'error': 'ANALYSIS_WORKER_FAILED'})
            selected.assert_not_called()


class NvidiaProcessTests(unittest.TestCase):
    def call(self, output, **options):
        command = [sys.executable, '-c', 'import json,sys; json.load(sys.stdin); print(' + repr(json.dumps(output)) + ')']
        async def run():
            return await run_analysis_process(DOCUMENT, DOCUMENT_ID, KEY,
                asyncio.get_running_loop().time() + 10, command=command,
                **dict({'nvidia_only': True}, **options))
        return asyncio.run(run())

    def test_single_key_wire_and_clean_environment_in_real_child(self):
        output = {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_RATE_LIMIT'}
        command = [sys.executable, '-c', (
            "import sys,os,json; r=json.load(sys.stdin); "
            "assert set(r)=={'document','documentId','key','mode'}; "
            "assert r['key']=='synthetic-nvidia-secret' and r['mode']=='integrated-nvidia'; "
            "assert all(os.getenv(k) is None for k in ('UPSTAGE_API_KEY','NVIDIA_API_KEY')); "
            "assert r['key'] not in str(sys.argv); "
            'print(' + repr(json.dumps(output)) + ')')]
        async def run():
            return await run_analysis_process(DOCUMENT, DOCUMENT_ID, KEY,
                asyncio.get_running_loop().time() + 10, nvidia_only=True, command=command)
        with patch.dict(os.environ, {'UPSTAGE_API_KEY': 'forbidden-solar', 'NVIDIA_API_KEY': KEY}):
            self.assertEqual(asyncio.run(run()), output)

    def test_v2_projection_is_validated_again_at_process_boundary(self):
        self.assertEqual(self.call(draft()), draft())
        broken = deepcopy(draft())
        broken['profile']['evidence']['frontend'][0]['documentId'] = 'other'
        for invalid in (broken, {'outcome': 'complete', 'profile': {}},
                        {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'private'}):
            with self.subTest(output=invalid['outcome']), self.assertRaises(AnalysisProcessError):
                self.call(invalid)

    def test_conflicting_flags_and_second_key_are_rejected_before_spawn(self):
        for options in ({'nvidia_only': 1}, {'recoverable_solar': True},
                        {'integrated_candidates': True, 'nvidia_key': KEY}, {'nvidia_key': KEY}):
            with (self.subTest(options=options),
                  patch('agentfit_ai.analysis_process.asyncio.create_subprocess_exec',
                        side_effect=AssertionError('must not spawn')),
                  self.assertRaises(AnalysisProcessError)):
                self.call(draft(), **options)


class NvidiaHttpTests(unittest.TestCase):
    def client(self, **options):
        return TestClient(create_app(internal_token='synthetic-internal',
                                     analysis_mode='integrated-nvidia', **options))

    def test_only_nvidia_key_and_whole_request_deadline_reach_worker(self):
        seen = []
        async def worker(text, document_id, key, deadline, **options):
            seen.append((text, document_id, key, deadline - asyncio.get_running_loop().time(), options))
            return draft()
        with (patch.dict(os.environ, {'NVIDIA_API_KEY': KEY}, clear=True),
              patch('agentfit_ai.http_service.run_analysis_process', side_effect=worker)):
            response = self.client().post('/internal/v1/analyze', headers=HEADERS, content=DOCUMENT.encode())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), dict(draft(), requestId='REQ'))
        self.assertEqual(seen[0][:3], (DOCUMENT, DOCUMENT_ID, KEY))
        self.assertTrue(1790 < seen[0][3] <= 1800)
        self.assertEqual(seen[0][4], {'nvidia_only': True})

    def test_missing_nvidia_never_uses_available_solar_key(self):
        with (patch.dict(os.environ, {'UPSTAGE_API_KEY': 'forbidden-solar'}, clear=True),
              patch('agentfit_ai.http_service.run_analysis_process') as worker):
            response = self.client().post('/internal/v1/analyze', headers=HEADERS, content=DOCUMENT.encode())
        self.assertEqual((response.status_code, response.json()), (503, {'error': 'MISSING_OR_INVALID_KEY'}))
        worker.assert_not_called()

    def test_v2_required_and_invalid_results_are_rejected(self):
        client = self.client(analyze=lambda *_: draft())
        for header in (None, 'confirmation-v1'):
            headers = dict(HEADERS)
            if header is None:
                headers.pop('X-AgentFit-Analysis-Contract')
            else:
                headers['X-AgentFit-Analysis-Contract'] = header
            self.assertEqual(client.post('/internal/v1/analyze', headers=headers, content=b'x').status_code, 428)
        response = self.client(analyze=lambda *_: {'outcome': 'complete', 'profile': {}}).post(
            '/internal/v1/analyze', headers=HEADERS, content=DOCUMENT.encode())
        self.assertEqual((response.status_code, response.json()), (502, {'error': 'INVALID_ANALYSIS_RESULT'}))

    def test_timeout_configuration_and_safe_failure_response(self):
        for value in (True, 0, 3601):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.client(request_timeout_seconds=value)
        failed = {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_RATE_LIMIT'}
        response = self.client(analyze=lambda *_: failed, request_timeout_seconds=3600).post(
            '/internal/v1/analyze', headers=HEADERS, content=DOCUMENT.encode())
        self.assertEqual((response.status_code, response.json()), (200, dict(failed, requestId='REQ')))


if __name__ == '__main__':
    unittest.main()
