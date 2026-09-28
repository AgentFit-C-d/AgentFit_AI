import json
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import unittest
from unittest.mock import patch, MagicMock

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
        return SolarAnalyzer(KEY, evidence_contract=False, semantic_review=False, transport=lambda payload, *args: stage_reply(reply, payload)).analyze(document, "doc-1")

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
        SolarAnalyzer(KEY, evidence_contract=False, semantic_review=False, transport=transport).analyze("Alpha", "doc-1")
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
        client = SolarAnalyzer(KEY, evidence_contract=False, semantic_review=False, transport=transport)
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
            SolarAnalyzer(KEY, evidence_contract=False, semantic_review=False, transport=broken).analyze("Alpha", "doc-1")
        self.assertEqual(caught.exception.code, "PROVIDER_TIMEOUT")
        self.assertNotIn(KEY, str(caught.exception))


class HttpTests(unittest.TestCase):
    def test_short_local_http_response_is_returned_intact(self):
        class ShortHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), ShortHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch("agentfit_ai.solar.ENDPOINT",
                       f"http://127.0.0.1:{server.server_port}/chat/completions"):
                self.assertEqual(post_solar({}, KEY, 1), b'{"ok":true}')
        finally:
            server.shutdown()
            server.server_close()

    def test_chunked_local_http_response_is_returned_intact(self):
        class ChunkedHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(b"3\r\nabc\r\n3\r\ndef\r\n0\r\n\r\n")

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), ChunkedHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch("agentfit_ai.solar.ENDPOINT",
                       f"http://127.0.0.1:{server.server_port}/chat/completions"):
                self.assertEqual(post_solar({}, KEY, 1), b"abcdef")
        finally:
            server.shutdown()
            server.server_close()

    def test_compressed_provider_body_is_rejected_before_decode(self):
        class CompressedHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                body = gzip.compress(b'{"ok":true}')
                self.send_response(200)
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), CompressedHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch("agentfit_ai.solar.ENDPOINT",
                       f"http://127.0.0.1:{server.server_port}/"):
                with self.assertRaises(AnalysisError) as caught:
                    post_solar({}, KEY, 1)
            self.assertEqual(caught.exception.code, "INVALID_RESPONSE")
        finally:
            server.shutdown()
            server.server_close()

    def test_slow_stream_cannot_extend_total_call_timeout(self):
        class DripHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.send_header("Content-Length", "12")
                self.end_headers()
                try:
                    for _ in range(12):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.1)
                except OSError:
                    pass

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), DripHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            endpoint = f"http://127.0.0.1:{server.server_port}/chat/completions"
            started = time.monotonic()
            with patch("agentfit_ai.solar.ENDPOINT", endpoint):
                with self.assertRaises(AnalysisError) as caught:
                    post_solar({}, KEY, 0.35)
            self.assertEqual(caught.exception.code, "PROVIDER_TIMEOUT")
            self.assertLess(time.monotonic() - started, 0.9)
        finally:
            server.shutdown()
            server.server_close()

    def test_slow_headers_cannot_extend_total_call_timeout(self):
        class SlowHeaders(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                try:
                    self.wfile.write(b"HTTP/1.1 200 OK\r\n")
                    self.wfile.flush()
                    for byte in b"Content-Length: 2\r\n\r\nok":
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.05)
                except OSError:
                    pass

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHeaders)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            started = time.monotonic()
            with patch("agentfit_ai.solar.ENDPOINT",
                       f"http://127.0.0.1:{server.server_port}/chat/completions"):
                with self.assertRaises(AnalysisError) as caught:
                    post_solar({}, KEY, 0.25)
            self.assertEqual(caught.exception.code, "PROVIDER_TIMEOUT")
            self.assertLess(time.monotonic() - started, 0.7)
        finally:
            server.shutdown()
            server.server_close()

    def test_early_eof_with_content_length_is_network_failure(self):
        class Truncated(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.send_header("Content-Length", "8")
                self.end_headers()
                self.wfile.write(b"abc")

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Truncated)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch("agentfit_ai.solar.ENDPOINT",
                       f"http://127.0.0.1:{server.server_port}/chat/completions"):
                with self.assertRaises(AnalysisError) as caught:
                    post_solar({}, KEY, 1)
            self.assertEqual(caught.exception.code, "PROVIDER_NETWORK")
        finally:
            server.shutdown()
            server.server_close()

    def test_early_eof_with_chunked_body_is_network_failure(self):
        class TruncatedChunk(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(b"5\r\nabc")

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), TruncatedChunk)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch("agentfit_ai.solar.ENDPOINT",
                       f"http://127.0.0.1:{server.server_port}/chat/completions"):
                with self.assertRaises(AnalysisError) as caught:
                    post_solar({}, KEY, 1)
            self.assertEqual(caught.exception.code, "PROVIDER_NETWORK")
        finally:
            server.shutdown()
            server.server_close()

    def test_http_status_mapping_and_no_retry(self):
        class StatusHandler(BaseHTTPRequestHandler):
            requests = []

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.requests.append(self.path)
                self.send_response(int(self.path[1:]))
                self.end_headers()

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), StatusHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for status, code in ((401, "PROVIDER_AUTH"), (403, "PROVIDER_AUTH"),
                                 (429, "PROVIDER_RATE_LIMIT"), (503, "PROVIDER_UNAVAILABLE"),
                                 (400, "PROVIDER_REQUEST"), (302, "PROVIDER_REDIRECT")):
                with patch("agentfit_ai.solar.ENDPOINT",
                           f"http://127.0.0.1:{server.server_port}/{status}"):
                    with self.assertRaises(AnalysisError) as caught:
                        post_solar({}, KEY, 1)
                self.assertEqual(caught.exception.code, code)
            self.assertEqual(StatusHandler.requests,
                             ["/401", "/403", "/429", "/503", "/400", "/302"])
        finally:
            server.shutdown()
            server.server_close()

    def test_network_failure_is_mapped_without_exception_text(self):
        class Disconnected(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.connection.close()

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Disconnected)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch("agentfit_ai.solar.ENDPOINT",
                       f"http://127.0.0.1:{server.server_port}/"):
                with self.assertRaises(AnalysisError) as caught:
                    post_solar({}, KEY, 1)
            self.assertEqual(caught.exception.code, "PROVIDER_NETWORK")
            self.assertNotIn(KEY, str(caught.exception))
        finally:
            server.shutdown()
            server.server_close()

    def test_response_size_limit(self):
        class Oversized(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                body = b"x" * 1_048_577
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except OSError:
                    pass

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Oversized)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch("agentfit_ai.solar.ENDPOINT",
                       f"http://127.0.0.1:{server.server_port}/"):
                with self.assertRaises(AnalysisError) as caught:
                    post_solar({}, KEY, 1)
            self.assertEqual(caught.exception.code, "RESPONSE_TOO_LARGE")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
