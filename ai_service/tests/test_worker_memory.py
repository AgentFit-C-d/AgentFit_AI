"""OS PDF worker memory boundary, always exercised in a disposable process."""

import subprocess
import sys
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch


class WorkerMemoryTests(unittest.TestCase):
    def test_child_cannot_commit_more_than_its_limit(self):
        script = (
            "from agentfit_ai.worker_memory import apply_pdf_memory_limit\n"
            "apply_pdf_memory_limit(128 * 1024 * 1024)\n"
            "print('applied', flush=True)\n"
            "try:\n"
            "    block = bytearray(256 * 1024 * 1024)\n"
            "    print('allocated', flush=True)\n"
            "except MemoryError:\n"
            "    print('limited', flush=True)\n"
        )
        result = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                timeout=5, check=False)
        self.assertIn(b"applied", result.stdout)
        self.assertNotIn(b"allocated", result.stdout)
        self.assertTrue(b"limited" in result.stdout or result.returncode != 0)

    def test_pdf_main_fails_closed_before_reading_when_limit_setup_fails(self):
        from agentfit_ai import pdf_worker

        input_buffer = Mock()
        output_buffer = BytesIO()
        with patch.object(pdf_worker, "apply_pdf_memory_limit", side_effect=OSError(
                "private operating system detail")), patch.object(
                    pdf_worker.sys, "stdin", SimpleNamespace(buffer=input_buffer)), patch.object(
                    pdf_worker.sys, "stdout", SimpleNamespace(buffer=output_buffer)):
            self.assertEqual(pdf_worker.main(), 0)
        input_buffer.read.assert_not_called()
        self.assertEqual(output_buffer.getvalue(), b'{"error": "PDF_WORKER_FAILED"}')

    def test_memory_error_during_parse_is_safe_worker_failure(self):
        from agentfit_ai import pdf_worker

        with patch("pypdf.PdfReader", side_effect=MemoryError):
            self.assertEqual(pdf_worker.extract_pdf_bytes(b"%PDF-1.4"),
                             {"error": "PDF_WORKER_FAILED"})

    def test_linux_keeps_a_stricter_existing_hard_limit(self):
        from agentfit_ai import worker_memory

        setrlimit = Mock()
        resource = SimpleNamespace(RLIMIT_AS=9, RLIM_INFINITY=-1,
                                   getrlimit=lambda _: (128, 256),
                                   setrlimit=setrlimit)
        with patch.object(worker_memory.sys, "platform", "linux"), patch.dict(
                sys.modules, {"resource": resource}):
            worker_memory.apply_pdf_memory_limit(512)
        setrlimit.assert_called_once_with(9, (256, 256))

    def test_unsupported_platform_fails_closed(self):
        from agentfit_ai import worker_memory

        with patch.object(worker_memory.sys, "platform", "darwin"):
            with self.assertRaises(OSError):
                worker_memory.apply_pdf_memory_limit()


if __name__ == "__main__":
    unittest.main()
