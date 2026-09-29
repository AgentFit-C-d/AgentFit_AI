import json
import sys
import tempfile
import unittest
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import Mock, patch

from agentfit_ai.profile import FIELDS
from agentfit_ai.section_feature_review import section_review_payload
from agentfit_ai.solar import AnalysisError


DOCUMENT = "# Alpha\n- registration"


def response(fields):
    return json.dumps({"model": "solar-pro4-260806",
                       "choices": [{"finish_reason": "stop", "message": {
                           "content": json.dumps(fields)}}],
                       "usage": {"prompt_tokens": 10, "completion_tokens": 20}}).encode()


def core():
    fields = {field: None for field in FIELDS if field != "features"}
    fields["project_name"] = {"state": "confirmed", "items": [
        {"lineId": 1, "selector": "BODY", "role": "product_fact"}]}
    return fields


def features():
    return {"features": {"state": "confirmed", "items": [
        {"lineId": 2, "selector": "BODY", "role": "user_action"}]}}


class SectionReviewModelProbeTests(unittest.TestCase):
    def test_probe_arms_share_review_input_and_schema(self):
        probe = import_module("agentfit_ai.section_review_model_probe")
        self.assertTrue(hasattr(probe, "probe_arms"))
        transport = Mock(side_effect=[response(core()), response(features())])
        profile = probe.capture_draft(DOCUMENT, "doc", "synthetic-key", transport)
        base = section_review_payload(DOCUMENT, profile, (1, 2),
                                      model="solar-pro4", effort="medium")
        arms = probe.probe_arms(base)
        self.assertEqual(len(arms), 6)
        self.assertEqual([(model, effort) for model, effort, _ in arms[:3]],
                         [("solar-pro4", "medium"), ("solar-pro4", "low"),
                          ("solar-pro4", "none")])
        self.assertEqual([effort for _, effort, _ in arms[3:]],
                         ["provider_default"] * 3)
        for _, _, payload in arms:
            self.assertEqual(payload["messages"], base["messages"])
            self.assertEqual(payload["response_format"], base["response_format"])

    def test_cli_requires_live_and_never_overwrites_results(self):
        probe = import_module("agentfit_ai.section_review_model_probe")
        self.assertTrue(hasattr(probe, "main"))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "probe.json"
            with patch.object(sys, "argv", ["probe", "--output", str(output)]):
                with self.assertRaises(SystemExit):
                    probe.main()
            output.write_text("existing", encoding="utf-8")
            with patch.object(sys, "argv", ["probe", "--live", "--output",
                                                str(output)]):
                with self.assertRaises(SystemExit):
                    probe.main()
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_cli_does_not_allow_replacing_pinned_document_or_section(self):
        probe = import_module("agentfit_ai.section_review_model_probe")
        with tempfile.TemporaryDirectory() as temp:
            output = str(Path(temp) / "probe.json")
            for extra in (("--manifest", "other.json"),
                          ("--section-index", "1")):
                with self.subTest(extra=extra):
                    with patch.object(sys, "argv", ["probe", "--live", "--output",
                                                    output, *extra]):
                        with self.assertRaises(SystemExit):
                            probe.main()

    def test_solar_reply_must_identify_pro4(self):
        probe = import_module("agentfit_ai.section_review_model_probe")
        transport = Mock(side_effect=[response(core()), response(features())])
        profile = probe.capture_draft(DOCUMENT, "doc", "synthetic-key", transport)
        payload = section_review_payload(DOCUMENT, profile, (1, 2),
                                         model="solar-pro4", effort="medium")
        sender = Mock()
        sender._send_payload.return_value = (
            {"checkedRange": {"start": 1, "end": 2}, "issues": []},
            "solar-mini4", 12, 34)
        row = probe.evaluate_section(DOCUMENT, profile, (1, 2), sender, payload,
                                     model="solar-pro4", effort="medium")
        self.assertEqual(row["outcome"], "failed")
        self.assertEqual(row["error"], "PROVIDER_MODEL")

    def test_capture_draft_stops_before_any_semantic_review(self):
        self.assertIsNotNone(find_spec("agentfit_ai.section_review_model_probe"))
        capture_draft = import_module("agentfit_ai.section_review_model_probe").capture_draft
        transport = Mock(side_effect=[response(core()), response(features())])
        profile = capture_draft(DOCUMENT, "doc", "synthetic-key", transport)
        self.assertEqual(profile["data"]["features"], ["registration"])
        self.assertEqual(transport.call_count, 2)

    def test_evaluate_section_returns_only_safe_validation_counts(self):
        self.assertIsNotNone(find_spec("agentfit_ai.section_review_model_probe"))
        probe = import_module("agentfit_ai.section_review_model_probe")
        capture_draft, evaluate_section = probe.capture_draft, probe.evaluate_section
        transport = Mock(side_effect=[response(core()), response(features())])
        profile = capture_draft(DOCUMENT, "doc", "synthetic-key", transport)
        payload = section_review_payload(DOCUMENT, profile, (1, 2),
                                         model="solar-pro4", effort="low")
        sender = Mock()
        sender._send_payload.return_value = (
            {"checkedRange": {"start": 1, "end": 2}, "issues": []},
            "solar-pro4", 12, 34)
        row = evaluate_section(DOCUMENT, profile, (1, 2), sender, payload,
                               model="solar-pro4", effort="low")
        self.assertEqual(row["outcome"], "validated")
        self.assertEqual(row["prompt_tokens"], 12)
        self.assertEqual(row["completion_tokens"], 34)
        self.assertEqual(row["issue_count"], 0)
        self.assertNotIn("registration", json.dumps(row))
        self.assertNotIn("Alpha", json.dumps(row))

    def test_evaluate_section_sanitizes_provider_and_shape_failures(self):
        self.assertIsNotNone(find_spec("agentfit_ai.section_review_model_probe"))
        probe = import_module("agentfit_ai.section_review_model_probe")
        capture_draft, evaluate_section = probe.capture_draft, probe.evaluate_section
        transport = Mock(side_effect=[response(core()), response(features())])
        profile = capture_draft(DOCUMENT, "doc", "synthetic-key", transport)
        payload = section_review_payload(DOCUMENT, profile, (1, 2),
                                         model="solar-pro4", effort="medium")
        sender = Mock()
        sender._send_payload.side_effect = AnalysisError("INCOMPLETE_RESPONSE")
        row = evaluate_section(DOCUMENT, profile, (1, 2), sender, payload,
                               model="solar-pro4", effort="medium")
        self.assertEqual(row["error"], "INCOMPLETE_RESPONSE")
        self.assertNotIn("registration", json.dumps(row))
        sender._send_payload.side_effect = None
        sender._send_payload.return_value = (
            {"checkedRange": {"start": 1, "end": 1}, "issues": []},
            "solar-pro4", 12, 34)
        row = evaluate_section(DOCUMENT, profile, (1, 2), sender, payload,
                               model="solar-pro4", effort="medium")
        self.assertEqual(row["error"], "SEMANTIC_REVIEW_INVALID")
