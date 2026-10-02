"""Offline live-runner gate: real subprocess lifecycle, no external model calls."""
import asyncio
import ctypes
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import monotonic
import unittest

from agentfit_ai.solar import AnalysisError
from review_preservation_fixture import load, offline

FIXTURE = Path(__file__).parent/'fixtures/document_profile_live_worker.py'


class DocumentProfileLiveTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('diagnostic_tools.document_profile_live'),
                             'bounded v3 evaluation runner is not implemented')
        self.live = importlib.import_module('diagnostic_tools.document_profile_live')

    def test_request_cap_and_first_failure_never_send_again(self):
        with TemporaryDirectory() as folder, offline():
            calls = []
            def send(payload, key, timeout):
                calls.append(timeout)
                return b'LOCAL'
            guard = self.live.RequestGuard(send, 1800, Path(folder), clock=lambda: 0)
            for _ in range(50):
                guard({'model': self.live.MODEL}, 'OFFLINE', 600)
            with self.assertRaises(AnalysisError):
                guard({'model': self.live.MODEL}, 'OFFLINE', 600)
            self.assertEqual(len(calls), 50)
        with TemporaryDirectory() as folder, offline():
            calls = []
            def fail(*args):
                calls.append(1)
                raise AnalysisError('PROVIDER_FAILURE')
            guard = self.live.RequestGuard(fail, 1800, Path(folder), clock=lambda: 0)
            for _ in range(2):
                with self.assertRaises(AnalysisError):
                    guard({'model': self.live.MODEL}, 'OFFLINE', 600)
            self.assertEqual(calls, [1])

    def test_request_budget_is_shorter_than_remaining_and_no_expired_request_starts(self):
        for now, expected in ((0, 600), (1770, 28)):
            with TemporaryDirectory() as folder, offline():
                sent = []
                guard = self.live.RequestGuard(lambda p, k, t: sent.append(t) or b'LOCAL',
                                                1800, Path(folder), clock=lambda: now)
                guard({'model': self.live.MODEL}, 'OFFLINE', 600)
                self.assertEqual(sent, [expected])
        with TemporaryDirectory() as folder, offline():
            guard = self.live.RequestGuard(lambda *a: self.fail('expired request sent'),
                                            1800, Path(folder), clock=lambda: 1798)
            with self.assertRaises(AnalysisError):
                guard({'model': self.live.MODEL}, 'OFFLINE', 600)

    def test_unapproved_model_rejected_without_transport(self):
        with TemporaryDirectory() as folder, offline():
            guard = self.live.RequestGuard(lambda *a: self.fail('unapproved model sent'),
                                            1800, Path(folder), clock=lambda: 0)
            with self.assertRaises(AnalysisError):
                guard({'model': 'other-model'}, 'OFFLINE', 600)

    def test_changed_frozen_input_blocks_this_and_later_sends(self):
        with TemporaryDirectory() as folder, offline():
            output = Path(folder)
            source = output/'source.txt'
            gold = output/'gold.json'
            source.write_text('original', encoding='utf-8')
            gold.write_text('{}', encoding='utf-8')
            self.live.save(output/'freeze.json', {'actualWorkingFileHashes': self.live.actual_hashes(),
                'sourcePath': str(source), 'goldPath': str(gold),
                'sourceSha256': self.live.digest(source), 'goldSha256': self.live.digest(gold)})
            sent = []
            guard = self.live.RequestGuard(lambda *a: sent.append(1) or b'LOCAL',
                                            1800, output, clock=lambda: 0)
            source.write_text('changed', encoding='utf-8')
            with self.assertRaises(AnalysisError):
                guard({'model': self.live.MODEL}, 'OFFLINE', 600)
            source.write_text('original', encoding='utf-8')
            with self.assertRaises(AnalysisError):
                guard({'model': self.live.MODEL}, 'OFFLINE', 600)
            self.assertEqual(sent, [])

    def run_child(self, mode, output, total=8, reserve=1):
        return self.live.run_once(load('document.txt'), 'OFFLINE-NONCREDENTIAL', output,
            total_seconds=total, finish_reserve=reserve,
            command_builder=lambda deadline: [sys.executable, str(FIXTURE), mode, str(output), str(deadline)])

    def test_v3_selection_through_parent_child_recorder_final_result(self):
        with TemporaryDirectory() as folder, offline():
            output = Path(folder).resolve()
            result = self.run_child('replay', output, total=20, reserve=2)
            self.assertEqual(result['contract'], 'confirmation-v3')
            self.assertEqual(len(result['reviewDispositions']), 6)
            trace = json.loads((output/'trace.json').read_text(encoding='utf-8'))
            self.assertEqual(trace['status'], 'complete')
            self.assertEqual(trace['stages']['final_response'], result)
            run = json.loads((output/'execution.json').read_text(encoding='utf-8'))
            self.assertEqual(run['requestAttempts'], 22)  # Stored responses, not live requests.
            self.assertEqual(run['retries'], 0)
            self.assertTrue(all(c['state'] == 'completed' for c in
                json.loads((output/'request-journal.json').read_text(encoding='utf-8'))))

    def check_terminated(self, mode, expected):
        with TemporaryDirectory() as folder, offline():
            output = Path(folder).resolve()
            result = self.run_child(mode, output, total=3, reserve=.5)
            self.assertEqual(result.get('error'), expected)
            run = json.loads((output/'execution.json').read_text(encoding='utf-8'))
            self.assertLess(run['elapsedSeconds'], 3)
            self.assertEqual(run['requestAttempts'], 1)
            self.assertTrue((output/'trace-checkpoint.json').exists())
            self.assertTrue((output/'active-request.json').exists())
            termination = json.loads((output/'termination.json').read_text(encoding='utf-8'))
            self.assertTrue(termination['analysisProcessReaped'])
            self.assertEqual(termination['error'], expected)
            if sys.platform == 'win32':
                pid = json.loads((output/'request-journal.json').read_text(encoding='utf-8'))[0]['pid']
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.OpenProcess.restype = ctypes.c_void_p
                kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                handle = kernel.OpenProcess(0x1000, False, pid)
                if handle:
                    code = ctypes.c_ulong()
                    self.assertTrue(kernel.GetExitCodeProcess(handle, ctypes.byref(code)))
                    kernel.CloseHandle(handle)
                    self.assertNotEqual(code.value, 259, 'request process still running')

    def test_total_expiry_terminates_inflight_request_and_preserves_diagnostics(self):
        self.check_terminated('total-timeout', 'ANALYSIS_DEADLINE_EXCEEDED')

    def test_single_request_expiry_terminates_inflight_request_and_preserves_diagnostics(self):
        self.check_terminated('request-timeout', 'PROVIDER_TIMEOUT')


if __name__ == '__main__':
    unittest.main()
