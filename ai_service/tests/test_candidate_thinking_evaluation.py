"""Paired thinking trials must preserve inputs, failure denominators and privacy."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest

from agentfit_ai.candidate_thinking_evaluation import evaluate_thinking_reviews
from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.profile import FIELDS
from agentfit_ai.real_document_holdout import PreparedCase
from agentfit_ai.solar import AnalysisError


class CandidateThinkingEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.text = '현재 PostgreSQL을 사용한다. MongoDB는 검토 중이다. Redis는 사용하지 않는다.'
        self.case = PreparedCase('synthetic', self.text,
            [{'id': 'C01', 'field': 'database', 'contains_any': ['PostgreSQL']}],
            'a' * 64, hashlib.sha256(self.text.encode()).hexdigest(), None, 0, 0)
        refs = []
        for index, value in enumerate(('PostgreSQL', 'MongoDB', 'Redis')):
            start = self.text.index(value)
            refs.append({'id': f'C{index:03}', 'start': start, 'end': start + len(value),
                         'field': 'database', 'status': 'confirmed'})
        self.snapshot = {'state': 'finished', 'case_id': self.case.id,
            'source_sha256': self.case.source_sha256, 'redacted_sha256': self.case.redacted_sha256,
            'candidate_count': 3, 'rejected_candidate_count': 0, 'classification_refs': refs}
        self.expected = {'C000': True, 'C001': False, 'C002': False}
        self.sent = []

    def transport(self, payload, key, timeout):
        self.sent.append(deepcopy(payload))
        self.assertEqual((key, timeout), ('nvidia-secret', 600))
        data = json.loads(payload['messages'][-1]['content'])
        if 'selections' in data:
            wrong = ['C001', 'C002'] if payload['chat_template_kwargs']['thinking'] else ['C002']
            content = {'checkedCandidateIds': ['C000', 'C001', 'C002'],
                       'wrongCandidateIds': wrong,
                       'rejectionReasons': [{'id': item, 'reason': 'not_current'} for item in wrong]}
        else:
            content = {'checkedFields': list(FIELDS), 'missingFields': []}
        return json.dumps({'model': MODEL, 'choices': [{'finish_reason': 'stop',
            'message': {'content': json.dumps(content)}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50}}).encode()

    def run_trial(self, **overrides):
        return evaluate_thinking_reviews(**{'case': self.case, 'snapshot': self.snapshot,
            'key': 'nvidia-secret', 'expected_keep': self.expected,
            'transport': self.transport, **overrides})

    def test_boolean_only_change_same_candidates_independent_scores(self):
        original = deepcopy(self.snapshot)
        result = self.run_trial()
        self.assertEqual(self.snapshot, original)
        self.assertEqual(len(self.sent), 4)
        before, after = deepcopy(self.sent[0]), deepcopy(self.sent[2])
        self.assertEqual(before.pop('chat_template_kwargs'), {'thinking': False})
        self.assertEqual(after.pop('chat_template_kwargs'), {'thinking': True})
        self.assertEqual(before, after)
        self.assertEqual((before['max_tokens'], before['temperature']), (8192, 0))
        self.assertNotIn('reasoning_effort', before)
        self.assertEqual([arm['audit_matched'] for arm in result['arms']], [2, 3])
        self.assertEqual([arm['audit_total'] for arm in result['arms']], [3, 3])
        self.assertEqual(result['state'], 'finished')
        self.assertEqual(result['planned_calls'], 4)
        for arm in result['arms']:
            self.assertEqual(arm['attempted_calls'], 2)
            self.assertEqual(arm['suggestion_checked'], 1)
            self.assertEqual(arm['verdict']['checkedFields'], list(FIELDS))

    def test_provider_failure_is_unassessed_and_second_arm_still_runs(self):
        count = 0
        def transport(payload, key, timeout):
            nonlocal count
            count += 1
            if count == 1:
                payload['messages'].clear()
                raise AnalysisError('PROVIDER_UNAVAILABLE')
            return self.transport(payload, key, timeout)
        result = self.run_trial(transport=transport)
        self.assertEqual(count, 3)
        failed, good = result['arms']
        self.assertEqual(failed['outcome'], 'failed')
        self.assertEqual(failed['provider_error'], 'PROVIDER_UNAVAILABLE')
        self.assertNotIn('audit_matched', failed)
        self.assertNotIn('suggestion_checked', failed)
        self.assertEqual(good['audit_matched'], 3)
        self.assertEqual(result['failed'], 1)

    def test_explicit_effort_changes_only_thinking_arm_and_records_requested_setting(self):
        result = self.run_trial(thinking_effort=25, structured_output=False)
        self.assertEqual(result['settings']['thinking_effort_requested'], 25)
        self.assertEqual([arm['reasoning_effort_requested'] for arm in result['arms']], [None, 25])
        before, after = deepcopy(self.sent[0]), deepcopy(self.sent[2])
        self.assertEqual(before.pop('chat_template_kwargs'), {'thinking': False})
        self.assertEqual(after.pop('chat_template_kwargs'), {'thinking': True, 'reasoning_effort': 25})
        self.assertEqual(before, after)
        for request in self.sent:
            self.assertNotIn('response_format', request)
            self.assertIn('JSON Schema:', request['messages'][0]['content'])
            self.assertNotIn('reasoning_effort', {k: v for k, v in request.items() if k != 'chat_template_kwargs'})

    def test_invalid_effort_fails_before_any_request(self):
        for effort in (True, False, 0, -1, 101, 25.0, '25', [], {}):
            with self.subTest(effort=effort), self.assertRaises(ValueError):
                self.run_trial(thinking_effort=effort)
        self.assertEqual(self.sent, [])

    def test_optional_shape_capture_preserves_requests_and_default_reports(self):
        default = self.run_trial()
        original = deepcopy(self.sent)
        self.assertTrue(all('response_shape' not in attempt for arm in default['arms']
                            for attempt in arm['transport_attempts']))
        self.sent.clear()
        captured = self.run_trial(capture_response_shape=True)
        self.assertEqual(self.sent, original)
        self.assertTrue(captured['settings']['capture_response_shape'])
        self.assertTrue(all(attempt['response_shape']['issue'] is None for arm in captured['arms']
                            for attempt in arm['transport_attempts']))

    def test_shape_capture_does_not_repair_fence_or_leak_private_content(self):
        def fenced(payload, key, timeout):
            reply = json.loads(self.transport(payload, key, timeout))
            reply['choices'][0]['message']['content'] = '```json\n' + reply['choices'][0]['message']['content'] + '\n```'
            reply['choices'][0]['message']['reasoning_content'] = 'private reasoning value'
            return json.dumps(reply).encode()
        result = self.run_trial(capture_response_shape=True, transport=fenced)
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(result['failed'], 2)
        for arm in result['arms']:
            self.assertNotIn('audit_matched', arm)
            self.assertEqual(arm['provider_error'], 'INVALID_RESPONSE')
            shape = arm['transport_attempts'][0]['response_shape']
            self.assertEqual(shape['issue'], 'CONTENT_JSON')
            self.assertTrue(shape['fenced_json'])
        for private in (self.text, 'nvidia-secret', 'checkedCandidateIds', 'private reasoning value'):
            self.assertNotIn(private, json.dumps(result, ensure_ascii=False))

    def test_shape_option_requires_boolean_before_request(self):
        for value in (None, 1, 'true', []):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                self.run_trial(capture_response_shape=value)
        self.assertEqual(self.sent, [])

    def test_opt_in_fence_normalization_preserves_requests_and_prior_diagnostics(self):
        baseline = self.run_trial()
        requests = deepcopy(self.sent)
        self.sent.clear()
        def fenced(payload, key, timeout):
            reply = json.loads(self.transport(payload, key, timeout))
            reply['choices'][0]['message']['content'] = '```json\n' + reply['choices'][0]['message']['content'] + '\n```'
            return json.dumps(reply).encode()
        result = self.run_trial(transport=fenced, normalize_json_fences=True, capture_response_shape=True)
        self.assertEqual(self.sent, requests)
        self.assertEqual([r['audit_matched'] for r in result['arms']], [r['audit_matched'] for r in baseline['arms']])
        self.assertTrue(result['settings']['normalize_json_fences'])
        for arm in result['arms']:
            for attempt in arm['transport_attempts']:
                self.assertTrue(attempt['json_fence_normalized'])
                self.assertEqual(attempt['response_shape']['issue'], 'CONTENT_JSON')
        self.assertTrue(all('json_fence_normalized' not in a for r in baseline['arms'] for a in r['transport_attempts']))

    def test_normalization_keeps_id_model_sensitive_and_finish_failures(self):
        for kind, error in (('id', 'INVALID_REVIEW_CONTRACT'), ('model', 'PROVIDER_MODEL'),
                            ('sensitive', 'SENSITIVE_CONTENT'), ('length', 'INCOMPLETE_RESPONSE')):
            self.sent.clear()
            def invalid(payload, key, timeout):
                reply = json.loads(self.transport(payload, key, timeout))
                msg = reply['choices'][0]['message']
                value = json.loads(msg['content'])
                if kind == 'id':
                    value['wrongCandidateIds'] = ['C999']
                if kind == 'model':
                    reply['model'] = 'untrusted-model'
                if kind == 'sensitive':
                    msg['reasoning_content'] = 'nvidia-secret'
                if kind == 'length':
                    reply['choices'][0]['finish_reason'] = 'length'
                msg['content'] = '```json\n' + json.dumps(value) + '\n```'
                return json.dumps(reply).encode()
            with self.subTest(kind=kind):
                result = self.run_trial(transport=invalid, normalize_json_fences=True)
                self.assertEqual(len(self.sent), 2)
                self.assertEqual(result['failed'], 2)
                for arm in result['arms']:
                    self.assertNotIn('audit_matched', arm)
                    if kind == 'id':
                        self.assertEqual(arm['error'], 'COVERAGE_REVIEW_FAILED')
                        self.assertEqual(arm['review_calls'][0]['error'], error)
                        self.assertEqual(arm['review_calls'][0]['contract_issue'],
                                         'WRONG_CANDIDATE_IDS_MEMBER')
                    else:
                        self.assertEqual(arm['provider_error'], error)
                self.assertNotIn('nvidia-secret', json.dumps(result))
                self.assertNotIn('untrusted-model', json.dumps(result))

    def test_normalization_requires_boolean_before_request(self):
        for value in (None, 1, 'true', []):
            with self.assertRaises(ValueError):
                self.run_trial(normalize_json_fences=value)
        self.assertEqual(self.sent, [])

    def test_effort_boundaries_and_none_preserve_default_requests(self):
        for effort in (1, 100, None):
            with self.subTest(effort=effort):
                self.sent.clear()
                result = self.run_trial(thinking_effort=effort)
                self.assertEqual(result['settings']['thinking_effort_requested'], effort)
                for request in self.sent:
                    kwargs = request['chat_template_kwargs']
                    expected = {'thinking': kwargs['thinking']}
                    if kwargs['thinking'] and effort is not None:
                        expected['reasoning_effort'] = effort
                    self.assertEqual(kwargs, expected)
                if effort is None:
                    explicit_none = deepcopy(self.sent)
                    self.sent.clear()
                    self.run_trial()
                    self.assertEqual(self.sent, explicit_none)

    def test_schema_free_pair_preserves_prompts_and_still_rejects_invalid_json(self):
        result = self.run_trial(structured_output=False)
        self.assertEqual(result['settings']['structured_output'], False)
        self.assertTrue(all('response_format' not in request for request in self.sent))
        a, b = deepcopy(self.sent[0]), deepcopy(self.sent[2])
        a.pop('chat_template_kwargs')
        b.pop('chat_template_kwargs')
        self.assertEqual(a, b)
        self.assertEqual(result['arms'][1]['audit_matched'], 3)
        def invalid(payload, key, timeout):
            reply = json.loads(self.transport(payload, key, timeout))
            reply['choices'][0]['message']['content'] = 'not-json-private'
            return json.dumps(reply).encode()
        bad = self.run_trial(structured_output=False, transport=invalid)
        self.assertEqual(bad['failed'], 2)
        self.assertTrue(all('audit_matched' not in arm for arm in bad['arms']))
        self.assertNotIn('not-json-private', json.dumps(bad))

    def test_schema_free_pair_retains_exact_schema_in_system_prompt(self):
        self.run_trial()
        original = deepcopy(self.sent)
        self.sent.clear()
        self.run_trial(structured_output=False)
        marker = '\nReturn exactly one JSON object, without Markdown, matching this JSON Schema:\n'
        for before, after in zip(original, self.sent, strict=True):
            self.assertEqual(before['messages'][1:], after['messages'][1:])
            prefix, separator, schema = after['messages'][0]['content'].partition(marker)
            self.assertEqual(prefix, before['messages'][0]['content'])
            self.assertEqual(separator, marker)
            self.assertEqual(json.loads(schema), before['response_format']['json_schema']['schema'])
            self.assertNotIn('response_format', after)

    def test_invalid_snapshot_gold_key_and_observer_fail_before_request(self):
        bad_snapshot = {**self.snapshot, 'redacted_sha256': 'b' * 64}
        bad_case = replace(self.case, checks=[{'id': 'C01', 'field': 'bad', 'expect_null': True}])
        for overrides in ({'snapshot': bad_snapshot}, {'expected_keep': {'C999': True}},
                          {'expected_keep': {'C000': 1}}, {'expected_keep': {}},
                          {'case': bad_case}, {'key': ''}, {'key': 'PostgreSQL'},
                          {'on_update': 1}, {'transport': 1}, {'structured_output': 1}):
            with self.subTest(overrides=list(overrides)), self.assertRaises(ValueError):
                self.run_trial(**overrides)
        self.assertEqual(self.sent, [])

    def test_progress_is_detached_and_contains_no_values_or_gold(self):
        updates = []
        def observer(report):
            updates.append(deepcopy(report))
            report['arms'].clear()
        result = self.run_trial(on_update=observer)
        self.assertEqual(len(result['arms']), 2)
        self.assertTrue(any(row.get('active_thinking') is True for row in updates))
        self.assertEqual(updates[-1]['state'], 'finished')
        text = json.dumps([result, updates], ensure_ascii=False)
        for private in (self.text, 'PostgreSQL', 'MongoDB', 'Redis', 'nvidia-secret', 'expected_keep'):
            self.assertNotIn(private, text)
        for payload in self.sent:
            self.assertNotIn('expected_keep', json.dumps(payload))

    def test_callback_failure_stops_without_retry_or_next_arm(self):
        def observer(report):
            if self.sent:
                raise RuntimeError('private observer detail')
        with self.assertRaisesRegex(RuntimeError, '^progress observer failed$'):
            self.run_trial(on_update=observer)
        self.assertEqual(len(self.sent), 1)

    def test_one_time_callback_failure_is_not_swallowed_by_provider_parser(self):
        raised = False
        def observer(report):
            nonlocal raised
            if self.sent and not raised:
                raised = True
                raise OSError('private write detail')
        with self.assertRaisesRegex(RuntimeError, '^progress observer failed$'):
            self.run_trial(on_update=observer)
        self.assertEqual(len(self.sent), 1)

    def test_length_and_invalid_contract_are_not_scored(self):
        for kind in ('length', 'contract'):
            def transport(payload, key, timeout):
                reply = json.loads(self.transport(payload, key, timeout))
                if kind == 'length':
                    reply['choices'][0]['finish_reason'] = 'length'
                else:
                    value = json.loads(reply['choices'][0]['message']['content'])
                    value['checkedCandidateIds'].reverse()
                    reply['choices'][0]['message']['content'] = json.dumps(value)
                return json.dumps(reply).encode()
            with self.subTest(kind=kind):
                result = self.run_trial(transport=transport)
                self.assertEqual(result['failed'], 2)
                self.assertTrue(all('audit_matched' not in row for row in result['arms']))

    def test_unknown_exception_and_untrusted_model_text_are_not_reported(self):
        for kind in ('exception', 'model'):
            def transport(payload, key, timeout):
                if kind == 'exception':
                    raise RuntimeError(self.text + ' nvidia-secret')
                reply = json.loads(self.transport(payload, key, timeout))
                reply['model'] = self.text
                return json.dumps(reply).encode()
            result = self.run_trial(transport=transport)
            self.assertEqual(result['failed'], 2)
            self.assertNotIn(self.text, json.dumps(result, ensure_ascii=False))
            self.assertNotIn('nvidia-secret', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
