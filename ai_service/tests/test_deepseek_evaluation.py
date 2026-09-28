import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agentfit_ai.deepseek_evaluation import NvidiaAnalyzer, load_key, nvidia_payload
from agentfit_ai.solar import AnalysisError


class DeepseekEvaluationTests(unittest.TestCase):
    def test_explicit_env_file_supplies_nvidia_key_without_logging_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("NVIDIA_API_KEY=fixture-key\n", encoding="utf-8")
            with patch.dict("os.environ", {"NVIDIA_API_KEY": "different-key"}):
                self.assertEqual(load_key(path), "fixture-key")

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

    def test_glm_and_kimi_payloads_preserve_review_schema_with_supported_options(self):
        original = copy.deepcopy(self.source)
        glm = nvidia_payload(self.source, model="z-ai/glm-5.3")
        kimi = nvidia_payload(self.source, model="moonshotai/kimi-k3")
        self.assertEqual(self.source, original)
        for payload, model in ((glm, "z-ai/glm-5.3"), (kimi, "moonshotai/kimi-k3")):
            self.assertEqual(payload["model"], model)
            self.assertEqual(payload["messages"], original["messages"])
            self.assertEqual(payload["response_format"], original["response_format"])
            self.assertNotIn("frequency_penalty", payload)
            self.assertEqual(payload["reasoning_effort"], "low")
        self.assertEqual(glm["chat_template_kwargs"], {"clear_thinking": True})
        self.assertEqual(glm["temperature"], 0.5)
        self.assertNotIn("chat_template_kwargs", kimi)
        self.assertEqual(kimi["temperature"], 1)

    def test_model_specific_parser_rejects_provider_model_mismatch(self):
        for model in ("z-ai/glm-5.3", "moonshotai/kimi-k3"):
            with self.subTest(model=model):
                seen = []
                def transport(payload, key, timeout):
                    seen.append(payload["model"])
                    return json.dumps({"model": model, "choices": [{"finish_reason": "stop",
                        "message": {"content": '{"issues":[]}'}}], "usage": {}}).encode()
                got = NvidiaAnalyzer("secret", model=model, transport=transport)._send_payload(
                    self.source, ("issues",), timeout=40)
                self.assertEqual(got[1], model)
                self.assertEqual(seen, [model])
        with self.assertRaises(ValueError):
            NvidiaAnalyzer("secret", model="unknown/model")


if __name__ == "__main__":
    unittest.main()
