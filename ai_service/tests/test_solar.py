import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import SolarAnalyzer, AnalysisError, post_solar, candidate_to_profile

KEY = "synthetic-local-test-key"


def candidate(text="Alpha"):
    fields = dict.fromkeys(FIELDS)
    fields["project_name"] = {"value": text, "evidenceLineIds": [1]}
    return fields


def envelope(value=None, finish="stop", refusal=None):
    return json.dumps({
        "model": "solar-pro4-test",
        "choices": [{"finish_reason": finish, "message": {
            "content": json.dumps(value if value is not None else candidate()),
            "refusal": refusal,
        }}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 20},
    }).encode()


def stage_reply(raw, payload):
    try:
        value = json.loads(raw)
        fields = json.loads(value["choices"][0]["message"]["content"])
        if type(fields) is dict and set(fields) == set(FIELDS):
            names = payload["response_format"]["json_schema"]["schema"]["required"]
            value["choices"][0]["message"]["content"] = json.dumps({name: fields[name] for name in names})
            return json.dumps(value).encode()
    except (ValueError, TypeError, KeyError, IndexError):
        pass
    return raw


class SolarTests(unittest.TestCase):
    def run_with(self, reply, document="Alpha"):
        return SolarAnalyzer(KEY, semantic_review=False, transport=lambda payload, *args: stage_reply(reply, payload)).analyze(document, "doc-1")

    def test_valid_unicode_evidence_and_safe_result(self):
        value = candidate()
        value["project_name"]["evidenceLineIds"] = [2]
        result = self.run_with(envelope(value), chr(0x1f600) + "\nAlpha")
        self.assertEqual(result.profile["evidence"]["project_name"], [
            {"documentId": "doc-1", "start": 2, "end": 7}])
        self.assertEqual(result.profile["data"]["database"], None)
        self.assertEqual(result.prompt_tokens, 24)
        self.assertNotIn("evidenceQuotes", result.profile)
        self.assertNotIn(KEY, repr(result))

    def test_request_schema_and_instructions(self):
        calls = []
        def transport(payload, key, timeout):
            calls.append((payload, key, timeout))
            return stage_reply(envelope(), payload)
        SolarAnalyzer(KEY, semantic_review=False, transport=transport).analyze("Alpha", "doc-1")
        payload, key, timeout = calls[0]
        self.assertEqual(key, KEY)
        self.assertEqual(timeout, 40)
        self.assertNotIn(KEY, json.dumps(payload))
        schema = payload["response_format"]["json_schema"]
        self.assertTrue(schema["strict"])
        self.assertEqual(set(schema["schema"]["required"]), set(FIELDS) - {"features"})
        self.assertEqual(len(calls), 2)
        self.assertNotIn("tools", payload)

    def test_invalid_input_never_calls_provider(self):
        transport = MagicMock()
        client = SolarAnalyzer(KEY, semantic_review=False, transport=transport)
        for doc in (" ", "x" * 100001, "api_key=abcdef1234567890", KEY):
            with self.subTest(doc_length=len(doc)):
                with self.assertRaises(AnalysisError):
                    client.analyze(doc, "doc-1")
        transport.assert_not_called()

    def test_missing_and_ambiguous_evidence_rejected(self):
        for document, code in (("Beta", "EVIDENCE_NOT_FOUND"),
                               ("Alpha Alpha", "AMBIGUOUS_EVIDENCE")):
            with self.subTest(code=code):
                with self.assertRaises(AnalysisError) as caught:
                    candidate_to_profile(document, "doc-1", {"data": dict.fromkeys(FIELDS) | {"project_name": "Alpha"}, "evidenceQuotes": {f: ["Alpha"] if f == "project_name" else [] for f in FIELDS}})
                self.assertEqual(caught.exception.code, code)

    def test_bad_structure_never_becomes_success(self):
        for value in ([], {"data": {}}, candidate()):
            if isinstance(value, dict) and "project_name" in value:
                value["backend"] = {"value": ["Python"], "evidenceLineIds": []}
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(AnalysisError):
                    self.run_with(envelope(value))

    def test_null_cannot_be_hidden_in_known_object(self):
        value = candidate()
        value["database"] = {"value": None, "evidenceLineIds": [1]}
        with self.assertRaises(AnalysisError) as caught:
            self.run_with(envelope(value))
        self.assertEqual(caught.exception.code, "INVALID_RESPONSE")

    def test_legacy_validator_still_rejects_unknown_evidence(self):
        value = {"data": dict.fromkeys(FIELDS), "evidenceQuotes": {f: [] for f in FIELDS}}
        value["evidenceQuotes"]["database"] = ["Alpha"]
        with self.assertRaises(AnalysisError) as caught:
            candidate_to_profile("Alpha", "doc-1", value)
        self.assertEqual(caught.exception.code, "UNKNOWN_HAS_EVIDENCE")

    def test_old_wire_shape_and_extra_known_keys_rejected(self):
        for value in ({"data": dict.fromkeys(FIELDS), "evidenceQuotes": {}}, candidate()):
            if "project_name" in value:
                value["project_name"]["extra"] = "unexpected"
            with self.assertRaises(AnalysisError) as caught:
                self.run_with(envelope(value))
            self.assertEqual(caught.exception.code, "INVALID_RESPONSE")

    def test_truncated_or_refused_output_rejected(self):
        for reply, code in ((envelope(finish="length"), "INCOMPLETE_RESPONSE"),
                            (envelope(refusal="private provider message"), "PROVIDER_REFUSAL")):
            with self.assertRaises(AnalysisError) as caught:
                self.run_with(reply)
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("private provider", str(caught.exception))

    def test_malformed_json_rejected(self):
        for raw in (b"bad json", b"null", b"{}", b"[]"):
            with self.subTest(raw=raw):
                with self.assertRaises(AnalysisError) as caught:
                    self.run_with(raw)
                self.assertEqual(caught.exception.code, "INVALID_RESPONSE")

    def test_key_in_output_is_not_returned_or_logged(self):
        with self.assertRaises(AnalysisError) as caught:
            self.run_with(envelope(candidate(KEY)))
        self.assertEqual(caught.exception.code, "SENSITIVE_CONTENT")
        self.assertNotIn(KEY, str(caught.exception))

    def test_transport_exception_is_safe(self):
        def broken(*args):
            raise TimeoutError("sensitive message " + KEY)
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer(KEY, semantic_review=False, transport=broken).analyze("Alpha", "doc-1")
        self.assertEqual(caught.exception.code, "PROVIDER_TIMEOUT")
        self.assertNotIn(KEY, str(caught.exception))


