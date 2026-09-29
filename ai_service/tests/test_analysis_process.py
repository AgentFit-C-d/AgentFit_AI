import asyncio
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


if __name__ == "__main__":
    unittest.main()
