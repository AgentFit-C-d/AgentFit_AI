"""Offline synthetic streams; no model API or account credential is used."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.nvidia_streaming import post_nvidia_streaming, post_nvidia_streaming_inline
from agentfit_ai.nvidia_streaming import _stream_output, _assemble_sse
from agentfit_ai.solar import AnalysisError
from test_nvidia_streaming import event, wire, local_provider
from test_status_model_comparison import load, HARNESS


class ResponseDiagnosticTests(unittest.TestCase):
    KEY = 'synthetic-diagnostic-key-0123456789'

    def failure(self, body, *, headers=None, status=200, isolated=False, key=None):
        transport = post_nvidia_streaming if isolated else post_nvidia_streaming_inline
        with local_provider(body, headers=headers, status=status) as requests:
            with self.assertRaises(AnalysisError) as caught:
                transport({'model': MODEL}, key or self.KEY, 10)
        self.assertEqual(caught.exception.code, 'INVALID_RESPONSE')
        self.assertEqual(str(caught.exception), 'INVALID_RESPONSE')
        self.assertEqual(len(requests), 1)
        record = getattr(caught.exception, 'response_diagnostic', None)
        self.assertIsInstance(record, dict, 'INVALID_RESPONSE currently drops its HTTP/SSE context')
        return record

    def test_worker_preserves_failed_event_and_json_position_not_previous_event(self):
        first = wire([event(content='{')], done=False)
        bad = b'{"choices":]}'
        record = self.failure(first + b'data: ' + bad + b'\n\n', isolated=True)
        self.assertEqual(record['http_status'], 200)
        self.assertEqual(record['content_type'], 'text/event-stream')
        self.assertEqual(record['error_location'], 'sse.json')
        self.assertEqual(record['sse_event']['index'], 2)
        self.assertEqual(record['sse_event']['excerpt'], bad.decode())
        self.assertEqual(record['sse_event']['data_bytes'], len(bad))
        self.assertEqual(record['sse_event']['json_error'], {'char': 11, 'line': 1, 'column': 12})

    def test_http_rejection_records_metadata_without_reading_or_logging_body(self):
        for status, headers in ((201, {}), (200, {'Content-Type': 'application/json; charset=utf-8'}),
                                (200, {'Content-Encoding': 'gzip'}),
                                (200, {'Content-Length': 'invalid'})):
            with self.subTest(status=status, headers=headers):
                record = self.failure(b'private HTTP body', headers=headers, status=status)
                self.assertEqual(record['http_status'], status)
                self.assertEqual(record['content_type'], headers.get('Content-Type', 'text/event-stream'))
                self.assertEqual(record['error_location'], 'http.content_length' if
                                 'Content-Length' in headers else 'http.headers')
                self.assertIsNone(record['sse_event'])
                self.assertNotIn('private HTTP body', json.dumps(record))

    def test_error_locations_for_duplicate_utf8_shape_usage_delta_and_finish(self):
        invalid_delta = event(content=12)
        samples = [(b'{"choices":[],"choices":[]}', 'sse.json'),
                   (b'\xff', 'sse.json'), (b'[]', 'sse.event'),
                   (b'{"error":{"message":"upstream failure"}}', 'sse.event'),
                   (b'{"choices":"wrong"}', 'sse.choices'),
                   (json.dumps(event(identity='')).encode(), 'sse.id'),
                   (json.dumps(dict(event(), usage={'prompt_tokens': -1})).encode(), 'sse.usage.prompt_tokens'),
                   (json.dumps(invalid_delta).encode(), 'sse.delta.content'),
                   (json.dumps(event(role='user')).encode(), 'sse.delta'),
                   (json.dumps(event(finish='unknown')).encode(), 'sse.finish_reason')]
        for raw, location in samples:
            with self.subTest(location=location, raw=raw):
                record = self.failure(b'data: ' + raw + b'\n\n')
                self.assertEqual(record['error_location'], location)
                self.assertEqual(record['sse_event']['index'], 1)

    def test_raw_excerpt_is_bounded_in_utf8_and_marks_truncation(self):
        raw = json.dumps({'error': {'message': '한' * 5000}}, ensure_ascii=False).encode()
        record = self.failure(b'data: ' + raw + b'\n\n')
        failed = record['sse_event']
        self.assertEqual(failed['data_bytes'], len(raw))
        self.assertLessEqual(len(failed['excerpt'].encode()), 2048)
        self.assertTrue(failed['truncated'])
        self.assertFalse(failed['redacted'])
        self.assertLessEqual(len(json.dumps(record, ensure_ascii=False).encode()), 8192)

    def test_credentials_are_suppressed_before_truncation_even_when_escaped(self):
        escaped = ''.join('\\u%04x' % ord(c) for c in self.KEY)
        samples = [self.KEY, escaped, 'Authorization: Bearer another-secret',
                   '"api_key":"different-secret"', 'Proxy-Authorization: Basic c2VjcmV0',
                   'Bearer another-secret', 'x-api-key: private-key',
                   '\\u0041uthorization: private-secret']
        for secret in samples:
            with self.subTest(secret=secret):
                # A secret after the excerpt boundary must still suppress the entire excerpt.
                raw = ('x' * 3000 + secret).encode()
                record = self.failure(b'data: ' + raw + b'\n\n',
                    headers={'Set-Cookie': 'private-cookie', 'X-API-Key': 'response-secret'})
                encoded = json.dumps(record)
                self.assertNotIn(self.KEY, encoded)
                self.assertNotIn('another-secret', encoded)
                self.assertNotIn('response-secret', encoded)
                self.assertNotIn('private-cookie', encoded)
                self.assertTrue(record['sse_event']['redacted'])
                self.assertEqual(record['sse_event']['excerpt'], '[REDACTED]')

    def test_content_type_is_bounded_and_cannot_echo_key_or_auth_header(self):
        for value in ('application/json; token=' + self.KEY,
                      'application/json; Authorization=secret', 'x/' + 'a' * 500):
            record = self.failure(b'', headers={'Content-Type': value})
            self.assertNotIn(self.KEY, json.dumps(record))
            self.assertNotIn('Authorization', record['content_type'])
            self.assertLessEqual(len(record['content_type'].encode()), 128)

    def test_utf16_utf32_and_nul_separated_credentials_are_not_retained(self):
        for encoding in ('utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be'):
            for isolated in (False, True):
                with self.subTest(encoding=encoding, isolated=isolated):
                    raw = json.dumps({'error': {'message': self.KEY}}).encode(encoding)
                    record = self.failure(b'data: ' + raw + b'\n\n', isolated=isolated)
                    self.assertTrue(record['sse_event']['redacted'])
                    self.assertEqual(record['sse_event']['excerpt'], '[REDACTED]')
        raw = ('bad ' + '\x00'.join(self.KEY)).encode()
        record = self.failure(b'data: ' + raw + b'\n\n')
        self.assertTrue(record['sse_event']['redacted'])

    def test_finished_record_keeps_diagnostic_and_original_terminal_error(self):
        module = load(HARNESS/'experiment.py', 'diagnostic_gate_test')
        jobs = [{'docId': d, 'arm': a, 'batch': b, 'payload': {'model': module.MODELS[a]}}
                for d, a, b in module.SCHEDULE]
        with tempfile.TemporaryDirectory() as tmp, local_provider(b'data: {broken}\n\n'):
            gate = module.ModelCallGate(tmp, jobs, check_free=lambda: 5400,
                check_identity=lambda: None, transport=post_nvidia_streaming_inline)
            with self.assertRaises(AnalysisError):
                gate(jobs[0]['payload'], self.KEY, 10)
            saved = json.loads((Path(tmp)/'01-finished.json').read_text(encoding='utf-8'))
            self.assertIn('response_diagnostic', saved)
            self.assertEqual(saved['response_diagnostic']['error_location'], 'sse.json')
            self.assertEqual(saved['error'], 'INVALID_RESPONSE')
            self.assertFalse(saved['returned'])
            self.assertTrue(gate.stopped)
            self.assertEqual(gate.started, 1)
            self.assertFalse((Path(tmp)/'01-response.json').exists())
            with self.assertRaises(ValueError):
                gate(jobs[1]['payload'], self.KEY, 10)
            self.assertNotIn(self.KEY, ''.join(p.read_text(encoding='utf-8') for p in Path(tmp).iterdir()))

    def test_diagnostic_failure_falls_back_to_original_error(self):
        # Diagnostics JSON encoding may fail; it must not replace INVALID_RESPONSE.
        from agentfit_ai.nvidia_response_diagnostics import encode_diagnostic
        with patch('agentfit_ai.nvidia_stream_worker.encode_diagnostic', return_value=None), \
                local_provider(b'data: {broken}\n\n'):
            with self.assertRaises(AnalysisError) as caught:
                post_nvidia_streaming_inline({'model': MODEL}, self.KEY, 10)
        self.assertEqual(caught.exception.code, 'INVALID_RESPONSE')
        with patch('agentfit_ai.nvidia_response_diagnostics._excerpt', side_effect=ValueError('private')):
            from agentfit_ai.nvidia_response_diagnostics import invalid_response
            self.assertIsNone(encode_diagnostic(invalid_response('sse.json', b'{', 1),
                                               200, 'text/event-stream', self.KEY))

    def test_parent_discards_malformed_or_extra_diagnostic_fields(self):
        record = self.failure(b'data: {broken}\n\n')
        for altered in (dict(record, Authorization=self.KEY),
                        dict(record, content_type='x' * 200),
                        dict(record, sse_event=dict(record['sse_event'], excerpt='x' * 2049)),
                        dict(record, error_location=self.KEY)):
            with self.subTest(record=altered), self.assertRaises(AnalysisError) as caught:
                _stream_output(b'D' + json.dumps(altered).encode(), self.KEY)
            self.assertEqual(str(caught.exception), 'INVALID_RESPONSE')
            self.assertIsNone(caught.exception.response_diagnostic)
        with self.assertRaises(AnalysisError) as caught:
            _stream_output(b'D' + json.dumps(dict(record, content_type=self.KEY)).encode(), self.KEY)
        self.assertNotIn(self.KEY, json.dumps(caught.exception.response_diagnostic))
        for hidden in ('\x00'.join(self.KEY), '\\u0000'.join(self.KEY)):
            forged = dict(record, sse_event=dict(record['sse_event'], excerpt=hidden))
            with self.assertRaises(AnalysisError) as caught:
                _stream_output(b'D' + json.dumps(forged).encode(), self.KEY)
            self.assertEqual(caught.exception.response_diagnostic['sse_event']['excerpt'], '[REDACTED]')

    def test_non_invalid_errors_do_not_gain_raw_diagnostics(self):
        for body, code in ((b'data: [DONE]\n\n', 'INCOMPLETE_RESPONSE'),
                           (wire([event(model='wrong')]), 'PROVIDER_MODEL')):
            with self.subTest(code=code), local_provider(body), self.assertRaises(AnalysisError) as caught:
                post_nvidia_streaming_inline({'model': MODEL}, self.KEY, 10)
            self.assertEqual(caught.exception.code, code)
            self.assertIsNone(getattr(caught.exception, 'response_diagnostic', None))

    def test_success_is_byte_identical_and_reasoning_is_not_retained(self):
        source = wire([event(reasoning_content='discarded internal reasoning'),
                       event(content='{"value":"한글"}', finish='stop')])
        expected = _assemble_sse((bytes([b]) for b in source), MODEL)
        with local_provider(source):
            actual = post_nvidia_streaming({'model': MODEL}, self.KEY, 10)
        self.assertEqual(actual, expected)
        self.assertNotIn(b'discarded', actual)


if __name__ == '__main__':
    unittest.main()
