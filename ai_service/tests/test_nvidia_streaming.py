"""A stream must be complete and bounded before the normal model parser sees it."""
import json
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import threading
import time
import unittest
from unittest.mock import patch

from agentfit_ai.deepseek_evaluation import MODEL, NvidiaAnalyzer
from agentfit_ai.nvidia_streaming import _assemble_sse, post_nvidia_streaming
from agentfit_ai.solar import AnalysisError

# Allow process startup separately from the explicit in-flight deadline tests.
LOCAL_HTTP_TIMEOUT = 10
IN_FLIGHT_TIMEOUT = 5


def event(*, content=None, finish=None, model=MODEL, identity='completion-1', **delta):
    if content is not None:
        delta['content'] = content
    return {'id': identity, 'model': model, 'choices': [
        {'index': 0, 'delta': delta, 'finish_reason': finish}]}


def wire(events, *, done=True, newline=b'\n'):
    parts = [b'data: ' + json.dumps(row, ensure_ascii=False).encode() + newline * 2 for row in events]
    if done:
        parts.append(b'data: [DONE]' + newline * 2)
    return b''.join(parts)


@contextmanager
def local_provider(body, *, status=200, headers=None, drip=False, slow_headers=False, streamed=None):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            incoming = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append({'payload': incoming, 'authorization': self.headers.get('Authorization'),
                             'accept': self.headers.get('Accept')})
            try:
                if slow_headers:
                    self.wfile.write(b'HTTP/1.1 200 OK\r\n')
                    self.wfile.flush()
                    if streamed is not None:
                        streamed.set()
                    for byte in b'Content-Type: text/event-stream\r\n\r\n':
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.5)
                    return
                self.send_response(status)
                for name, value in dict({'Content-Type': 'text/event-stream'}, **(headers or {})).items():
                    self.send_header(name, value)
                self.end_headers()
                if drip:
                    for _ in range(750):
                        self.wfile.write(b': heartbeat\n\n')
                        self.wfile.flush()
                        if streamed is not None:
                            streamed.set()
                        time.sleep(0.04)
                else:
                    for offset in range(0, len(body), 7):
                        self.wfile.write(body[offset:offset + 7])
                        self.wfile.flush()
            except OSError:
                pass

        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        with patch('agentfit_ai.nvidia_streaming.ENDPOINT', f'http://127.0.0.1:{server.server_port}/v1/chat/completions'):
            yield requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


