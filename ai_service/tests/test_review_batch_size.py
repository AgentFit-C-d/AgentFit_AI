"""Changing batch size must preserve coverage, defaults and failure boundaries."""
from copy import deepcopy
import hashlib
import json
import unittest

from agentfit_ai.candidate_split_review import review_candidates_separately
from agentfit_ai.candidate_thinking_evaluation import evaluate_thinking_reviews
from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.profile import FIELDS
from agentfit_ai.real_document_holdout import PreparedCase
from agentfit_ai.solar import AnalysisError


def fixture(count=23):
    text = ' '.join(['Go'] * count) + ' Python'
    items = [{'id': f'C{i:03d}', 'start': i * 3, 'end': i * 3 + 2} for i in range(count)]
    items.append({'id': f'C{count:03d}', 'start': len(text) - 6, 'end': len(text)})
    labels = [{'id': item['id'], 'field': 'backend',
               'status': 'confirmed' if i < count else 'tentative'} for i, item in enumerate(items)]
    return text, {'candidates': items, 'rejected': []}, labels


def response(value, model='solar-pro4-260806', finish='stop'):
    return json.dumps({'model': model, 'choices': [{'finish_reason': finish,
                       'message': {'content': json.dumps(value)}}], 'usage': {}}).encode()


class ReviewBatchSizeTests(unittest.TestCase):
    def setUp(self):
        self.text, self.frozen, self.labels = fixture()
        self.requests = []

    def transport(self, payload, key, timeout):
        self.requests.append(deepcopy(payload))
        data = json.loads(payload['messages'][-1]['content'])
        if 'selections' in data:
            ids = [item['id'] for item in data['selections']]
            wrong = ['C005'] if 'C005' in ids else []
            value = {'checkedCandidateIds': ids, 'wrongCandidateIds': wrong}
            if 'rejectionReasons' in payload['response_format']['json_schema']['schema']['required']:
                value['rejectionReasons'] = [{'id': item, 'reason': 'wrong_field'} for item in wrong]
        else:
            value = {'checkedFields': list(FIELDS), 'missingFields': []}
        return response(value, model=MODEL if payload['model'] == MODEL else 'solar-pro4-260806')

    def review(self, **options):
        return review_candidates_separately(self.text, self.frozen, self.labels, 'test-secret',
            **{'transport': self.transport, **options})

    def evaluation(self, **options):
        case = PreparedCase('synthetic-batches', self.text,
            [{'id': 'C01', 'field': 'backend', 'contains_any': ['Go']}],
            'a' * 64, hashlib.sha256(self.text.encode()).hexdigest(), None, 0, 0)
        snapshot = {'state': 'finished', 'case_id': case.id, 'source_sha256': case.source_sha256,
            'redacted_sha256': case.redacted_sha256, 'candidate_count': len(self.labels),
            'rejected_candidate_count': 0, 'classification_refs': [
                {**item, **label} for item, label in zip(self.frozen['candidates'], self.labels)]}
        return evaluate_thinking_reviews(case, snapshot, 'test-secret', expected_keep={'C000': True, 'C005': False},
            **{'transport': self.transport, **options})

    def test_default_and_explicit_twenty_are_identical(self):
        before = self.review()
        baseline = deepcopy(self.requests)
        self.requests.clear()
        after = self.review(candidate_batch_size=20)
        self.assertEqual(before, after)
        self.assertEqual(self.requests, baseline)
        self.requests.clear()
        default = self.evaluation()
        baseline = deepcopy(self.requests)
        self.requests.clear()
        explicit = self.evaluation(candidate_batch_size=20)
        self.assertEqual(self.requests, baseline)
        self.assertEqual(explicit['planned_calls'], default['planned_calls'])

    def test_ten_visits_every_confirmed_occurrence_once_before_coverage(self):
        original = deepcopy((self.frozen, self.labels))
        calls = []
        result = self.review(candidate_batch_size=10, review_calls=calls)
        data = [json.loads(r['messages'][-1]['content']) for r in self.requests]
        self.assertEqual([len(d['selections']) for d in data[:-1]], [10, 10, 3])
        selected = [row for d in data[:-1] for row in d['selections']]
        self.assertEqual([r['id'] for r in selected], [r['id'] for r in self.labels[:-1]])
        for selection, source in zip(selected, self.frozen['candidates'][:-1]):
            self.assertEqual((selection['start'], selection['end']), (source['start'], source['end']))
            self.assertEqual(selection['value'], self.text[source['start']:source['end']])
        self.assertEqual(data[-1]['confirmedValues']['backend'], ['Go'])
        self.assertEqual(result['wrongCandidateIds'], ['C005'])
        self.assertEqual([c['batch_index'] for c in calls], [1, 2, 3, None])
        self.assertEqual([c['candidate_count'] for c in calls], [10, 10, 3, None])
        self.assertEqual((self.frozen, self.labels), original)

    def test_one_and_twenty_boundaries(self):
        for size, counts in ((1, [1] * 23), (20, [20, 3])):
            self.requests.clear()
            with self.subTest(size=size):
                self.review(candidate_batch_size=size)
                data = [json.loads(r['messages'][-1]['content']) for r in self.requests]
                self.assertEqual([len(d['selections']) for d in data[:-1]], counts)
                self.assertNotIn('selections', data[-1])

    def test_invalid_sizes_fail_before_both_entry_points_send(self):
        for value in (True, False, None, 0, -1, 21, 10.0, '10', [], {}):
            for method in (self.review, self.evaluation):
                with self.subTest(value=value, entry=method.__name__), self.assertRaises(ValueError):
                    method(candidate_batch_size=value)
        self.assertEqual(self.requests, [])

    def test_later_invalid_batch_does_not_reach_coverage(self):
        calls = []
        def invalid(payload, key, timeout):
            raw = self.transport(payload, key, timeout)
            if len(self.requests) == 2:
                envelope = json.loads(raw)
                value = json.loads(envelope['choices'][0]['message']['content'])
                value['checkedCandidateIds'].pop()
                return response(value)
            return raw
        with self.assertRaises(ValueError):
            self.review(candidate_batch_size=10, transport=invalid, review_calls=calls)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual([c['validated'] for c in calls], [True, False])
        self.assertTrue(all('selections' in json.loads(r['messages'][-1]['content']) for r in self.requests))

    def test_empty_confirmed_still_checks_coverage_once(self):
        self.text, self.frozen, self.labels = fixture(0)
        result = self.review(candidate_batch_size=1)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(result['checkedFields'], list(FIELDS))

    def test_solar_adaptive_ten_recovers_only_trusted_length_with_fives(self):
        self.text, self.frozen, self.labels = fixture(10)
        calls = []
        def length_once(payload, key, timeout):
            raw = self.transport(payload, key, timeout)
            return response({}, finish='length') if len(self.requests) == 1 else raw
        self.review(candidate_batch_size=10, adaptive_review=True, transport=length_once, review_calls=calls)
        self.assertEqual([c['candidate_count'] for c in calls], [10, 5, 5, None])
        self.assertEqual([c['sub_batch_index'] for c in calls], [None, 1, 2, None])
        self.assertTrue(calls[0]['recovered'])
        self.requests.clear()
        self.text, self.frozen, self.labels = fixture(5)
        with self.assertRaises(AnalysisError):
            self.review(candidate_batch_size=5, adaptive_review=True, transport=length_once)
        self.assertEqual(len(self.requests), 1)

    def test_evaluation_updates_both_arm_budgets_and_actual_batches(self):
        result = self.evaluation(candidate_batch_size=10)
        self.assertEqual(result['settings']['batch_size'], 10)
        self.assertEqual(result['planned_calls'], 8)
        self.assertEqual([a['attempted_calls'] for a in result['arms']], [4, 4])
        self.assertEqual([a['audit_matched'] for a in result['arms']], [2, 2])
        for arm in result['arms']:
            self.assertEqual([c['candidate_count'] for c in arm['review_calls']], [10, 10, 3, None])
            self.assertEqual([c['validated'] for c in arm['review_calls']], [True] * 4)

    def test_evaluation_late_failure_is_unscored_and_does_not_spend_rest_of_arm(self):
        def invalid(payload, key, timeout):
            raw = self.transport(payload, key, timeout)
            return response({}, model=MODEL, finish='length') if len(self.requests) in (2, 4) else raw
        result = self.evaluation(candidate_batch_size=10, transport=invalid)
        self.assertEqual(len(self.requests), 4)
        self.assertEqual(result['failed'], 2)
        for arm in result['arms']:
            self.assertNotIn('audit_matched', arm)
            self.assertNotIn('suggestion_checked', arm)
            self.assertEqual(arm['attempted_calls'], 2)
            self.assertEqual(arm['provider_error'], 'INCOMPLETE_RESPONSE')


if __name__ == '__main__':
    unittest.main()
