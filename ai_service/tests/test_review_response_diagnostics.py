"""Safe diagnostics explain rejection without changing response acceptance."""
import json
import unittest
from unittest.mock import patch

from agentfit_ai.review_response_diagnostics import describe_review_response
from agentfit_ai.solar import MAX_RESPONSE_BYTES


class ReviewResponseDiagnosticsTests(unittest.TestCase):
    keys = ('checkedCandidateIds', 'wrongCandidateIds', 'rejectionReasons')

    def envelope(self, content, **message_fields):
        return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
            'content': content, **message_fields}}]}).encode()

    def describe(self, raw):
        return describe_review_response(raw, self.keys)

    def test_valid_shape_has_no_values_and_is_not_semantic_validation(self):
        content = json.dumps(dict.fromkeys(self.keys, 'private incorrect value'))
        row = self.describe(self.envelope(content))
        self.assertIsNone(row['issue'])
        self.assertEqual(row['json_kind'], 'object')
        self.assertEqual((row['missing_key_count'], row['unexpected_key_count']), (0, 0))
        self.assertNotIn('private', json.dumps(row))

    def test_complete_json_fence_is_diagnosed_but_still_invalid(self):
        obj = json.dumps(dict.fromkeys(self.keys, []))
        for text in ('```json\n' + obj + '\n```', '  ```JSON\r\n' + obj + '\r\n```  '):
            with self.subTest(kind=text[:8]):
                row = self.describe(self.envelope(text))
                self.assertEqual(row['issue'], 'CONTENT_JSON')
                self.assertTrue(row['fenced_json'])
                self.assertTrue(row['fenced_object_keys_match'])
        for text in ('prose\n```json\n' + obj + '\n```',
                     '```json\n' + obj + '\n```\ntrailer',
                     '```json\n{}\n```\n```json\n{}\n```',
                     '```python\n' + obj + '\n```', '```json\nnot-json\n```'):
            row = self.describe(self.envelope(text))
            self.assertEqual(row['issue'], 'CONTENT_JSON')
            self.assertFalse(row['fenced_json'])

    def test_missing_and_unexpected_keys_are_counts_without_names(self):
        row = self.describe(self.envelope(json.dumps({'private-key': 'private-value', self.keys[0]: []})))
        self.assertEqual(row['issue'], 'CONTENT_KEYS')
        self.assertEqual((row['missing_key_count'], row['unexpected_key_count']), (2, 1))
        self.assertNotIn('private', json.dumps(row))

    def test_duplicate_keys_and_malformed_json_do_not_become_objects(self):
        for content in ('{"x":1,"x":2}', '{"private":', 'private prose'):
            row = self.describe(self.envelope(content))
            self.assertEqual(row['issue'], 'CONTENT_JSON')
            self.assertNotIn('private', json.dumps(row))

    def test_non_object_json_root_types_have_fixed_names(self):
        for value, kind in (([], 'array'), ('private', 'string'), (None, 'null'),
                            (True, 'boolean'), (3.5, 'number')):
            with self.subTest(kind=kind):
                row = self.describe(self.envelope(json.dumps(value)))
                self.assertEqual((row['issue'], row['json_kind']), ('CONTENT_ROOT', kind))

    def test_bad_envelopes_have_fixed_issues(self):
        cases = [(None, 'RAW_TYPE'), ('private', 'RAW_TYPE'),
                 (b'x' * (MAX_RESPONSE_BYTES + 1), 'RAW_SIZE'), (b'{private', 'ENVELOPE_JSON'),
                 (b'[]', 'ENVELOPE_ROOT'), (b'{}', 'CHOICES_SHAPE'),
                 (b'{"choices":[{}]}', 'MESSAGE_SHAPE'),
                 (self.envelope(None), 'CONTENT_TYPE'), (self.envelope([]), 'CONTENT_TYPE'),
                 (self.envelope('', refusal='private reason'), 'REFUSAL'),
                 (self.envelope('{}', tool_calls=[{'private': 'value'}]), 'TOOLS')]
        for raw, issue in cases:
            with self.subTest(issue=issue):
                row = self.describe(raw)
                self.assertEqual(row['issue'], issue)
                self.assertNotIn('private', json.dumps(row))

    def test_non_stop_is_not_accepted_even_with_valid_content(self):
        for finish in ('length', 'tool_calls', 'private finish', None):
            raw = json.dumps({'choices': [{'finish_reason': finish, 'message': {
                'content': json.dumps(dict.fromkeys(self.keys, []))}}]}).encode()
            row = self.describe(raw)
            self.assertEqual(row['issue'], 'NON_STOP_FINISH')
            self.assertNotIn('private', json.dumps(row))

    def test_deep_roots_and_large_integer_are_rejected_without_details(self):
        cases = ((b'[' * 2000 + b']' * 2000, ('ENVELOPE_JSON', 'ENVELOPE_ROOT')),
                 (self.envelope('[' * 2000 + ']' * 2000), ('CONTENT_JSON', 'CONTENT_ROOT')),
                 (self.envelope('9' * 10000), ('CONTENT_JSON',)))
        for raw, allowed in cases:
            row = self.describe(raw)
            self.assertIn(row['issue'], allowed)

    def test_parser_recursion_error_uses_fixed_issue(self):
        with patch('agentfit_ai.review_response_diagnostics._json', side_effect=RecursionError('private details')):
            self.assertEqual(self.describe(b'{}')['issue'], 'ENVELOPE_JSON')
        envelope = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
        with patch('agentfit_ai.review_response_diagnostics._json', side_effect=[envelope, RecursionError('private details')]):
            row = self.describe(b'{}')
            self.assertEqual(row['issue'], 'CONTENT_JSON')
            self.assertNotIn('private', json.dumps(row))

    def test_expected_keys_are_bounded_and_validated(self):
        for keys in (None, 'private', [], [1], ['a', 'a'], [''], [str(i) for i in range(33)]):
            with self.subTest(kind=type(keys).__name__), self.assertRaisesRegex(ValueError, '^invalid response diagnostic keys$'):
                describe_review_response(b'{}', keys)
        for keys in (['a'], tuple(str(i) for i in range(32))):
            self.assertEqual(describe_review_response(self.envelope('{}'), keys)['issue'], 'CONTENT_KEYS')


if __name__ == '__main__':
    unittest.main()