class StreamingTransportTests(unittest.TestCase):
    KEY = 'local-fixture-token'

    def payload(self):
        return {'model': MODEL, 'messages': [{'role': 'user', 'content': 'invented input'}],
                'stream': False, 'max_tokens': 512, 'chat_template_kwargs': {'thinking': False}}

    def test_real_worker_streams_into_existing_parser_without_mutating_request(self):
        original = self.payload()
        before = deepcopy(original)
        source = wire([event(role='assistant'), event(content='{"value":7}', finish='stop')])
        with local_provider(source) as requests:
            sender = NvidiaAnalyzer(self.KEY, transport=post_nvidia_streaming, model=MODEL)
            body, model, pt, ct = sender._send_payload(original, ('value',), timeout=LOCAL_HTTP_TIMEOUT)
        self.assertEqual((body, model, pt, ct), ({'value': 7}, MODEL, None, None))
        self.assertEqual(original, before)
        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0]['payload']['stream'])
        self.assertEqual(requests[0]['payload']['max_tokens'], 512)
        self.assertEqual(requests[0]['payload']['chat_template_kwargs'], {'thinking': False})
        self.assertEqual(requests[0]['authorization'], 'Bearer ' + self.KEY)
        self.assertEqual(requests[0]['accept'], 'text/event-stream')

    def test_http_error_and_redirect_never_return_error_body_or_retry(self):
        for status, code in ((401, 'PROVIDER_AUTH'), (429, 'PROVIDER_RATE_LIMIT'),
                             (503, 'PROVIDER_UNAVAILABLE'), (400, 'PROVIDER_REQUEST'),
                             (302, 'PROVIDER_REDIRECT')):
            with self.subTest(status=status), local_provider(b'private body', status=status,
                    headers={'Location': 'http://127.0.0.1:1/forbidden'}) as requests:
                with self.assertRaises(AnalysisError) as caught:
                    post_nvidia_streaming(self.payload(), self.KEY, LOCAL_HTTP_TIMEOUT)
                self.assertEqual(str(caught.exception), code)
                self.assertEqual(len(requests), 1)

    def test_mime_encoding_and_declared_size_are_checked(self):
        valid = wire([event(content='{}', finish='stop')])
        for headers, code in (({'Content-Type': 'application/json'}, 'INVALID_RESPONSE'),
                              ({'Content-Encoding': 'gzip'}, 'INVALID_RESPONSE'),
                              ({'Content-Length': '99999999'}, 'RESPONSE_TOO_LARGE'),
                              ({'Content-Length': 'invalid'}, 'INVALID_RESPONSE')):
            with self.subTest(headers=headers), local_provider(valid, headers=headers):
                with self.assertRaises(AnalysisError) as caught:
                    post_nvidia_streaming(self.payload(), self.KEY, LOCAL_HTTP_TIMEOUT)
                self.assertEqual(caught.exception.code, code)

    def test_truncated_stream_partial_output_and_mismatched_model_fail_in_worker(self):
        for source, code in ((wire([event(content='{}', finish='stop')], done=False), 'INCOMPLETE_RESPONSE'),
                              (wire([event(content='{}', finish='stop', model='wrong')]), 'PROVIDER_MODEL'),
                              (b'data: invalid\n\n', 'INVALID_RESPONSE')):
            with self.subTest(code=code), local_provider(source):
                with self.assertRaises(AnalysisError) as caught:
                    post_nvidia_streaming(self.payload(), self.KEY, LOCAL_HTTP_TIMEOUT)
                self.assertEqual(caught.exception.code, code)

    def test_slow_headers_or_keepalive_events_cannot_extend_parent_deadline(self):
        for mode in ('drip', 'slow_headers'):
            streamed = threading.Event()
            with self.subTest(mode=mode), local_provider(b'', streamed=streamed, **{mode: True}):
                started = time.monotonic()
                with self.assertRaises(AnalysisError) as caught:
                    post_nvidia_streaming(self.payload(), self.KEY, IN_FLIGHT_TIMEOUT)
                self.assertEqual(caught.exception.code, 'PROVIDER_TIMEOUT')
                self.assertTrue(streamed.is_set(), 'deadline must expire during the HTTP response')
                self.assertLess(time.monotonic() - started, IN_FLIGHT_TIMEOUT + 1.5)

    def test_short_deadline_is_forwarded_unchanged_and_timeout_is_sanitized(self):
        for deadline in (0.25, 0.35):
            with self.subTest(deadline=deadline), patch(
                    'agentfit_ai.nvidia_streaming.subprocess.run',
                    side_effect=subprocess.TimeoutExpired('synthetic private command', deadline)) as spawn:
                with self.assertRaises(AnalysisError) as caught:
                    post_nvidia_streaming(self.payload(), self.KEY, deadline)
            self.assertEqual(str(caught.exception), 'PROVIDER_TIMEOUT')
            self.assertEqual(spawn.call_args.kwargs['timeout'], deadline)
            self.assertEqual(json.loads(spawn.call_args.kwargs['input'])['timeout'], deadline)
            self.assertEqual(spawn.call_count, 1)

    def test_invalid_inputs_cannot_start_child(self):
        with patch('agentfit_ai.nvidia_streaming.subprocess.run') as spawn:
            for payload, key, timeout in (({}, self.KEY, 1), (self.payload(), '', 1),
                                          (self.payload(), self.KEY, 0),
                                          (self.payload(), self.KEY, True),
                                          (self.payload(), self.KEY, float('nan')),
                                          (self.payload(), self.KEY, float('inf')),
                                          (self.payload(), self.KEY, 10 ** 1000),
                                          (self.payload(), self.KEY, 601)):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    post_nvidia_streaming(payload, key, timeout)
            with patch('agentfit_ai.nvidia_streaming.MAX_INPUT_BYTES', 20), self.assertRaises(ValueError):
                post_nvidia_streaming(self.payload(), self.KEY, 1)
        self.assertEqual(spawn.call_count, 0)

    def test_untrusted_child_framing_cannot_be_success_or_expose_body(self):
        for output, returncode in ((b'Eprivate response', 0), (b'partial JSON', 0),
                                   (b'S{}', 1), (b'', 0)):
            with self.subTest(output=output), patch('agentfit_ai.nvidia_streaming.subprocess.run',
                    return_value=subprocess.CompletedProcess([], returncode, stdout=output)):
                with self.assertRaises(AnalysisError) as caught:
                    post_nvidia_streaming(self.payload(), self.KEY, 1)
                self.assertEqual(str(caught.exception), 'PROVIDER_NETWORK')

    def test_child_gets_key_only_in_stdin_and_parent_applies_requested_timeout(self):
        with patch('agentfit_ai.nvidia_streaming.subprocess.run',
                return_value=subprocess.CompletedProcess([], 0, stdout=b'S{}')) as spawn:
            self.assertEqual(post_nvidia_streaming(self.payload(), self.KEY, 2.5), b'{}')
        arguments, options = spawn.call_args
        self.assertNotIn(self.KEY, json.dumps(arguments))
        self.assertNotIn(self.KEY, json.dumps(options['env']))
        request = json.loads(options['input'])
        self.assertEqual(request['key'], self.KEY)
        self.assertEqual(options['timeout'], 2.5)
        self.assertEqual(options['stderr'], subprocess.DEVNULL)