class HttpTests(unittest.TestCase):
    @patch("agentfit_ai.solar.build_opener")
    def test_http_status_mapping_and_no_retry(self, factory):
        for status, code in ((401, "PROVIDER_AUTH"), (403, "PROVIDER_AUTH"),
                             (429, "PROVIDER_RATE_LIMIT"), (503, "PROVIDER_UNAVAILABLE"),
                             (400, "PROVIDER_REQUEST"), (302, "PROVIDER_REDIRECT")):
            opener = MagicMock()
            opener.open.side_effect = HTTPError("fixed", status, "private", {}, None)
            factory.return_value = opener
            with self.assertRaises(AnalysisError) as caught:
                post_solar({}, KEY, 40)
            self.assertEqual(caught.exception.code, code)
            opener.open.assert_called_once()

    @patch("agentfit_ai.solar.build_opener")
    def test_network_and_timeout_mapping(self, factory):
        for reason, code in ((TimeoutError(), "PROVIDER_TIMEOUT"),
                             (OSError(), "PROVIDER_NETWORK")):
            factory.return_value.open.side_effect = URLError(reason)
            with self.assertRaises(AnalysisError) as caught:
                post_solar({}, KEY, 40)
            self.assertEqual(caught.exception.code, code)

    @patch("agentfit_ai.solar.build_opener")
    def test_response_size_limit(self, factory):
        factory.return_value.open.return_value.__enter__.return_value.read.return_value = b"x" * (1048576 + 1)
        with self.assertRaises(AnalysisError) as caught:
            post_solar({}, KEY, 40)
        self.assertEqual(caught.exception.code, "RESPONSE_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
