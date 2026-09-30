"""A stream must be complete and bounded before the normal model parser sees it."""
import json
import unittest
from unittest.mock import patch

from agentfit_ai.deepseek_evaluation import MODEL, NvidiaAnalyzer
from agentfit_ai.nvidia_streaming import _assemble_sse
from agentfit_ai.solar import AnalysisError


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
