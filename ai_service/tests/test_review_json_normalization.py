"""Only complete fenced JSON may change content; validation remains downstream."""
from copy import deepcopy
import json
import unittest

from agentfit_ai.review_json_normalization import normalize_review_json_fence
from agentfit_ai.solar import MAX_RESPONSE_BYTES


class ReviewJsonNormalizationTests(unittest.TestCase):
    keys = ('a', 'b')

    def envelope(self, content, *, finish='stop', **message):
        return {'model': 'unchanged-model', 'choices': [{'index': 0, 'finish_reason': finish,
            'message': {'role': 'assistant', 'content': content, 'reasoning_content': 'private reasoning', **message}}],
            'usage': {'prompt_tokens': 3}, 'provider_extra': {'label': 'private value'}}

    def encode(self, content, **kwargs):
        return json.dumps(self.envelope(content, **kwargs)).encode()

    def normalize(self, raw):
        return normalize_review_json_fence(raw, self.keys)

    def test_plain_json_bytes_are_identical(self):
        raw = self.encode('{"a":[],"b":[]}')
        result, changed = self.normalize(raw)
        self.assertIs(result, raw)
        self.assertFalse(changed)

    def test_single_fence_changes_only_content_and_preserves_inner_text(self):
        inner = '{"a": "한글 ``` value", "b": [1, 2]}'
        for language, newline in (('json', '\n'), ('JSON', '\r\n'), ('', '\n')):
            original = self.envelope('  ```' + language + newline + inner + newline + '```  ')
            expected = deepcopy(original)
            expected['choices'][0]['message']['content'] = inner
            output, changed = self.normalize(json.dumps(original).encode())
            self.assertTrue(changed)
            self.assertEqual(json.loads(output), expected)

    def test_ambiguous_partial_multi_block_and_wrong_keys_are_unchanged(self):
        obj = '{"a":[],"b":[]}'
        cases = ('prose\n```json\n' + obj + '\n```', '```json\n' + obj + '\n```\nprose',
            '```json\n' + obj, '```json\n{}\n```\n```json\n' + obj + '\n```',
            '```python\n' + obj + '\n```', '```json\n[]\n```', '```json\n{"a":[]}\n```',
            '```json\n{"a":[],"b":[],"extra":[]}\n```', '```json\n{"a":[],"a":[],"b":[]}\n```')
        for content in cases:
            raw = self.encode(content)
            output, changed = self.normalize(raw)
            self.assertIs(output, raw)
            self.assertFalse(changed)

    def test_nonstandard_json_constants_are_not_unwrapped(self):
        for constant in ('NaN', 'Infinity', '-Infinity'):
            raw = self.encode('```json\n{"a":' + constant + ',"b":[]}\n```')
            output, changed = self.normalize(raw)
            self.assertIs(output, raw)
            self.assertFalse(changed)

    def test_bad_envelopes_refusal_tools_and_non_stop_are_unchanged(self):
        content = '```json\n{"a":[],"b":[]}\n```'
        for raw in (None, b'{bad', b'[]', self.encode(content, finish='length'),
                    self.encode(content, refusal='private'), self.encode(content, tool_calls=[{}]),
                    self.encode(None)):
            output, changed = self.normalize(raw)
            self.assertIs(output, raw)
            self.assertFalse(changed)

    def test_input_limit_preserves_original(self):
        raw = b' ' * (MAX_RESPONSE_BYTES + 1)
        output, changed = self.normalize(raw)
        self.assertIs(output, raw)
        self.assertFalse(changed)

    def test_output_limit_preserves_original_even_when_numbers_expand(self):
        envelope = self.envelope('```json\n{"a":[],"b":[]}\n```')
        envelope['extra'] = [10.0] * 240000
        raw = json.dumps(envelope, separators=(',', ':')).encode().replace(b'10.0', b'1e1')
        self.assertLess(len(raw), MAX_RESPONSE_BYTES)
        output, changed = self.normalize(raw)
        self.assertIs(output, raw)
        self.assertFalse(changed)

    def test_unencodable_envelope_metadata_keeps_original(self):
        envelope = self.envelope('```json\n{"a":[],"b":[]}\n```')
        envelope['private_extra'] = '\ud800'
        raw = json.dumps(envelope).encode()
        output, changed = self.normalize(raw)
        self.assertIs(output, raw)
        self.assertFalse(changed)

    def test_expected_keys_use_existing_validation(self):
        for keys in (None, [], ['a', 'a']):
            with self.assertRaises(ValueError):
                normalize_review_json_fence(b'{}', keys)


if __name__ == '__main__':
    unittest.main()