class SSEAssemblyTests(unittest.TestCase):
    def assert_error(self, source, code):
        with self.assertRaises(AnalysisError) as caught:
            _assemble_sse([source], MODEL)
        self.assertEqual(caught.exception.code, code)

    def test_fragmented_utf8_and_crlf_preserve_content_and_exclude_reasoning(self):
        source = b': heartbeat\r\nevent: message\r\n\r\n' + wire([
            event(role='assistant', reasoning_content='private analysis'),
            event(content='{"value":"한'), event(content='글"}', finish='stop'),
            {'id': 'completion-1', 'model': MODEL, 'choices': [],
             'usage': {'prompt_tokens': 4, 'completion_tokens': 7}}], newline=b'\r\n')
        result = json.loads(_assemble_sse((bytes([byte]) for byte in source), MODEL))
        self.assertEqual(result, {'model': MODEL, 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': '{"value":"한글"}'}}],
            'usage': {'prompt_tokens': 4, 'completion_tokens': 7}})
        self.assertNotIn('private analysis', json.dumps(result))

    def test_multiline_event_and_missing_usage_are_supported(self):
        source = wire([event(content='{"value":1}', finish='stop')])
        source = source.replace(b', "choices":', b',\ndata: "choices":', 1)
        result = json.loads(_assemble_sse([source], MODEL))
        self.assertEqual(result['usage'], {})
        self.assertEqual(result['choices'][0]['message']['content'], '{"value":1}')

    def test_nonstop_finish_is_preserved_for_existing_parser_to_reject(self):
        assembled = _assemble_sse([wire([event(content='{"value":1}', finish='length')])], MODEL)
        self.assertEqual(json.loads(assembled)['choices'][0]['finish_reason'], 'length')
        sender = NvidiaAnalyzer('test-key', transport=lambda *args: assembled, model=MODEL)
        with self.assertRaises(AnalysisError) as caught:
            sender._send_payload({'model': MODEL, 'max_tokens': 1}, ('value',))
        self.assertEqual(caught.exception.code, 'INCOMPLETE_RESPONSE')

    def test_normal_assembled_response_uses_existing_schema_validator(self):
        assembled = _assemble_sse([wire([event(content='{"value":1}', finish='stop')])], MODEL)
        sender = NvidiaAnalyzer('test-key', transport=lambda *args: assembled, model=MODEL)
        body, model, prompt, completion = sender._send_payload({'max_tokens': 512}, ('value',))
        self.assertEqual((body, model, prompt, completion), ({'value': 1}, MODEL, None, None))
        with self.assertRaises(AnalysisError):
            sender._send_payload({'max_tokens': 512}, ('wrong_field',))

    def test_truncated_stream_or_missing_finish_never_becomes_success(self):
        for source in (b'', wire([event(content='{}', finish='stop')], done=False),
                       wire([event(content='{}')]), b'data: [DONE]\n\n',
                       wire([event(content='{}', finish='stop')])[:-1]):
            with self.subTest(source=source[:20]):
                self.assert_error(source, 'INCOMPLETE_RESPONSE')

    def test_model_mismatch_or_absence_cannot_be_relabelled_as_requested_model(self):
        self.assert_error(wire([event(content='{}', finish='stop', model='wrong')]), 'PROVIDER_MODEL')
        self.assert_error(wire([event(content='{'), event(content='}', finish='stop', model='wrong')]),
                          'PROVIDER_MODEL')
        item = event(content='{}', finish='stop')
        del item['model']
        self.assert_error(wire([item]), 'PROVIDER_MODEL')

    def test_completion_identity_cannot_change_midstream(self):
        self.assert_error(wire([event(content='{'), event(content='}', finish='stop', identity='other')]),
                          'INVALID_RESPONSE')

    def test_choice_shape_and_unexpected_delta_cannot_hide_another_output(self):
        invalid = []
        for index in (1, True, -1):
            item = event(content='{}', finish='stop')
            item['choices'][0]['index'] = index
            invalid.append(item)
        item = event(content='{}', finish='stop')
        item['choices'].append(dict(item['choices'][0]))
        invalid.extend([item, event(content='{}', finish='stop', role='user'),
                        event(content='{}', finish='stop', tool_calls=[{'id': 'x'}]),
                        event(content='{}', finish='stop', function_call={'name': 'x'}),
                        event(content='{}', finish='stop', refusal='refused'),
                        event(content=['invalid'], finish='stop'),
                        event(content='{}', finish='stop', reasoning_content=123)])
        for item in invalid:
            with self.subTest(item=item):
                self.assert_error(wire([item]), 'INVALID_RESPONSE')

    def test_content_or_second_finish_after_completion_is_rejected(self):
        for last in (event(content='extra'), event(finish='stop')):
            self.assert_error(wire([event(content='{}', finish='stop'), last]), 'INVALID_RESPONSE')

    def test_malformed_json_utf8_duplicate_keys_and_error_events_fail_closed(self):
        for source in (b'data: {broken}\n\n', b'data: \xff\n\n',
                       b'data: {"model":"a","model":"b"}\n\n',
                       wire([{'error': {'message': 'private upstream error'}}]),
                       wire([{'choices': 'bad'}])):
            with self.subTest(source=source[:25]):
                self.assert_error(source, 'INVALID_RESPONSE')

    def test_wire_event_and_final_envelope_limits_apply_before_success(self):
        valid = wire([event(content='{"value":1}', finish='stop')])
        with patch('agentfit_ai.nvidia_streaming.MAX_STREAM_BYTES', len(valid)):
            self.assertEqual(json.loads(_assemble_sse([valid], MODEL))['model'], MODEL)
            self.assert_error(b':x\n\n' + valid, 'RESPONSE_TOO_LARGE')
        with patch('agentfit_ai.nvidia_streaming.MAX_EVENT_BYTES', 32):
            self.assert_error(b'data: ' + b'x' * 33, 'RESPONSE_TOO_LARGE')
            self.assert_error(b'data: ' + b'x' * 20 + b'\ndata: ' + b'x' * 20 + b'\n\n',
                              'RESPONSE_TOO_LARGE')
        with patch('agentfit_ai.nvidia_streaming.MAX_RESPONSE_BYTES', 8):
            self.assert_error(valid, 'RESPONSE_TOO_LARGE')


if __name__ == '__main__':
    unittest.main()
