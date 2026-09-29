import json
import unittest
from unittest.mock import Mock

from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.nvidia_source_selector import NvidiaSourceSelectorAnalyzer
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from test_semantic_review import verdict


def reply(fields, model=MODEL):
    return json.dumps({"model": model, "choices": [{"finish_reason": "stop",
                       "message": {"content": json.dumps(fields)}}],
                       "usage": {"prompt_tokens": 2, "completion_tokens": 3}}).encode()


def core():
    fields = {field: None for field in FIELDS if field != "features"}
    fields["project_name"] = {"state": "confirmed", "items": [
        {"lineId": 1, "selector": "BODY", "role": "product_fact"}]}
    return fields


def features():
    return {"features": {"state": "confirmed", "items": [
        {"lineId": 2, "selector": "BODY", "role": "user_action"}]}}


class NvidiaSourceSelectorTests(unittest.TestCase):
    def test_compact_review_uses_nvidia_sender_and_normalizes_reply(self):
        transport = Mock(side_effect=[reply(core()), reply(features()),
                                      reply({"issues": []})])
        analyzer = NvidiaSourceSelectorAnalyzer(
            "synthetic-nvidia-key", transport=transport, compact_review=True)
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        review = transport.call_args_list[2].args[0]
        self.assertEqual(review["model"], MODEL)
        self.assertEqual(review["max_tokens"], 4096)
        self.assertEqual(review["response_format"]["json_schema"]["schema"]["required"],
                         ["issues"])

    def test_all_stages_route_to_deepseek_with_same_schema_and_nvidia_key(self):
        transport = Mock(side_effect=[reply(core()), reply(features()), reply(verdict())])
        analyzer = NvidiaSourceSelectorAnalyzer(
            "synthetic-nvidia-key", transport=transport, model=MODEL,
            analysis_timeout_seconds=300, field_call_timeout_seconds=120,
            experimental_long_timeout=True)
        result = analyzer.analyze("# Alpha\n- registration", "doc")
        self.assertEqual(result.profile["data"]["project_name"], "Alpha")
        self.assertEqual(result.profile["data"]["features"], ["registration"])
        self.assertEqual(result.diagnostics["calls"][0]["model"], MODEL)
        self.assertEqual(transport.call_count, 3)
        for call in transport.call_args_list:
            payload, key, timeout = call.args
            self.assertEqual((payload["model"], key), (MODEL, "synthetic-nvidia-key"))
            self.assertEqual(payload["chat_template_kwargs"], {"thinking": False})
            self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(transport.call_args_list[0].args[2], 120)

    def test_wrong_reported_model_and_sensitive_input_fail_before_profile(self):
        transport = Mock(return_value=reply(core(), model="other/model"))
        analyzer = NvidiaSourceSelectorAnalyzer("synthetic-nvidia-key", transport=transport)
        with self.assertRaises(AnalysisError) as caught:
            analyzer.analyze("# Alpha\n- registration", "doc")
        self.assertEqual(caught.exception.code, "PROVIDER_MODEL")
        transport.reset_mock()
        with self.assertRaises(AnalysisError):
            analyzer.analyze("synthetic-nvidia-key", "doc")
        transport.assert_not_called()

    def test_unknown_nvidia_model_is_rejected(self):
        with self.assertRaises(ValueError):
            NvidiaSourceSelectorAnalyzer("synthetic-key", model="unknown/model")
