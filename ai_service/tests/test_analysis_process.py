import asyncio
from copy import deepcopy
import json
import os
import sys
import time
import unittest
from unittest.mock import patch


class AnalysisProcessTests(unittest.TestCase):
    def run_async(self, coroutine):
        return asyncio.run(coroutine)

    def test_worker_result_is_decoded_and_environment_is_sanitized(self):
        from agentfit_ai.analysis_process import run_analysis_process

        command = [sys.executable, "-c", (
            "import json,os,sys; json.load(sys.stdin); "
            "print(json.dumps({'outcome':'complete','profile':{'seen':os.getenv('PRIVATE_MARKER')}}))")]

        async def run():
            return await run_analysis_process("Alpha", "doc_1", "test-key",
                                              asyncio.get_running_loop().time() + 5,
                                              command=command)

        with patch.dict(os.environ, {"PRIVATE_MARKER": "must-not-leak"}):
            self.assertEqual(self.run_async(run()),
                             {"outcome": "complete", "profile": {"seen": None}})

    def test_recoverable_mode_passes_mode_and_accepts_bounded_draft(self):
        from agentfit_ai.analysis_process import run_analysis_process

        command = [sys.executable, "-c", (
            "import json,sys; request=json.load(sys.stdin); "
            "print(json.dumps({'outcome':'needs_confirmation','profile':{'data':{}},"
            "'fieldStates':{},'questions':[],'error':'PROVIDER_TIMEOUT'} "
            "if request.get('mode')=='recoverable-solar' else {'error':'BAD_MODE'}))")]

        async def run():
            return await run_analysis_process("Alpha", "doc_1", "test-key",
                                              asyncio.get_running_loop().time() + 5,
                                              recoverable_solar=True, command=command)

        self.assertEqual(self.run_async(run())["outcome"], "needs_confirmation")

    def test_process_rejects_draft_in_default_mode(self):
        from agentfit_ai.analysis_process import AnalysisProcessError, run_analysis_process

        command = [sys.executable, "-c", (
            "import json; print(json.dumps({'outcome':'needs_confirmation',"
            "'profile':{},'fieldStates':{},'questions':[],"
            "'error':'PROVIDER_TIMEOUT'}))")]

        async def run():
            return await run_analysis_process("Alpha", "doc_1", "test-key",
                                              asyncio.get_running_loop().time() + 5,
                                              command=command)

        with self.assertRaises(AnalysisProcessError) as caught:
            self.run_async(run())
        self.assertEqual(caught.exception.code, "ANALYSIS_WORKER_FAILED")

    def test_deadline_stops_a_sleeping_worker(self):
        from agentfit_ai.analysis_process import AnalysisProcessError, run_analysis_process

        command = [sys.executable, "-c", "import time; time.sleep(10)"]
        launched = []
        original = asyncio.create_subprocess_exec

        async def capture(*args, **kwargs):
            process = await original(*args, **kwargs)
            launched.append(process)
            return process

        async def run():
            return await run_analysis_process("Alpha", "doc_1", "test-key",
                                              asyncio.get_running_loop().time() + .2,
                                              command=command)

        started = time.monotonic()
        with patch("agentfit_ai.analysis_process.asyncio.create_subprocess_exec",
                   side_effect=capture):
            with self.assertRaises(AnalysisProcessError) as caught:
                self.run_async(run())
        self.assertEqual(caught.exception.code, "ANALYSIS_DEADLINE_EXCEEDED")
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(len(launched), 1)
        self.assertIsNotNone(launched[0].returncode)

    def test_oversized_worker_output_is_rejected(self):
        from agentfit_ai.analysis_process import AnalysisProcessError, run_analysis_process

        command = [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1500001)"]

        async def run():
            return await run_analysis_process("Alpha", "doc_1", "test-key",
                                              asyncio.get_running_loop().time() + 5,
                                              command=command)

        with self.assertRaises(AnalysisProcessError) as caught:
            self.run_async(run())
        self.assertEqual(caught.exception.code, "ANALYSIS_WORKER_FAILED")

    def test_cancellation_ends_worker_before_returning(self):
        from agentfit_ai.analysis_process import run_analysis_process

        command = [sys.executable, "-c", "import time; time.sleep(10)"]
        launched = []
        original = asyncio.create_subprocess_exec

        async def capture(*args, **kwargs):
            process = await original(*args, **kwargs)
            launched.append(process)
            return process

        async def run():
            task = asyncio.create_task(run_analysis_process(
                "Alpha", "doc_1", "test-key", asyncio.get_running_loop().time() + 20,
                command=command))
            await asyncio.sleep(.2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        started = time.monotonic()
        with patch("agentfit_ai.analysis_process.asyncio.create_subprocess_exec",
                   side_effect=capture):
            self.run_async(run())
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(len(launched), 1)
        self.assertIsNotNone(launched[0].returncode)

    def test_unlaunchable_worker_is_safe_error(self):
        from agentfit_ai.analysis_process import AnalysisProcessError, run_analysis_process

        async def run():
            return await run_analysis_process("Alpha", "doc_1", "test-key",
                                              asyncio.get_running_loop().time() + 5,
                                              command=["there-is-no-such-executable-agentfit"])

        with self.assertRaises(AnalysisProcessError) as caught:
            self.run_async(run())
        self.assertEqual(caught.exception.code, "ANALYSIS_WORKER_FAILED")


class IntegratedProcessTests(unittest.TestCase):
    def draft(self):
        from test_candidate_confirmation import result
        profile = result()['profile']
        states = {field: 'unknown' if value is None else 'suggested'
                  for field, value in profile['data'].items()}
        states['frontend'] = 'unresolved'
        return {'contract': 'confirmation-v2', 'outcome': 'needs_confirmation',
                'profile': profile, 'fieldStates': states, 'error': 'REVIEW_CONFIRMATION_REQUIRED',
                'questions': [{'field': field, 'questionId': 'confirm_' + field,
                    'reason': 'REVIEW_ISSUE' if state == 'unresolved' else 'CONFIRM_SUGGESTION'}
                    for field, state in states.items() if state != 'unknown']}

    def call(self, response, **kwargs):
        from agentfit_ai.analysis_process import run_analysis_process
        from test_candidate_confirmation import DOCUMENT, DOCUMENT_ID
        command = [sys.executable, '-c', 'import sys,json; json.load(sys.stdin); print(' + repr(json.dumps(response)) + ')']
        async def run():
            return await run_analysis_process(DOCUMENT, DOCUMENT_ID, 'synthetic-solar',
                asyncio.get_running_loop().time() + 10, command=command, **kwargs)
        return asyncio.run(run())

    def test_integrated_v2_preserves_nonnull_unresolved_and_safe_failure(self):
        draft = self.draft()
        self.assertEqual(self.call(draft, integrated_candidates=True, nvidia_key='synthetic-nvidia'), draft)
        failed = {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_TIMEOUT'}
        self.assertEqual(self.call(failed, integrated_candidates=True, nvidia_key='synthetic-nvidia'), failed)

    def test_integrated_rejects_complete_v1_corrupt_profile_and_private_failure(self):
        from agentfit_ai.analysis_process import AnalysisProcessError
        bad = deepcopy(self.draft())
        bad['profile']['evidence']['frontend'][0]['documentId'] = 'wrong'
        cases = [bad, {'outcome': 'complete', 'profile': {}},
                 {'outcome': 'failed', 'error': 'PROVIDER_TIMEOUT'},
                 {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'private detail'}]
        for response in cases:
            with self.subTest(outcome=response['outcome']), self.assertRaises(AnalysisProcessError) as caught:
                self.call(response, integrated_candidates=True, nvidia_key='synthetic-nvidia')
            self.assertEqual(str(caught.exception), 'ANALYSIS_WORKER_FAILED')
        for options in ({}, {'recoverable_solar': True}):
            with self.subTest(options=options), self.assertRaises(AnalysisProcessError):
                self.call(self.draft(), **options)

    def test_invalid_modes_or_keys_never_launch_worker(self):
        from agentfit_ai.analysis_process import AnalysisProcessError
        variants = ({'integrated_candidates': True}, {'nvidia_key': 'synthetic'},
                    {'integrated_candidates': True, 'nvidia_key': ' '},
                    {'integrated_candidates': 1, 'nvidia_key': 'synthetic'},
                    {'recoverable_solar': True, 'integrated_candidates': True, 'nvidia_key': 'synthetic'})
        with patch('agentfit_ai.analysis_process.asyncio.create_subprocess_exec',
                   side_effect=AssertionError('invalid request launched')):
            for options in variants:
                with self.subTest(options=options), self.assertRaises(AnalysisProcessError):
                    self.call(self.draft(), **options)

    def test_both_keys_only_cross_stdin_and_mode_is_explicit(self):
        from agentfit_ai.analysis_process import run_analysis_process
        from test_candidate_confirmation import DOCUMENT, DOCUMENT_ID
        response = {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_TIMEOUT'}
        command = [sys.executable, '-c', (
            "import sys,os,json; r=json.load(sys.stdin); "
            "assert set(r)=={'document','documentId','key','nvidiaKey','mode'}; "
            "assert r['key']=='synthetic-solar' and r['nvidiaKey']=='synthetic-nvidia'; "
            "assert r['mode']=='integrated-candidates'; "
            "assert all(os.getenv(k) is None for k in ('UPSTAGE_API_KEY','NVIDIA_API_KEY')); "
            "assert r['key'] not in str(sys.argv) and r['nvidiaKey'] not in str(sys.argv); "
            'print(' + repr(json.dumps(response)) + ')')]
        async def run():
            return await run_analysis_process(DOCUMENT, DOCUMENT_ID, 'synthetic-solar',
                asyncio.get_running_loop().time() + 10, integrated_candidates=True,
                nvidia_key='synthetic-nvidia', command=command)
        with patch.dict(os.environ, {'UPSTAGE_API_KEY': 'synthetic-solar', 'NVIDIA_API_KEY': 'synthetic-nvidia'}):
            self.assertEqual(asyncio.run(run()), response)


if __name__ == "__main__":
    unittest.main()
