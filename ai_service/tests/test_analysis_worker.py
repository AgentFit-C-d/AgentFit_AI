import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agentfit_ai.solar import AnalysisError


class InlineProviderTests(unittest.TestCase):
    def test_success_returns_provider_body_without_a_subprocess(self):
        from agentfit_ai.solar import post_solar_inline

        with patch("agentfit_ai.provider_worker._fetch", return_value=b'S{"ok":true}') as fetch:
            self.assertEqual(post_solar_inline({"model": "solar-pro4"}, "test-key", 3),
                             b'{"ok":true}')
        fetch.assert_called_once_with("https://api.upstage.ai/v1/chat/completions",
                                      {"model": "solar-pro4"}, "test-key", 3)

    def test_provider_failure_keeps_existing_safe_code(self):
        from agentfit_ai.solar import post_solar_inline

        with patch("agentfit_ai.provider_worker._fetch", return_value=b"EPROVIDER_TIMEOUT"):
            with self.assertRaises(AnalysisError) as caught:
                post_solar_inline({}, "test-key", 3)
        self.assertEqual(caught.exception.code, "PROVIDER_TIMEOUT")


class AnalysisWorkerTests(unittest.TestCase):
    def request(self, document="Alpha", key="test-key"):
        return json.dumps({"document": document, "documentId": "doc_1", "key": key}).encode()

    def test_worker_returns_only_profile_from_analyzer(self):
        from agentfit_ai.analysis_worker import execute_request

        profile = {"data": {"project_name": "Alpha"}}
        with patch("agentfit_ai.analysis_worker.SolarAnalyzer") as analyzer:
            analyzer.return_value.analyze.return_value = SimpleNamespace(profile=profile)
            output = execute_request(self.request())
        self.assertEqual(json.loads(output), {"outcome": "complete", "profile": profile})
        self.assertEqual(analyzer.call_args.kwargs["transport"].__name__, "post_solar_inline")

    def test_worker_does_not_echo_document_or_key_on_failure(self):
        from agentfit_ai.analysis_worker import execute_request

        with patch("agentfit_ai.analysis_worker.SolarAnalyzer") as analyzer:
            analyzer.return_value.analyze.side_effect = RuntimeError("Alpha test-key")
            output = execute_request(self.request())
        self.assertEqual(json.loads(output), {"error": "ANALYSIS_WORKER_FAILED"})
        self.assertNotIn(b"Alpha", output)
        self.assertNotIn(b"test-key", output)

    def test_worker_limits_serialized_output(self):
        from agentfit_ai.analysis_worker import execute_request

        with patch("agentfit_ai.analysis_worker.SolarAnalyzer") as analyzer:
            analyzer.return_value.analyze.return_value = SimpleNamespace(
                profile={"oversized": "X" * 1_500_000})
            output = execute_request(self.request())
        self.assertEqual(json.loads(output), {"error": "ANALYSIS_WORKER_FAILED"})


if __name__ == "__main__":
    unittest.main()
