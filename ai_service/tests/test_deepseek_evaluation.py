import copy
import json
import unittest
from unittest.mock import Mock

from agentfit_ai.deepseek_evaluation import NvidiaAnalyzer, nvidia_payload
from agentfit_ai.solar import AnalysisError


class DeepseekEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "model": "solar-pro4", "reasoning_effort": "none",
            "messages": [{"role": "system", "content": "prompt"},
                         {"role": "user", "content": "synthetic candidates"}],
            "response_format": {"type": "json_schema", "json_schema": {"strict": True, "schema": {"type": "object"}}},
            "temperature": 0, "frequency_penalty": 0, "max_tokens": 4096, "stream": False,
        }

    def test_payload_preserves_prompt_candidates_schema_and_source(self):
        before = copy.deepcopy(self.source)
        got = nvidia_payload(self.source)
        self.assertEqual(self.source, before)
        self.assertEqual(got["model"], "deepseek-ai/deepseek-v4.1-flash")
        self.assertEqual(got["chat_template_kwargs"], {"thinking": False})
        self.assertEqual(got["messages"], before["messages"])
        self.assertEqual(got["response_format"], before["response_format"])
        self.assertEqual(got["max_tokens"], 4096)
        self.assertNotIn("reasoning_effort", got)
        self.assertNotIn("frequency_penalty", got)

    def test_common_parser_accepts_valid_reply_and_rejects_empty_content(self):
        captured = []
        def transport(payload, key, timeout):
            captured.append(payload)
            content = '{"decisions":{}}' if len(captured) != 2 else None
            model = "deepseek-ai/deepseek-v4.1-flash" if len(captured) != 3 else "other/model"
            return json.dumps({"model": model, "choices": [
                {"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7}}).encode()
        analyzer = NvidiaAnalyzer("secret", transport=transport)
        reply, model, pt, ct = analyzer._send_payload(self.source, ("decisions",), timeout=40)
        self.assertEqual(reply, {"decisions": {}})
        self.assertEqual((model, pt, ct), ("deepseek-ai/deepseek-v4.1-flash", 11, 7))
        self.assertEqual(captured[0]["chat_template_kwargs"], {"thinking": False})
        with self.assertRaises(AnalysisError) as error:
            analyzer._send_payload(self.source, ("decisions",), timeout=40)
        self.assertEqual(error.exception.code, "INVALID_RESPONSE")
        with self.assertRaises(AnalysisError) as error:
            analyzer._send_payload(self.source, ("decisions",), timeout=40)
        self.assertEqual(error.exception.code, "PROVIDER_MODEL")


if __name__ == "__main__":
    unittest.main()
