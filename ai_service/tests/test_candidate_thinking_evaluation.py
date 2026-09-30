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
        schema = payload['response_format']['json_schema']['name']
        if schema == 'agentfit_candidate_label_review':
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

    def test_invalid_snapshot_gold_key_and_observer_fail_before_request(self):
        bad_snapshot = {**self.snapshot, 'redacted_sha256': 'b' * 64}
        bad_case = replace(self.case, checks=[{'id': 'C01', 'field': 'bad', 'expect_null': True}])
        for overrides in ({'snapshot': bad_snapshot}, {'expected_keep': {'C999': True}},
                          {'expected_keep': {'C000': 1}}, {'expected_keep': {}},
                          {'case': bad_case}, {'key': ''}, {'key': 'PostgreSQL'},
                          {'on_update': 1}, {'transport': 1}):
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
